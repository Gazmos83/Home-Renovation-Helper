"""Pending `final` approvals over HTTP (render-guard design decision 2).

The first request for a `final` render shows the estimate and gets a token; a
second request carrying that token and "yes" runs it. Tokens live in memory,
are bound to one package version and request, expire after 15 minutes
(assumption, TODO(user)) and are single-use. A restart drops them: the owner
asks again and sees the estimate again; nothing was started.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

TTL_SECONDS: Final = 15 * 60


class ApprovalError(Exception):
    """A token that cannot be used; `reason` is safe to show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class PendingApproval:
    package_id: str
    version: int
    kind: str
    tier: str
    room: bool
    scene_document: dict[str, Any] | None
    expires_at: float
    record: str = "piece"
    # What the owner was quoted: where it runs and how long (seconds, as shown).
    target: str = "local"
    estimate_seconds: float | None = None

    def refuse_if_changed(self, target: str, estimate_seconds: float) -> None:
        """A "yes" covers only the quote shown: refuse another target or a longer estimate."""
        if target != self.target:
            raise ApprovalError(
                f"the render would now run on the {_PLACE[target]} instead of the {_PLACE[self.target]}; "
                "ask for it again to see the new estimate"
            )
        if self.estimate_seconds is not None and round(estimate_seconds, 1) > self.estimate_seconds:
            raise ApprovalError("the render's estimate has grown since it was shown; ask for it again")


_PLACE: Final = {"local": "laptop", "remote": "render server"}


class ApprovalStore:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic, ttl: float = TTL_SECONDS):
        self._clock = clock
        self._ttl = ttl
        self._lock = threading.Lock()
        self._pending: dict[str, PendingApproval] = {}

    def issue(
        self, *, package_id: str, version: int, kind: str, tier: str, room: bool,
        scene_document: dict[str, Any] | None, record: str = "piece",
        target: str = "local", estimate_seconds: float | None = None,
    ) -> str:
        token = secrets.token_urlsafe(24)
        pending = PendingApproval(
            package_id, version, kind, tier, room, scene_document, self._clock() + self._ttl, record,
            target, None if estimate_seconds is None else round(estimate_seconds, 1),
        )
        with self._lock:
            self._purge()
            self._pending[token] = pending
        return token

    def take(
        self, token: str, *, package_id: str, version: int, record: str = "piece"
    ) -> PendingApproval:
        """Use a token once. A token for another package version is refused and
        left alone; an expired or unknown one is refused."""
        with self._lock:
            self._purge()
            pending = self._pending.get(token)
            if pending is None:
                raise ApprovalError("the approval token is unknown or has expired")
            if (pending.package_id, pending.version, pending.record) != (package_id, version, record):
                raise ApprovalError("the approval token was issued for a different package version")
            del self._pending[token]
            return pending

    def discard(self, token: str) -> None:
        with self._lock:
            self._pending.pop(token, None)

    def _purge(self) -> None:
        now = self._clock()
        for key in [k for k, p in self._pending.items() if p.expires_at <= now]:
            del self._pending[key]
