import asyncio
from typing import Callable, Dict, Any, List

class MsgBus:
    def __init__(self) -> None:
        self._subs: Dict[str, List[Callable[[Any], None]]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._subs.setdefault(topic, []).append(handler)

    async def publish(self, topic: str, payload: Any) -> None:
        await self._queue.put((topic, payload))

    async def pump(self) -> None:
        while True:
            topic, payload = await self._queue.get()
            for handler in self._subs.get(topic, []):
                try:
                    handler(payload)
                except Exception as e:
                    print(f"[MsgBus] handler error on {topic}: {e}")
