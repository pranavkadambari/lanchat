import asyncio, time, uuid
from typing import Dict, Optional, Any, List, Callable
from .models import RoomState, Member, Message, new_id
from .transport import TCPServer, TCPClient, pack_frame, read_frame
from .discovery import DiscoveryService
from .mentions import extract_mentions
from .msgbus import MsgBus
from .netwatch import get_primary_ip

DEFAULT_TCP_PORT = 45999
ROOM_TTL = 6.0  # seconds

class HostRoomCtx:
    def __init__(self, room: RoomState, server: TCPServer, announcer: Callable[[], Dict[str, Any]]):
        self.room = room
        self.server = server
        self.announcer_supplier = announcer
        self.peer_writers: Dict[str, asyncio.StreamWriter] = {}

class SessionManager:
    def __init__(self, bus: MsgBus, nick: str):
        self.bus = bus
        self.nick = nick
        self.host_id: str = str(uuid.uuid4())

        # Multi-host rooms keyed by room name
        self.host_rooms: Dict[str, HostRoomCtx] = {}

        # Peer multi-room
        self.peer_rooms: Dict[str, TCPClient] = {}  # room -> TCPClient
        self.active_room: Optional[str] = None

        # Discovery state
        self.discovery = DiscoveryService(self._on_announce)
        self.rooms_index: Dict[str, Dict[str, Any]] = {}  # room_id -> payload{...,'last_seen'}
        self.joined_room_ids: set[str] = set()

        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        await self.discovery.start()
        asyncio.create_task(self.bus.pump())
        self._cleanup_task = asyncio.create_task(self._ttl_cleanup())

    async def stop(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
        await self.discovery.stop()
        for ctx in self.host_rooms.values():
            await ctx.server.stop()
        for c in self.peer_rooms.values():
            await c.close()

    # --------- Discovery handling ---------
    def _on_announce(self, payload: Dict[str, Any]):
        room_id = payload.get('room_id')
        if not room_id:
            return
        payload['last_seen'] = time.time()
        self.rooms_index[room_id] = payload

    def _filtered_rooms(self) -> List[Dict[str, Any]]:
        out = []
        for r in self.rooms_index.values():
            if r.get('host_id') == self.host_id:
                continue
            if r.get('room_id') in self.joined_room_ids:
                continue
            out.append(r)
        out.sort(key=lambda x: (x.get('room',''), x.get('from_addr',''), int(x.get('host_tcp_port',0))))
        return out

    async def _ttl_cleanup(self):
        while True:
            await asyncio.sleep(2.0)
            now = time.time()
            dead = [rid for rid, r in self.rooms_index.items() if now - r.get('last_seen', 0) > ROOM_TTL]
            changed = False
            for rid in dead:
                self.rooms_index.pop(rid, None)
                changed = True
            if changed:
                await self.bus.publish('discovery.rooms', self._filtered_rooms())

    def get_discovered_rooms(self) -> List[Dict[str, Any]]:
        return self._filtered_rooms()

    # --------- Hosting (multi-room) ---------
    async def host_create(self, room_name: str, enc: bool = False, history_limit: int = 200, port: int = DEFAULT_TCP_PORT):
        if room_name in self.host_rooms:
            # If same name already hosted, just focus that room
            await self.bus.publish('system.info', {'text': f'Room {room_name} already hosted.'})
            return

        room = RoomState(id=new_id(), name=room_name, enc_flag=enc, history_limit=history_limit)
        room.set_history_limit(history_limit)
        me = Member(peer_id='host', nick=self.nick, addr='127.0.0.1')
        room.members[me.peer_id] = me

        async def on_client(reader, writer):
            addr = writer.get_extra_info('peername')
            peer_id = new_id()
            try:
                join = await read_frame(reader)
                if join.get('type') != 'JOIN' or join.get('room') != room.name:
                    writer.close(); await writer.wait_closed(); return
                nick = join.get('nick', f'peer-{peer_id[:4]}')
                room.members[peer_id] = Member(peer_id=peer_id, nick=nick, addr=f"{addr[0]}:{addr[1]}")
                ctx.peer_writers[peer_id] = writer

                # Snapshot + backlog
                await self._send_member_snapshot(writer, room)
                await self._send_backlog(writer, room)
                await self._broadcast_presence(room)
                while True:
                    frame = await read_frame(reader)
                    if frame.get('type') == 'MSG':
                        text = frame.get('text', '')
                        msg = Message(msg_id=new_id(), ts=time.time(), from_id=peer_id,
                                      nick=nick, room=room.name, text=text,
                                      mentions=extract_mentions(text))
                        room.messages.append(msg)
                        await self._broadcast_msg_to_peers(room, msg)
            except Exception:
                pass
            finally:
                try:
                    ctx.peer_writers.pop(peer_id, None)
                    room.members.pop(peer_id, None)
                    await self._broadcast_presence(room)
                except Exception:
                    pass
                try:
                    writer.close(); await writer.wait_closed()
                except Exception:
                    pass

        server = TCPServer('0.0.0.0', port, on_client)
        await server.start()
        bound_port = server.bound_port()
        ip = await get_primary_ip()

        # Announcer supplier for this room
        def supplier():
            return {
                'room': room.name,
                'room_id': room.id,
                'host_id': self.host_id,
                'host_ip': ip,
                'host_tcp_port': bound_port,
                'enc': room.enc_flag,
                'member_count': len(room.members),
            }

        # Register announcer and context
        self.discovery.add_announcer(supplier)
        ctx = HostRoomCtx(room=room, server=server, announcer=supplier)
        self.host_rooms[room.name] = ctx

        # Mark as joined (as host)
        self.joined_room_ids.add(room.id)
        await self.bus.publish('discovery.rooms', self._filtered_rooms())
        # Local presence update for UI
        await self._broadcast_presence_local(room)

    async def _send_member_snapshot(self, writer, room: RoomState):
        snapshot = {
            'type': 'PRESENCE',
            'room': room.name,
            'mode': 'snapshot',
            'members': [{ 'peer_id': m.peer_id, 'nick': m.nick } for m in room.members.values()],
        }
        writer.write(pack_frame(snapshot)); await writer.drain()

    async def _send_backlog(self, writer, room: RoomState):
        backlog = {
            'type': 'BACKLOG',
            'room': room.name,
            'messages': [m.__dict__ for m in list(room.messages)],
            'limit': room.history_limit
        }
        writer.write(pack_frame(backlog)); await writer.drain()

    async def _broadcast_presence(self, room: RoomState):
        frame = {
            'type': 'PRESENCE',
            'room': room.name,
            'mode': 'update',
            'members': [{ 'peer_id': m.peer_id, 'nick': m.nick } for m in room.members.values()],
        }
        ctx = self.host_rooms.get(room.name)
        if ctx:
            for w in list(ctx.peer_writers.values()):
                try:
                    w.write(pack_frame(frame)); await w.drain()
                except Exception:
                    pass
        await self._broadcast_presence_local(room)

    async def _broadcast_presence_local(self, room: RoomState):
        await self.bus.publish('presence.update', {
            'room': room.name,
            'members': [{ 'peer_id': m.peer_id, 'nick': m.nick } for m in room.members.values()]
        })

    async def _broadcast_msg_to_peers(self, room: RoomState, msg: Message):
        frame = {
            'type': 'MSG',
            'room': room.name,
            'payload': msg.__dict__,
        }
        ctx = self.host_rooms.get(room.name)
        if ctx:
            for w in list(ctx.peer_writers.values()):
                try:
                    w.write(pack_frame(frame)); await w.drain()
                except Exception:
                    pass
        await self.bus.publish('message.new', msg.__dict__)

    # --------- Peer joining ---------
    async def peer_join(self, selected: Dict[str, Any], nick: str):
        room_name = selected['room']
        host_ip = selected['from_addr'] or selected.get('host_ip')
        port = int(selected['host_tcp_port'])
        room_id = selected['room_id']

        if selected.get('host_id') == self.host_id:
            await self.bus.publish('system.info', {'text': 'Cannot join your own room.'})
            return

        client = TCPClient(host_ip, port)
        await client.connect()
        await client.send({'type': 'JOIN', 'room': room_name, 'nick': nick})

        snap = await client.recv()
        if snap.get('type') == 'PRESENCE' and snap.get('room') == room_name:
            await self.bus.publish('presence.update', {'room': room_name, 'members': snap.get('members', [])})
        backlog = await client.recv()
        if backlog.get('type') == 'BACKLOG' and backlog.get('room') == room_name:
            for m in backlog.get('messages', []):
                await self.bus.publish('message.new', m)

        self.peer_rooms[room_name] = client
        self.active_room = self.active_room or room_name
        self.joined_room_ids.add(room_id)
        await self.bus.publish('discovery.rooms', self._filtered_rooms())
        asyncio.create_task(self._peer_reader(room_name, client))

    async def _peer_reader(self, room_name: str, client: TCPClient):
        try:
            while True:
                frame = await client.recv()
                if frame.get('type') == 'MSG' and frame.get('room') == room_name:
                    payload = frame.get('payload', {})
                    await self.bus.publish('message.new', payload)
                elif frame.get('type') == 'PRESENCE' and frame.get('room') == room_name:
                    await self.bus.publish('presence.update', {'room': room_name, 'members': frame.get('members', [])})
        except Exception:
            await self.bus.publish('system.info', {'text': f'Disconnected from host of room {room_name}. Room closed.'})

    # --------- Active room + sending ---------
    def set_active_room(self, room_name: str):
        self.active_room = room_name

    async def send_message(self, text: str):
        if not text.strip():
            return
        room = self.active_room
        if not room:
            await self.bus.publish('system.info', {'text': 'No active room.'})
            return
        # If hosting that room
        ctx = self.host_rooms.get(room)
        if ctx:
            msg = Message(msg_id=new_id(), ts=time.time(), from_id='host',
                          nick=self.nick, room=room, text=text,
                          mentions=extract_mentions(text))
            ctx.room.messages.append(msg)
            await self._broadcast_msg_to_peers(ctx.room, msg)
            return
        # Peer room
        client = self.peer_rooms.get(room)
        if client:
            await client.send({'type': 'MSG', 'room': room, 'text': text})
            return
        await self.bus.publish('system.info', {'text': f'Room {room} not joined.'})
