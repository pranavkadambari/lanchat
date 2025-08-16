import asyncio, threading, time
import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any
from ...core.msgbus import MsgBus
from ...core.session import SessionManager
from .views import ChatView

class TkApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('LAN Chat')
        self.bus = MsgBus()

        self.nick = self._prompt_nick()
        self.session = SessionManager(self.bus, nick=self.nick)

        self.rooms_cache: List[Dict[str, Any]] = []
        self.joined_rooms: List[str] = []  # room names
        self.room_messages: Dict[str, List[str]] = {}
        self.room_members: Dict[str, List[Dict[str, Any]]] = {}
        self.current_room: str | None = None

        self.view = ChatView(
            self.root,
            on_send=self._on_send,
            on_create_room=self._on_create_room,
            on_join_selected_room=self._on_join_selected_room,
            on_switch_room=self._on_switch_room,
            on_refresh_rooms=self._on_refresh_rooms
        )

        # Subscribe
        self.bus.subscribe('message.new', self._on_message)
        self.bus.subscribe('presence.update', self._on_presence)
        self.bus.subscribe('discovery.rooms', self._on_discovery_rooms)
        self.bus.subscribe('system.info', self._on_system_info)

        # Start asyncio loop in a thread
        self.loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()
        asyncio.run_coroutine_threadsafe(self.session.start(), self.loop)

        self._tick()

    def _prompt_nick(self) -> str:
        d = tk.Toplevel()
        d.title('Nickname')
        ttk.Label(d, text='Enter your nickname:').pack(padx=10, pady=10)
        e = ttk.Entry(d); e.pack(padx=10, pady=10); e.focus_set()
        val = {'nick': None}
        def ok():
            v = e.get().strip()
            if v:
                val['nick'] = v
                d.destroy()
        ttk.Button(d, text='OK', command=ok).pack(padx=10, pady=(0,10))
        d.grab_set()
        d.wait_window()
        return val['nick'] or 'User'

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _tick(self):
        self.root.after(100, self._tick)

    # UI callbacks
    def _on_send(self, text: str):
        asyncio.run_coroutine_threadsafe(self.session.send_message(text), self.loop)

    def _on_create_room(self, name: str, enc: bool):
        header = f"{name} (Host) Enc:{'ON' if enc else 'OFF'}"
        self.view.set_room_title(header)
        if name not in self.joined_rooms:
            self.joined_rooms.append(name)
            self.view.set_joined_rooms(self.joined_rooms)
        self.current_room = name
        self.session.set_active_room(name)
        asyncio.run_coroutine_threadsafe(self.session.host_create(name, enc=enc), self.loop)

    def _on_join_selected_room(self, idx: int, nick: str):
        if idx < 0 or idx >= len(self.rooms_cache):
            return
        selected = self.rooms_cache[idx]
        room_name = selected['room']
        self.view.set_room_title(f"{room_name} (Peer)")
        if room_name not in self.joined_rooms:
            self.joined_rooms.append(room_name)
            self.view.set_joined_rooms(self.joined_rooms)
        self.current_room = room_name
        self.session.set_active_room(room_name)
        asyncio.run_coroutine_threadsafe(self.session.peer_join(selected, nick), self.loop)
        # Remove from available list after join
        self._on_refresh_rooms()

    def _on_switch_room(self, idx: int):
        if idx < 0 or idx >= len(self.joined_rooms):
            return
        room_name = self.joined_rooms[idx]
        self.current_room = room_name
        self.session.set_active_room(room_name)
        self.view.set_room_title(room_name)
        lines = self.room_messages.get(room_name, [])
        self.view.set_chat(lines)
        self.view.set_members(self.room_members.get(room_name, []))

    def _on_refresh_rooms(self):
        rooms = self.session.get_discovered_rooms()
        self.rooms_cache = rooms
        self.view.set_available_rooms(rooms)

    # Bus handlers
    def _on_message(self, m: Dict[str, Any]):
        room = m.get('room')
        line = f"[{time.strftime('%H:%M:%S', time.localtime(m['ts']))}] {m['nick']}: {m['text']}"
        self.room_messages.setdefault(room, []).append(line)
        if self.current_room == room:
            self.root.after(0, lambda: self.view.add_message(line))

    def _on_presence(self, payload: Dict[str, Any]):
        room = payload.get('room')
        members = payload.get('members', [])
        self.room_members[room] = members
        if self.current_room == room:
            self.root.after(0, lambda: self.view.set_members(members))

    def _on_discovery_rooms(self, rooms: List[Dict[str, Any]]):
        self.rooms_cache = rooms  # UI only updates on manual refresh

    def _on_system_info(self, payload: Dict[str, Any]):
        self.root.after(0, lambda: self.view.add_message(f"* {payload.get('text')}"))

    def run(self):
        self.root.mainloop()

def main():
    print(__name__)
    app = TkApp()
    app.run()



