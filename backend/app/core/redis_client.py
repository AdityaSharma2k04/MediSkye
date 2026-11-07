import time
from typing import Any, Optional


class MockRedis:
    """
    TTL-aware bounded in-memory MockRedis implementation.
    Evicts expired keys on access, bounds max size to 4096 keys,
    and supports get, set, setex, and delete while preserving
    direct .store access for tests.
    """

    MAX_KEYS = 4096

    def __init__(self):
        self.store: dict[str, Any] = {}
        self.expiry: dict[str, float] = {}

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, exp in self.expiry.items() if exp is not None and exp <= now]
        for k in expired:
            self.store.pop(k, None)
            self.expiry.pop(k, None)

    def _ensure_capacity(self) -> None:
        self._evict_expired()
        if len(self.store) >= self.MAX_KEYS:
            oldest_key = next(iter(self.store))
            self.store.pop(oldest_key, None)
            self.expiry.pop(oldest_key, None)

    async def get(self, key: str) -> Optional[Any]:
        self._evict_expired()
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        self._ensure_capacity()
        self.store[key] = value
        if ex is not None:
            self.expiry[key] = time.monotonic() + float(ex)
        else:
            self.expiry.pop(key, None)
        return True

    async def setex(self, key: str, time_sec: int, value: Any) -> bool:
        self._ensure_capacity()
        self.store[key] = value
        self.expiry[key] = time.monotonic() + float(time_sec)
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.store:
                self.store.pop(k, None)
                self.expiry.pop(k, None)
                count += 1
        return count


redis_client = MockRedis()
