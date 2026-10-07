"""Environment-driven configuration.

Every deployment-specific value comes from the process environment. There are
no hardcoded fallbacks for required values: a missing or malformed one stops
startup rather than letting the service run in a half-configured state
(service-foundation).
"""

from __future__ import annotations

import functools
import ipaddress
import os
import re
from pathlib import Path
from typing import Annotated, Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AliasChoices,
    EmailStr,
    Field,
    PostgresDsn,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_REDACTED: Final = "***"

# The Cycles GPU back ends a render server may use (render-offload).
OFFLOAD_DEVICES: Final = ("OPTIX", "CUDA", "HIP")

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
DEFAULT_UPLOAD_ROOT: Final = REPO_ROOT / "docs" / "uploads"
DEFAULT_GUIDELINE_ROOT: Final = REPO_ROOT / "docs" / "guidelines"


class ConfigurationError(RuntimeError):
    """The environment cannot produce a usable configuration."""


# The only retailer this service may read (CLAUDE.md §5a). Bauhaus, Kaufland and
# OKI are excluded, not deferred.
KNOWN_RETAIL_SOURCES: Final = frozenset({"toom"})


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

    # --- The live Blender (photoreal-detail) ----------------------------------
    # The Blender MCP addon's socket. Loopback only: the live Blender is the
    # owner's own, on this machine.
    blender_live_host: str = "127.0.0.1"
    blender_live_port: int = 9876
    blender_live_timeout_seconds: float = 120.0

    # --- Render offload (render-offload) ---------------------------------------
    # The owner's rented GPU box, reached with the system's `ssh`. Off unless host,
    # user, key, known-hosts file and remote Blender path are all set.
    render_offload_host: str | None = None
    render_offload_port: int = 22
    render_offload_user: str | None = None
    render_offload_key_path: Path | None = None
    render_offload_known_hosts_path: Path | None = None
    render_offload_blender: str | None = None
    render_offload_cycles_device: str = "OPTIX"

    # --- Uploads (blueprints and photos attached to a conversation) -----------
    upload_root: Path = DEFAULT_UPLOAD_ROOT
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_max_per_thread: int = 20
    # A design file (design-import) is read whole to be checked, so it has its own, smaller cap.
    upload_max_design_bytes: int = 256 * 1024

    # --- Model library and room compositions (room-composition) ----------------
    model_max_bytes: int = 50 * 1024 * 1024
    model_zip_max_entries: int = 200
    model_zip_max_unpacked_bytes: int = 200 * 1024 * 1024
    model_max_triangles: int = 500_000
    composition_max_items: int = 30

    # --- Guideline files (the owner's own PDFs and notes) ----------------------
    guideline_root: Path = DEFAULT_GUIDELINE_ROOT
    turn_max_images: int = 4

    # --- HTTPS plugins -------------------------------------------------------
    # Hosts an HTTPS plugin's URL may name. Empty by default: no outbound host
    # is allow-listed until the owner sets one.
    plugin_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = ()
    plugin_timeout_seconds: float = 5.0
    plugin_max_response_bytes: int = 262_144
    plugin_min_interval_seconds: float = 0.5

    # --- Retail sources and pricing (pricing-researcher) ----------------------
    retail_sources: Annotated[frozenset[str], NoDecode] = KNOWN_RETAIL_SOURCES
    # Sent in the crawler's User-Agent so a site can reach the operator; falls back to the owner's email.
    crawler_contact: str | None = None
    ingestion_page_budget: int = 50
    ingestion_min_interval_seconds: float = 1.0
    # TODO(user): the toom store whose cut services and restrictions price a cut list.
    toom_home_store: str = "berlin-friedrichshain"
    # Refreshing a price and capturing a URL each read a retailer page.
    rate_limit_price_fetch: int = 10
    rate_limit_price_fetch_window_seconds: int = 60

    # --- Token budget --------------------------------------------------------
    # The day's start for the daily token ceiling, as an IANA time zone.
    budget_timezone: str = "Europe/Berlin"

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
    def crawler_identity(self) -> str:
        """The contact the crawler's User-Agent carries: configured, else the owner's email."""
        return self.crawler_contact or str(self.owner_email)

    def source_enabled(self, source: str) -> bool:
        return source in self.retail_sources

    @property
    def generation_enabled(self) -> bool:
        """Whether starting a Blender process is possible on this host now."""
        return self.blender_bin.is_file() and os.access(self.blender_bin, os.X_OK)

    @field_validator("blender_live_host", mode="after")
    @classmethod
    def _require_loopback_live_host(cls, value: str) -> str:
        if value == "localhost":
            return value
        try:
            if ipaddress.ip_address(value).is_loopback:
                return value
        except ValueError:
            pass
        raise ValueError("blender_live_host must be a loopback address (127.0.0.1, ::1 or localhost)")

    @field_validator("blender_live_port", mode="after")
    @classmethod
    def _require_live_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("blender_live_port must be between 1 and 65535")
        return value

    @field_validator("blender_live_timeout_seconds", mode="after")
    @classmethod
    def _require_live_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("blender_live_timeout_seconds must be positive")
        return value

    @field_validator("render_offload_host", "render_offload_user", "render_offload_blender", mode="after")
    @classmethod
    def _blank_offload_value_is_unset(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("render_offload_host", mode="after")
    @classmethod
    def _offload_host_is_a_plain_name(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]{0,252}", value):
            raise ValueError("render_offload_host must be a host name or address")
        return value

    @field_validator("render_offload_user", mode="after")
    @classmethod
    def _offload_user_is_a_plain_name(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9._-]{0,31}", value):
            raise ValueError("render_offload_user must be a plain user name")
        return value

    @field_validator("render_offload_blender", mode="after")
    @classmethod
    def _offload_blender_is_a_plain_path(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"/[A-Za-z0-9._/-]{1,250}", value):
            raise ValueError(
                "render_offload_blender must be an absolute path of letters, digits and . _ - /"
            )
        return value

    @field_validator("render_offload_port", mode="after")
    @classmethod
    def _offload_port_in_range(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("render_offload_port must be between 1 and 65535")
        return value

    @field_validator("render_offload_cycles_device", mode="after")
    @classmethod
    def _offload_device_known(cls, value: str) -> str:
        if value not in OFFLOAD_DEVICES:
            raise ValueError(f"render_offload_cycles_device must be one of {', '.join(OFFLOAD_DEVICES)}")
        return value

    @property
    def render_offload_configured(self) -> bool:
        """True only when every connection value is set; otherwise every render runs locally."""
        return all(
            (
                self.render_offload_host,
                self.render_offload_user,
                self.render_offload_key_path,
                self.render_offload_known_hosts_path,
                self.render_offload_blender,
            )
        )

    @model_validator(mode="after")
    def _offload_files_exist_when_configured(self) -> Settings:
        if not self.render_offload_configured:
            return self
        for variable, path in (
            ("RENDER_OFFLOAD_KEY_PATH", self.render_offload_key_path),
            ("RENDER_OFFLOAD_KNOWN_HOSTS_PATH", self.render_offload_known_hosts_path),
        ):
            if path is None or not path.is_file() or not os.access(path, os.R_OK):
                raise ValueError(f"{variable} must be a readable file")
        return self

    @field_validator(
        "upload_max_bytes",
        "upload_max_per_thread",
        "upload_max_design_bytes",
        "turn_max_images",
        "model_max_bytes",
        "model_zip_max_entries",
        "model_zip_max_unpacked_bytes",
        "model_max_triangles",
        "composition_max_items",
        mode="after",
    )
    @classmethod
    def _reject_non_positive_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("upload limits must be positive")
        return value

    @field_validator("blender_timeout_seconds", mode="after")
    @classmethod
    def _reject_non_positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("blender_timeout_seconds must be positive")
        return value

    @field_validator("cors_origins", "plugin_allowed_hosts", "retail_sources", mode="before")
    @classmethod
    def _accept_csv(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("retail_sources", mode="after")
    @classmethod
    def _only_known_retail_sources(cls, value: frozenset[str]) -> frozenset[str]:
        names = frozenset(str(item).strip().lower() for item in value)
        unknown = sorted(names - KNOWN_RETAIL_SOURCES)
        if unknown:
            raise ValueError(
                f"unknown retail source(s): {', '.join(unknown)}; "
                f"the only permitted source is {', '.join(sorted(KNOWN_RETAIL_SOURCES))}"
            )
        return names

    @field_validator(
        "ingestion_page_budget", "rate_limit_price_fetch", "rate_limit_price_fetch_window_seconds",
        mode="after",
    )
    @classmethod
    def _reject_non_positive_ingestion_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ingestion and rate limits must be positive")
        return value

    @field_validator("plugin_allowed_hosts", mode="after")
    @classmethod
    def _lower_plugin_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(host.lower() for host in value)

    @field_validator("plugin_timeout_seconds", "plugin_max_response_bytes", mode="after")
    @classmethod
    def _reject_non_positive_plugin_limit(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("plugin limits must be positive")
        return value

    @field_validator("plugin_min_interval_seconds", mode="after")
    @classmethod
    def _reject_negative_plugin_interval(cls, value: float) -> float:
        if value < 0:
            raise ValueError("plugin_min_interval_seconds must be zero or positive")
        return value

    @field_validator("budget_timezone", mode="after")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError(f"unknown time zone {value!r}") from None
        return value

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
            "blender_live": f"{self.blender_live_host}:{self.blender_live_port}",
            "render_offload": (
                f"{self.render_offload_user}@{self.render_offload_host}:{self.render_offload_port}"
                if self.render_offload_configured
                else "off"
            ),
            "upload_root": str(self.upload_root),
            "guideline_root": str(self.guideline_root),
            "generation": "on" if self.generation_enabled else "off",
            "plugin_allowed_hosts": list(self.plugin_allowed_hosts),
            "retail_sources": sorted(self.retail_sources),
            "toom_home_store": self.toom_home_store,
            "plugin_timeout_seconds": self.plugin_timeout_seconds,
            "budget_timezone": self.budget_timezone,
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
