# In-memory per-IP sliding window for MEGA/PikPak login POSTs (F-007).

from __future__ import annotations

import time


class LoginRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("Too many login attempts")


class LoginRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def check(self, ip: str, max_attempts: int, window_s: float) -> None:
        now = time.monotonic()
        hits = [t for t in self._hits.get(ip, []) if now - t < window_s]
        if len(hits) >= max_attempts:
            retry_after = max(1, int(window_s - (now - hits[0]) + 0.999))
            self._hits[ip] = hits
            raise LoginRateLimited(retry_after=retry_after)
        hits.append(now)
        self._hits[ip] = hits


login_rate_limiter = LoginRateLimiter()
