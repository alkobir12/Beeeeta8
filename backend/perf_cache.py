"""
🚀 Performance Cache — TTL-based module-level cache for heavy backend reads.

Used to speed up:
- /api/customers (was: ~2.8s — heavy partner financial aggregation)
- /api/suppliers (was: ~2.5s — same)
- /api/operations (was: ~1.5s)
- Dashboard + Operations page cold loads

Single-instance only (in-process dict). Acceptable for our deployment.
Invalidate manually on writes to keep data fresh.
"""

import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple


# (cache_key) -> (timestamp_seconds, value)
_CACHE: Dict[str, Tuple[float, Any]] = {}

# Default TTL: 15 seconds — fast enough for UX, short enough to not stale on writes
DEFAULT_TTL = 15.0

# Safety cap: prevent unbounded growth if many distinct filter combinations are queried.
# At 500 entries with avg size ~30KB, total ~15MB which is fine.
_MAX_ENTRIES = 500


def _evict_if_needed() -> None:
    """Drop oldest entries when cache exceeds max size."""
    if len(_CACHE) <= _MAX_ENTRIES:
        return
    # Drop the oldest 20% (cheap LRU-ish based on insertion timestamp)
    items_sorted = sorted(_CACHE.items(), key=lambda kv: kv[1][0])
    drop_count = max(1, len(items_sorted) - int(_MAX_ENTRIES * 0.8))
    for k, _ in items_sorted[:drop_count]:
        _CACHE.pop(k, None)


def _make_key(namespace: str, *parts: Any) -> str:
    suffix = "|".join(str(p) for p in parts) if parts else "_"
    return f"{namespace}::{suffix}"


def get_cached(namespace: str, *parts: Any, ttl: float = DEFAULT_TTL) -> Optional[Any]:
    """Return cached value if it exists and is within TTL, else None."""
    key = _make_key(namespace, *parts)
    entry = _CACHE.get(key)
    if entry is None:
        return None
    ts, value = entry
    if (time.time() - ts) > ttl:
        # Expired — drop it
        _CACHE.pop(key, None)
        return None
    return value


def set_cached(namespace: str, value: Any, *parts: Any) -> None:
    """Store value in cache with current timestamp."""
    key = _make_key(namespace, *parts)
    _CACHE[key] = (time.time(), value)
    _evict_if_needed()


def invalidate(namespace: Optional[str] = None) -> None:
    """Drop all cache entries for a namespace, or clear everything if no namespace."""
    if namespace is None:
        _CACHE.clear()
        return
    prefix = f"{namespace}::"
    for k in [k for k in _CACHE.keys() if k.startswith(prefix)]:
        _CACHE.pop(k, None)


async def get_or_compute_async(
    namespace: str,
    compute: Callable[[], Awaitable[Any]],
    *parts: Any,
    ttl: float = DEFAULT_TTL,
) -> Any:
    """Convenience: returns cached value if fresh, else awaits compute() and caches it."""
    cached = get_cached(namespace, *parts, ttl=ttl)
    if cached is not None:
        return cached
    value = await compute()
    set_cached(namespace, value, *parts)
    return value


def stats() -> Dict[str, Any]:
    """Debugging helper — current cache state."""
    return {
        "entries": len(_CACHE),
        "namespaces": sorted({k.split("::", 1)[0] for k in _CACHE.keys()}),
    }
