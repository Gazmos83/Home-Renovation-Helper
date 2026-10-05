"""service-foundation: environment-driven configuration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import ConfigurationError, Settings, load_settings, redact_dsn

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _settings(**overrides: object) -> Settings:
    base = {
        "database_url": "postgresql://u:p@localhost:5432/d",
        "openrouter_api_key": "sk-or-test",
        "cors_origins": "http://localhost:5173",
        "owner_email": "owner@example.com",
        "owner_password": "a-good-password",
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


def test_all_required_values_present(settings: Settings) -> None:
    assert settings.database_url is not None
    assert settings.cors_origins == ("http://localhost:5173",)
    assert str(settings.owner_email) == "owner@example.com"


def test_missing_required_values_name_the_variables(clean_env: None) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings(_env_file=None)
    message = str(caught.value)
    assert "DATABASE_URL" in message
    assert "OPENROUTER_API_KEY" in message
    assert "OWNER_EMAIL" in message
    assert "OWNER_PASSWORD" in message


def test_missing_database_url_is_named(clean_env: None) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings(
            openrouter_api_key="sk-or-test",
            cors_origins="http://localhost:5173",
            owner_email="owner@example.com",
            owner_password="a-good-password",
            _env_file=None,
        )
    assert "DATABASE_URL" in str(caught.value)


def test_several_values_wrong_at_once_are_all_named(clean_env: None) -> None:
    """The gateway credential unset and the origin list empty: one error, both
    variables named."""
    with pytest.raises(ConfigurationError) as caught:
        load_settings(
            database_url="postgresql://u:p@localhost:5432/d",
            cors_origins="",
            owner_email="owner@example.com",
            owner_password="a-good-password",
            _env_file=None,
        )
    message = str(caught.value)
    assert "OPENROUTER_API_KEY" in message
    assert "CORS_ORIGINS" in message


def test_malformed_database_url_is_rejected(clean_env: None) -> None:
    with pytest.raises(ValidationError):
        _settings(database_url="not-a-url")


def test_empty_origin_list_is_rejected(clean_env: None) -> None:
    with pytest.raises(Exception) as caught:
        _settings(cors_origins="")
    assert "origin" in str(caught.value)


def test_wildcard_origin_is_rejected(clean_env: None) -> None:
    with pytest.raises(Exception) as caught:
        _settings(cors_origins="*")
    assert "wildcard" in str(caught.value)


def test_a_weak_owner_password_is_rejected_by_name(clean_env: None) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings(
            database_url="postgresql://u:p@localhost:5432/d",
            openrouter_api_key="sk-or-test",
            cors_origins="http://localhost:5173",
            owner_email="owner@example.com",
            owner_password="short",
            _env_file=None,
        )
    assert "OWNER_PASSWORD" in str(caught.value)


def test_redact_dsn_removes_the_password() -> None:
    redacted = redact_dsn(
        _settings(
            database_url="postgresql://alice:sup3rs3cret@db.example:5432/prod"
        ).database_url
    )
    assert "sup3rs3cret" not in redacted
    assert "alice" in redacted
    assert "db.example" in redacted


def test_safe_summary_leaks_no_secret() -> None:
    configured = _settings(
        database_url="postgresql://alice:sup3rs3cret@db.example:5432/prod",
        openrouter_api_key="sk-or-v1-deadbeef",
        owner_password="hunter2hunter2",
        langfuse_host="https://cloud.langfuse.com",
        langfuse_public_key="pk-lf-public-c0ffee",
        langfuse_secret_key="sk-lf-secret-facade",
    )
    rendered = repr(configured.safe_summary())
    for secret in ("sup3rs3cret", "hunter2hunter2", "sk-or-v1-deadbeef", "c0ffee", "facade"):
        assert secret not in rendered
    # The host is not a secret and is useful in a startup line.
    assert "cloud.langfuse.com" in rendered
    assert configured.safe_summary()["owner_email"] == "owner@example.com"


def test_process_refuses_to_start_without_configuration(tmp_path: Path) -> None:
    """The spec's startup scenario: non-zero exit, variable named, no serving."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.config import load_settings; load_settings(_env_file=None)",
        ],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(BACKEND_ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "DATABASE_URL" in completed.stderr


def test_dev_panel_defaults_off(settings: Settings) -> None:
    assert settings.dev_panel_enabled is False
    assert settings.safe_summary()["dev_panel_enabled"] is False


def test_gateway_probe_defaults_on(clean_env: None) -> None:
    assert _settings().gateway_probe_enabled is True


def test_session_cookie_secure_defaults_off(settings: Settings) -> None:
    assert settings.session_cookie_secure is False


def test_tracing_is_off_unless_every_langfuse_value_is_present(clean_env: None) -> None:
    assert _settings().tracing_enabled is False
    assert _settings(langfuse_host="https://cloud.langfuse.com").tracing_enabled is False
    partial = _settings(
        langfuse_host="https://cloud.langfuse.com", langfuse_public_key="pk-lf-1"
    )
    assert partial.tracing_enabled is False
    assert partial.safe_summary()["tracing"] == "off"


def test_tracing_is_on_when_all_three_are_set(clean_env: None) -> None:
    configured = _settings(
        langfuse_host="https://cloud.langfuse.com",
        langfuse_public_key="pk-lf-1",
        langfuse_secret_key="sk-lf-1",
    )
    assert configured.tracing_enabled is True
    assert configured.safe_summary()["tracing"] == "on"


def test_a_blank_langfuse_value_counts_as_absent(clean_env: None) -> None:
    configured = _settings(
        langfuse_host="https://cloud.langfuse.com",
        langfuse_public_key="pk-lf-1",
        langfuse_secret_key="   ",
    )
    assert configured.tracing_enabled is False


def test_langfuses_own_base_url_name_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.invalid")
    configured = _settings(langfuse_public_key="pk-lf-1", langfuse_secret_key="sk-lf-1")
    assert configured.langfuse_host == "https://cloud.langfuse.invalid"
    assert configured.tracing_enabled is True


# --- Blender and renders ----------------------------------------------------------


def test_blender_defaults(clean_env: None) -> None:
    from app.config import DEFAULT_BLENDER_BIN, DEFAULT_RENDER_ROOT

    configured = _settings()
    assert configured.blender_bin == DEFAULT_BLENDER_BIN
    assert configured.blender_timeout_seconds == 600
    assert configured.render_root == DEFAULT_RENDER_ROOT


def test_a_non_positive_timeout_is_rejected_by_name(clean_env: None) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings(
            database_url="postgresql://u:p@localhost:5432/d",
            openrouter_api_key="sk-or-test",
            cors_origins="http://localhost:5173",
            owner_email="owner@example.com",
            owner_password="a-good-password",
            blender_timeout_seconds=0,
            _env_file=None,
        )
    assert "BLENDER_TIMEOUT_SECONDS" in str(caught.value)


def test_generation_needs_an_executable_binary(clean_env: None, tmp_path: Path) -> None:
    missing = _settings(blender_bin=tmp_path / "nope")
    assert missing.generation_enabled is False
    assert missing.safe_summary()["generation"] == "off"

    plain = tmp_path / "blender"
    plain.write_text("#!/bin/sh\n")
    assert _settings(blender_bin=plain).generation_enabled is False

    plain.chmod(0o755)
    ready = _settings(blender_bin=plain)
    assert ready.generation_enabled is True
    assert ready.safe_summary()["generation"] == "on"
    assert ready.safe_summary()["blender_bin"] == str(plain)
