from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


def _get_lock(session_id: str) -> asyncio.Lock:
    lock = _SESSION_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _SESSION_LOCKS[session_id] = lock
    return lock


@asynccontextmanager
async def session_lock(session_id: str):
    lock = _get_lock(session_id)
    async with lock:
        yield
