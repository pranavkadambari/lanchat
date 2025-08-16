import asyncio, json, struct
from typing import Callable, Optional, Dict, Any

HEADER = struct.Struct('!I')

def pack_frame(obj: Dict[str, Any]) -> bytes:
    data = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    return HEADER.pack(len(data)) + data

async def read_exactly(reader: asyncio.StreamReader, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = await reader.read(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading frame")
        buf += chunk
    return buf

async def read_frame(reader: asyncio.StreamReader) -> Dict[str, Any]:
    header = await read_exactly(reader, HEADER.size)
    (length,) = HEADER.unpack(header)
    data = await read_exactly(reader, length)
    return json.loads(data.decode('utf-8'))

class TCPServer:
    def __init__(self, host: str, port: int, on_client: Callable[[asyncio.StreamReader, asyncio.StreamWriter], None]):
        self.host = host
        self.port = port
        self.on_client = on_client
        self.server: Optional[asyncio.base_events.Server] = None

    async def start(self):
        try:
            self.server = await asyncio.start_server(self.on_client, self.host, self.port)
        except OSError:
            self.server = await asyncio.start_server(self.on_client, self.host, 0)
        addr = ', '.join(str(sock.getsockname()) for sock in self.server.sockets)
        print(f"[TCPServer] Listening on {addr}")

    def bound_port(self) -> int:
        if not self.server or not self.server.sockets:
            return self.port
        return self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print("[TCPServer] Stopped")

class TCPClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print(f"[TCPClient] Connected to {self.host}:{self.port}")

    async def send(self, obj):
        if not self.writer:
            raise ConnectionError("Not connected")
        self.writer.write(pack_frame(obj))
        await self.writer.drain()

    async def recv(self) -> Dict[str, Any]:
        if not self.reader:
            raise ConnectionError("Not connected")
        return await read_frame(self.reader)

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            print("[TCPClient] Closed")
