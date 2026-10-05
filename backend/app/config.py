"""Environment-driven configuration.

Every deployment-specific value comes from the process environment. There are
no hardcoded fallbacks for required values: a missing or malformed one stops
startup rather than letting the service run in a half-configured state
(service-foundation).
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Annotated, Any, Final

from pydantic import (
    AliasChoices,
    EmailStr,
    Field,
    PostgresDsn,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_REDACTED: Final = "***"

# The shortest initial owner password accepted. The same rule lives in
# `auth/passwords.hash_password`, but enforcing it here means a weak
# `OWNER_PASSWORD` stops startup by name rather than surfacing later.
MIN_OWNER_PASSWORD_LENGTH: Final = 10

# The canonical .env lives at the repo root (CLAUDE.md §2), so it is resolved
# absolutely rather than relative to whatever directory the process started in.
REPO_ROOT: Final = Path(__file__).resolve().parents[2]

# The pinned Blender (CLAUDE.md §2). Overridable with BLENDER_BIN.
DEFAULT_BLENDER_BIN: Final = Path(
    "/home/pingu/Applications/blender-5.2.1-linux-x64/blender"
)
DEFAULT_RENDER_ROOT: Final = REPO_ROOT / "docs" / "renders"


class ConfigurationError(RuntimeError):
    """The environment cannot produce a usable configuration."""


def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return value


def redact_dsn(dsn: PostgresDsn | None) -> str:
    """Render a connection URL with every password replaced.

    Rebuilt from parts rather than string-substituted so a password can never
    survive by being absent from the pattern we expected it to match. Postgres
    DSNs may carry several hosts, each with its own credentials, so all of them
    are walked rather than just the first.
    """
    if dsn is None:
        return ""
    authorities = []
    for host in dsn.hosts():
        userinfo = ""
        if host.get("username"):
            userinfo = str(host["username"])
            if host.get("password"):
                userinfo = f"{userinfo}:{_REDACTED}"
            userinfo = f"{userinfo}@"
        port = f":{host['port']}" if host.get("port") else ""
        authorities.append(f"{userinfo}{host.get('host') or ''}{port}")
    return f"{dsn.scheme}://{','.join(authorities)}{dsn.path or ''}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn
    test_database_url: PostgresDsn | None = None

    # --- Model gateway -------------------------------------------------------
    # The single gateway to every model (CLAUDE.md §2). Required: it is the only
    # route to a model, so starting without it would mean failing at the first
    # turn instead of at startup.
    openrouter_api_key: SecretStr

    # --- Browser origins -----------------------------------------------------
    cors_origins: Annotated[tuple[str, ...], NoDecode]

    # --- Owner account -------------------------------------------------------
    # The single owner, created from these on first start (owner-auth).
    owner_email: EmailStr
    owner_password: SecretStr

    # --- Developer panel -----------------------------------------------------
    # When false, every /admin route answers 404 so the homeowner surface shows
    # no sign of it (owner-auth, design.md decision 2).
    dev_panel_enabled: bool = False

    # --- Startup gateway probe -----------------------------------------------
    # One minimal call per routed slug at startup. On by default; off for
    # offline boots and tests (llm-gateway, design.md decision 5).
    gateway_probe_enabled: bool = True

    # --- Sessions ------------------------------------------------------------
    # Whether the session cookie carries `Secure`. Off for the loopback dev
    # setup, where the frontend and backend both serve plain HTTP; a deployment
    # behind HTTPS must turn this on.
    session_cookie_secure: bool = False
    # How long a sign-in lasts. Slides forward as the session is used.
    auth_session_days: int = 14
    # Sign-in attempts per address and per network within the window.
    auth_rate_limit: int = 10
    auth_rate_limit_window_seconds: int = 60

    # --- Blender and renders -------------------------------------------------
    # Neither is checked at startup: a host without Blender must still boot and
    # serve records. Only starting a Blender process is refused
    # (`generation_enabled`, render-guard design decision 11).
    blender_bin: Path = DEFAULT_BLENDER_BIN
    blender_timeout_seconds: int = 600
    render_root: Path = DEFAULT_RENDER_ROOT

    # --- Tracing (optional) --------------------------------------------------
    # Langfuse. All three must be set for tracing to run at all; with any of them
    # absent the service starts and answers exactly as before. An unreachable
    # Langfuse never delays or fails a turn (service-foundation).
    # `LANGFUSE_BASE_URL` is the name Langfuse's own documentation now uses.
    langfuse_host: str | None = Field(
        default=None, validation_alias=AliasChoices("langfuse_host", "langfuse_base_url")
    )
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    # Separates development traces from a deployment's in the same project.
    langfuse_tracing_environment: str = Field(
        default="development", pattern=r"^[a-z0-9_-]{1,40}$"
    )

    @property
    def tracing_enabled(self) -> bool:
        """True only when every Langfuse value is present and non-blank."""
        return bool(
            (self.langfuse_host or "").strip()
            and (self.langfuse_public_key and self.langfuse_public_key.get_secret_value().strip())
            and (self.langfuse_secret_key and self.langfuse_secret_key.get_secret_value().strip())
        )

    @property
    def generation_enabled(self) -> bool:
        """Whether starting a Blender process is possible on this host now."""
        return self.blender_bin.is_file() and os.access(self.blender_bin, os.X_OK)

    @field_validator("blender_timeout_seconds", mode="after")
    @classmethod
    def _reject_non_positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("blender_timeout_seconds must be positive")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _accept_csv(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("cors_origins", mode="after")
    @classmethod
    def _reject_wildcard_origin(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one origin is required")
        if "*" in value:
            raise ValueError(
                "wildcard origin '*' is not allowed: credentialed requests require "
                "explicit origins"
            )
        return value

    @field_validator("owner_password", mode="after")
    @classmethod
    def _reject_weak_owner_password(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_OWNER_PASSWORD_LENGTH:
            raise ValueError(
                f"the owner password must be at least {MIN_OWNER_PASSWORD_LENGTH} characters"
            )
        return value

    def safe_summary(self) -> dict[str, Any]:
        """A log-safe view: no gateway key, no owner password, no Langfuse keys,
        no database password."""
        return {
            "database_url": redact_dsn(self.database_url),
            "test_database_url": redact_dsn(self.test_database_url),
            "cors_origins": list(self.cors_origins),
            "openrouter_api_key": _REDACTED,
            "owner_email": self.owner_email,
            "owner_password": _REDACTED,
            "dev_panel_enabled": self.dev_panel_enabled,
            "gateway_probe_enabled": self.gateway_probe_enabled,
            "session_cookie_secure": self.session_cookie_secure,
            "auth_session_days": self.auth_session_days,
            "tracing": "on" if self.tracing_enabled else "off",
            "blender_bin": str(self.blender_bin),
            "blender_timeout_seconds": self.blender_timeout_seconds,
            "render_root": str(self.render_root),
            "generation": "on" if self.generation_enabled else "off",
            "langfuse_host": self.langfuse_host,
            "langfuse_tracing_environment": self.langfuse_tracing_environment,
            "langfuse_public_key": _REDACTED,
            "langfuse_secret_key": _REDACTED,
        }


def _describe(error: ValidationError) -> str:
    lines = []
    for detail in error.errors():
        location = detail["loc"]
        name = str(location[0]).upper() if location else "(root)"
        lines.append(f"  {name}: {detail['msg']}")
    return "Invalid configuration:\n" + "\n".join(lines)


def load_settings(**overrides: Any) -> Settings:
    """Build settings, converting pydantic's error into one naming the variables."""
    try:
        return Settings(**overrides)
    except ValidationError as error:
        raise ConfigurationError(_describe(error)) from error


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
