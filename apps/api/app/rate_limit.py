from collections import defaultdict, deque
from time import time

from fastapi import HTTPException, Request, status

from .config import settings

WINDOW_SEC = 60
_requests: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
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
