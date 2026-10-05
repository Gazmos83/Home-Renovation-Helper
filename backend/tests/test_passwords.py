"""owner-auth: passwords are stored hashed and compared uniformly."""

from __future__ import annotations

import pytest

from app.auth.passwords import (
    DUMMY_HASH,
    MIN_PASSWORD_LENGTH,
    WeakPassword,
    hash_password,
    verify_password,
)

GOOD = "correct horse battery staple"


def test_a_hash_round_trips() -> None:
    digest = hash_password(GOOD)
    assert verify_password(GOOD, digest) is True


def test_the_hash_is_argon2_and_hides_the_password() -> None:
    digest = hash_password(GOOD)
    assert digest.startswith("$argon2")
    assert GOOD not in digest


def test_the_same_password_hashes_differently_each_time() -> None:
    assert hash_password(GOOD) != hash_password(GOOD)


def test_a_wrong_password_does_not_verify() -> None:
    assert verify_password("not it", hash_password(GOOD)) is False


@pytest.mark.parametrize("password", ["", "short", "x" * (MIN_PASSWORD_LENGTH - 1)])
def test_a_short_password_is_refused_by_name(password: str) -> None:
    with pytest.raises(WeakPassword) as caught:
        hash_password(password)
    assert str(MIN_PASSWORD_LENGTH) in str(caught.value)


def test_the_minimum_length_itself_is_accepted() -> None:
    assert verify_password("x" * MIN_PASSWORD_LENGTH, hash_password("x" * MIN_PASSWORD_LENGTH))


def test_an_unknown_email_still_runs_a_full_verification() -> None:
    assert verify_password(GOOD, None) is False
    assert DUMMY_HASH.startswith("$argon2")


def test_the_dummy_hashs_own_value_never_authenticates() -> None:
    assert verify_password("password-for-an-account-that-does-not-exist", None) is False


def test_a_malformed_stored_hash_is_a_failed_login_not_a_crash() -> None:
    assert verify_password(GOOD, "not-a-hash") is False
