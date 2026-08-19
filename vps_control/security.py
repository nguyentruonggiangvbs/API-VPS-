from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from .config import settings


class SlidingWindowRateLimiter:
    def __init__(self, limit: int = 180, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        queue = self._hits[key]
        cutoff = now - self.window_seconds
        while queue and queue[0] < cutoff:
            queue.popleft()
        if len(queue) >= self.limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(self.window_seconds)},
            )
        queue.append(now)


rate_limiter = SlidingWindowRateLimiter()


def _extract_api_key(
    x_api_key: str | None,
    authorization: str | None,
) -> str:
    if x_api_key:
        return x_api_key.strip()
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    return ""


async def require_api_key(
    request: Request,
    x_api_key: Annotated[
        str | None, Header(alias="X-API-Key")
    ] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    client = request.client.host if request.client else "unknown"
    rate_limiter.check(client)

    supplied = _extract_api_key(x_api_key, authorization)
    expected = settings.api_key

    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.actor = "api-key"
    return supplied
