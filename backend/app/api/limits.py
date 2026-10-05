"""Sign-in rate limiting (owner-auth).

A fixed-window counter per subject, held in process. The foundation's schema has
no counters table (the four tables are owner, session, operator settings and
usage), and a single-owner service running one process needs no cross-process
counter, so the window lives on `app.state.auth_rate_limiter`. A new counter is
created per application, so one test's attempts never bleed into the next.

The subject is always server-resolved: the submitted email (hashed) and the
network address. A body field can never name the subject, and the refusal is
the same whether or not the email exists.
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import Final

from fastapi import HTTPException, Request, status

RATE_LIMITED: Final = "rate_limited"
REASON: Final = "too many sign-in attempts; wait and try again"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _network_key(request: Request) -> str:
    host = request.client.host if request.client is not None else "unknown"
    return "net:" + _digest(host)


class RateLimiter:
    """A fixed-window counter keyed by subject. `limit <= 0` disables it."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._counters: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    def _hit(self, key: str, now: float) -> bool:
        """Count one attempt against `key`; return True when it is over the limit."""
        window_start, count = self._counters[key]
        if now - window_start >= self._window:
            window_start, count = now, 0
        count += 1
        self._counters[key] = (window_start, count)
        return count > self._limit

    def check(self, subjects: list[str]) -> None:
        """Count this attempt against every subject; refuse if any is over."""
        if self._limit <= 0:
            return
        now = time.monotonic()
        over = False
        # Every subject is counted, so the refusal does not reveal which one
        # tripped (and the counts stay honest for a later attempt).
        for subject in subjects:
            if self._hit(subject, now):
                over = True
        if over:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"failure_class": RATE_LIMITED, "reason": REASON},
                headers={"Retry-After": str(self._window)},
            )


def check_auth(request: Request, email: str) -> None:
    """Limit sign-in attempts per email and per network, without saying whether
    the email exists: the same subjects are counted for every submission."""
    limiter: RateLimiter = request.app.state.auth_rate_limiter
    normalised = email.strip().lower()
    limiter.check(["email:" + _digest(normalised), _network_key(request)])
