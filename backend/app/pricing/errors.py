"""The two ways a pricing operation can be refused, with a reason safe to show."""

from __future__ import annotations


class NotFound(LookupError):
    """The entry, snapshot or record asked for does not exist."""


class Refused(ValueError):
    """The request is understood but refused; the message says why."""


class NotApproved(Refused):
    """Refused because the version has not been approved by the owner."""


class Conflict(Refused):
    """Refused because of the current state (a duplicate key, an entry still in use)."""
