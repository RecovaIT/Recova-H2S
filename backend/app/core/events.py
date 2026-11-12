"""Thread-safe + asyncio-aware real-time event broker for SSE & WebSocket streams.

Background workers and synchronous FastAPI services publish pipeline step events,
emergency alerts, and referral notifications keyed by `organization_id` (plus
optional `run:<run_id>` channels). Connected SSE/WebSocket clients receive events
with zero polling, scoped strictly to their authenticated organisation.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Subscription:
    channel: str
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=256))


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, list[Subscription]] = defaultdict(list)

    def subscribe(self, channel: str, loop: asyncio.AbstractEventLoop) -> Subscription:
        sub = Subscription(channel=channel, loop=loop)
        with self._lock:
            self._subs[channel].append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            lst = self._subs.get(sub.channel)
            if lst and sub in lst:
                lst.remove(sub)
            if lst is not None and not lst:
                self._subs.pop(sub.channel, None)

    def publish(self, channel: str, event_type: str, data: dict[str, Any]) -> None:
        payload = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        with self._lock:
            targets = list(self._subs.get(channel, ()))
        for sub in targets:
            try:
                if sub.loop.is_closed():
                    continue
                sub.loop.call_soon_threadsafe(self._put_nonblocking, sub.queue, payload)
            except RuntimeError:
                pass

    @staticmethod
    def _put_nonblocking(q: asyncio.Queue[dict[str, Any]], item: dict[str, Any]) -> None:
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def publish_org(self, organization_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        self.publish(f"org:{organization_id}", event_type, data)

    def publish_run(self, organization_id: uuid.UUID, run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        enriched = {"run_id": str(run_id), **data}
        self.publish(f"org:{organization_id}", event_type, enriched)
        self.publish(f"run:{organization_id}:{run_id}", event_type, enriched)


event_bus = EventBus()


def format_sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"
