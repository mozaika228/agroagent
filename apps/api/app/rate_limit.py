from collections import defaultdict, deque
from time import time

from fastapi import HTTPException, Request, status

from .config import settings

try:
    from redis import Redis
    from redis.exceptions import RedisError
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore[assignment]

    class RedisError(Exception):
        pass

WINDOW_SEC = 60
_requests: dict[str, deque[float]] = defaultdict(deque)
_redis_client = Redis.from_url(settings.redis_url) if (Redis and settings.redis_url) else None


def _check_rate_limit_memory(ip: str) -> None:
    now = time()
    q = _requests[ip]
    while q and (now - q[0]) > WINDOW_SEC:
        q.popleft()
    if len(q) >= settings.max_requests_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
        )
    q.append(now)


def _check_rate_limit_redis(ip: str) -> None:
    if _redis_client is None:
        _check_rate_limit_memory(ip)
        return

    key = f"rate_limit:{ip}:{int(time() // WINDOW_SEC)}"
    try:
        count = _redis_client.incr(key)
        if count == 1:
            _redis_client.expire(key, WINDOW_SEC + 2)
        if count > settings.max_requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
            )
    except RedisError:
        _check_rate_limit_memory(ip)


def check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit_redis(ip)
