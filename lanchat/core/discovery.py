import asyncio, json, socket, time
from typing import Callable, Dict, Any, Optional, List

BROADCAST_ADDR = '255.255.255.255'
DISCOVERY_PORT = 44888
ANNOUNCE_INTERVAL = 2.0

class DiscoveryService:
    """UDP broadcast discovery. Supports multiple concurrent announcers."""
    def __init__(self, on_announce: Callable[[Dict[str, Any]], None]):
        self.on_announce = on_announce
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, 'SO_REUSEPORT'):
            try:
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setblocking(False)
        self._running = False
        self._task_recv: Optional[asyncio.Task] = None
        self._task_send: Optional[asyncio.Task] = None
        self._suppliers: List[Callable[[], Dict[str, Any]]] = []

    async def start(self):
        loop = asyncio.get_running_loop()
        self._sock.bind(('', DISCOVERY_PORT))
        self._running = True
        self._task_recv = loop.create_task(self._recv_loop())
        self._task_send = loop.create_task(self._sender())

    async def stop(self):
        self._running = False
        if self._task_recv:
            self._task_recv.cancel()
        if self._task_send:
            self._task_send.cancel()
        try:
            self._sock.close()
        except Exception:
            pass

    async def _recv_loop(self):
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(self._sock, 65536)
                try:
                    msg = json.loads(data.decode('utf-8'))
                    if msg.get('type') == 'ANNOUNCE':
                        msg['from_addr'] = addr[0]
                        self.on_announce(msg)
                except Exception:
                    pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.05)

    async def _sender(self):
        loop = asyncio.get_running_loop()
        while self._running:
            for supplier in list(self._suppliers):
                try:
                    payload = supplier()
                    frame = json.dumps({'type': 'ANNOUNCE', **payload}).encode('utf-8')
                    await loop.sock_sendto(self._sock, frame, (BROADCAST_ADDR, DISCOVERY_PORT))
                except Exception:
                    pass
            await asyncio.sleep(ANNOUNCE_INTERVAL)

    def add_announcer(self, supplier: Callable[[], Dict[str, Any]]):
        self._suppliers.append(supplier)

    def remove_announcer(self, supplier: Callable[[], Dict[str, Any]]):
        try:
            self._suppliers.remove(supplier)
        except ValueError:
            pass
