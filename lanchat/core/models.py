from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Deque, List, Optional
from collections import deque
import time, uuid

def new_id() -> str:
    return str(uuid.uuid4())

@dataclass
class Member:
    peer_id: str
    nick: str
    addr: str
    joined_ts: float = field(default_factory=lambda: time.time())
    muted: bool = False

@dataclass
class Message:
    msg_id: str
    ts: float
    from_id: str
    nick: str
    room: str
    text: str
    mentions: List[str] = field(default_factory=list)

@dataclass
class FileMeta:
    file_id: str
    name: str
    size: int
    sha256: str
    mime: str
    total_chunks: int
    received_chunks: int = 0

@dataclass
class RoomState:
    id: str
    name: str
    enc_flag: bool
    history_limit: int = 200
    members: Dict[str, Member] = field(default_factory=dict)
    messages: Deque[Message] = field(default_factory=lambda: deque(maxlen=200))
    files: Dict[str, FileMeta] = field(default_factory=dict)
    salt: Optional[bytes] = None
    session_nonce: Optional[bytes] = None

    def set_history_limit(self, n: int):
        old = list(self.messages)
        self.messages = deque(old[-n:], maxlen=n)
        self.history_limit = n
