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


# --- retail sources (pricing-researcher) ----------------------------------------------


def _retail_settings(**overrides):
    from app.config import Settings

    base = {
        "database_url": "postgresql://u:p@h/d",
        "openrouter_api_key": "k",
        "cors_origins": "http://localhost:5173",
        "owner_email": "owner@example.com",
        "owner_password": "an-initial-owner-password",
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})


def test_toom_is_the_only_default_retail_source() -> None:
    settings = _retail_settings()
    assert settings.retail_sources == frozenset({"toom"})
    assert settings.source_enabled("toom") and not settings.source_enabled("bauhaus")


def test_an_unknown_retail_source_fails_startup_naming_it() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as caught:
        _retail_settings(retail_sources="toom,bauhaus")
    assert "bauhaus" in str(caught.value)


def test_the_crawler_identity_falls_back_to_the_owners_email() -> None:
    assert _retail_settings().crawler_identity == "owner@example.com"
    assert _retail_settings(crawler_contact="https://example.org/contact").crawler_identity == "https://example.org/contact"


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_loopback_hosts_are_accepted(host):
    assert _settings(blender_live_host=host).blender_live_host == host


@pytest.mark.parametrize("host", ["192.168.1.20", "example.com", "0.0.0.0"])
def test_a_non_loopback_host_is_refused_naming_the_setting(host):
    with pytest.raises(ValueError, match="blender_live_host"):
        _settings(blender_live_host=host)


# --- render offload (render-offload) --------------------------------------------------------------


@pytest.fixture
def offload_files(tmp_path: Path) -> dict[str, object]:
    key = tmp_path / "id_ed25519"
    known = tmp_path / "known_hosts"
    key.write_text("PRIVATE KEY BYTES", encoding="utf-8")
    known.write_text("gpu.example.org ssh-ed25519 AAAA", encoding="utf-8")
    return {
        "render_offload_host": "gpu.example.org",
        "render_offload_user": "render",
        "render_offload_key_path": key,
        "render_offload_known_hosts_path": known,
        "render_offload_blender": "/opt/blender-5.2.1/blender",
    }


def test_offload_is_off_by_default() -> None:
    settings = _settings()
    assert settings.render_offload_configured is False
    assert settings.safe_summary()["render_offload"] == "off"


def test_offload_is_off_when_any_connection_value_is_missing(offload_files: dict) -> None:
    for missing in offload_files:
        values = {k: v for k, v in offload_files.items() if k != missing}
        assert _settings(**values).render_offload_configured is False, missing


def test_blank_values_count_as_unset(offload_files: dict) -> None:
    assert _settings(**{**offload_files, "render_offload_host": "  "}).render_offload_configured is False


def test_a_configured_offload_is_summarised_without_the_key(offload_files: dict) -> None:
    settings = _settings(**offload_files)
    assert settings.render_offload_configured is True
    summary = settings.safe_summary()
    assert summary["render_offload"] == "render@gpu.example.org:22"
    assert "id_ed25519" not in repr(summary) and "PRIVATE" not in repr(summary)
    assert settings.render_offload_cycles_device == "OPTIX"


def test_a_missing_key_file_fails_naming_the_setting(offload_files: dict, tmp_path: Path) -> None:
    offload_files["render_offload_key_path"] = tmp_path / "nope"
    with pytest.raises(ValidationError, match="RENDER_OFFLOAD_KEY_PATH"):
        _settings(**offload_files)


def test_a_missing_known_hosts_file_fails_naming_the_setting(offload_files: dict, tmp_path: Path) -> None:
    offload_files["render_offload_known_hosts_path"] = tmp_path / "nope"
    with pytest.raises(ValidationError, match="RENDER_OFFLOAD_KNOWN_HOSTS_PATH"):
        _settings(**offload_files)


def test_load_settings_names_the_variable(offload_files: dict, tmp_path: Path, clean_env: None) -> None:
    offload_files["render_offload_key_path"] = tmp_path / "nope"
    with pytest.raises(ConfigurationError, match="RENDER_OFFLOAD_KEY_PATH"):
        load_settings(
            database_url="postgresql://u:p@localhost:5432/d", openrouter_api_key="sk-or-test",
            cors_origins="http://localhost:5173", owner_email="owner@example.com",
            owner_password="a-good-password", _env_file=None, **offload_files,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("render_offload_cycles_device", "METAL"),
        ("render_offload_blender", "blender"),
        ("render_offload_blender", "/opt/blender; rm -rf /"),
        ("render_offload_blender", "/opt/blen der/blender"),
        ("render_offload_host", "gpu.example.org; id"),
        ("render_offload_user", "root; id"),
        ("render_offload_port", 0),
        ("render_offload_port", 70000),
    ],
)
def test_an_unsafe_or_unknown_offload_value_is_refused_naming_it(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match=field):
        _settings(**{field: value})


@pytest.mark.parametrize("device", ["OPTIX", "CUDA", "HIP"])
def test_the_known_gpu_devices_are_accepted(device: str) -> None:
    assert _settings(render_offload_cycles_device=device).render_offload_cycles_device == device


def test_the_design_upload_cap_defaults_to_256_kib_and_must_be_positive() -> None:
    import pytest
    from pydantic import ValidationError

    assert _settings().upload_max_design_bytes == 256 * 1024
    with pytest.raises(ValidationError) as caught:
        _settings(upload_max_design_bytes=0)
    assert "upload limits must be positive" in str(caught.value)


def test_the_model_library_limits_have_the_decided_defaults_and_refuse_zero() -> None:
    import pytest
    from pydantic import ValidationError

    settings = _settings()
    assert settings.model_max_bytes == 50 * 1024 * 1024
    assert settings.model_zip_max_entries == 200
    assert settings.model_zip_max_unpacked_bytes == 200 * 1024 * 1024
    assert settings.model_max_triangles == 500_000
    assert settings.composition_max_items == 30
    for field in ("model_max_bytes", "model_zip_max_entries", "model_zip_max_unpacked_bytes",
                  "model_max_triangles", "composition_max_items"):
        with pytest.raises(ValidationError):
            _settings(**{field: 0})


def test_the_note_upload_cap_defaults_to_256_kib_and_must_be_positive() -> None:
    import pytest
    from pydantic import ValidationError

    assert _settings().upload_max_note_bytes == 256 * 1024
    with pytest.raises(ValidationError) as caught:
        _settings(upload_max_note_bytes=0)
    assert "upload limits must be positive" in str(caught.value)
