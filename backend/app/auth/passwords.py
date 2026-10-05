"""Password hashing and verification (owner-auth).

argon2 through `pwdlib`, whose recommended parameters are memory-hard: a leaked
`users` table does not yield passwords at any useful rate. The plain password
exists only as a local argument here and is never stored, logged or returned.

`verify_password` deliberately does the same work whether or not the email
exists — see `DUMMY_HASH`.
"""

from __future__ import annotations

from typing import Final

from pwdlib import PasswordHash

MIN_PASSWORD_LENGTH: Final = 10

_hasher: Final = PasswordHash.recommended()


class WeakPassword(ValueError):
    """The password is too short to accept. Carries a message safe to show."""

    def __init__(self) -> None:
        super().__init__(
            f"the password must be at least {MIN_PASSWORD_LENGTH} characters"
        )


def hash_password(password: str) -> str:
    """The argon2 digest to store. Raises `WeakPassword` below the minimum.

    The length rule lives here as well as in configuration so that every path
    that can create or change the owner account is held to it.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword
    return _hasher.hash(password)


# A real argon2 digest of a value no account uses. Verifying against this when
# the email is unknown keeps the work — and so the response time — the same as
# a wrong password for a known email, so timing does not tell the two apart.
DUMMY_HASH: Final = _hasher.hash("password-for-an-account-that-does-not-exist")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Whether `password` matches. A `None` hash is the unknown-email case.

    Always runs a full verification, so an unknown email costs what a wrong
    password costs.
    """
    digest = password_hash if password_hash is not None else DUMMY_HASH
    try:
        matched = _hasher.verify(password, digest)
    except Exception:  # noqa: BLE001 - a malformed stored hash is a failed login
        return False
    return matched and password_hash is not None
