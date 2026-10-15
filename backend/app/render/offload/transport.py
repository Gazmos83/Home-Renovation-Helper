"""ssh and scp over the existing launcher seam (render-offload design decisions 1 and 2).

The system's OpenSSH does the connecting: key only, batch mode, the host key
pinned in the owner's known-hosts file, no agent, no password. Every call goes
through the same `Launch` the Blender processes use, so tests substitute it.

Nothing a model or the owner typed ever reaches a remote command. A command is
built only from constants, a job id this module generates, the Blender path and
device validated at startup, and the tier's integers and engine; each piece
goes through `shlex.quote`.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from app.blender.launch import Launch, LaunchResult
from app.config import Settings

CONNECT_TIMEOUT_SECONDS: Final = 10
REMOTE_ROOT: Final = "hra-render"
SSH_FAILED: Final = "the render server could not be reached"
# Pod mode (render-pod-lifecycle design decision 4): every pod has a new address and
# port but the same host key from the network volume, pinned under this name.
POD_HOST_KEY_ALIAS: Final = "hra-render-pod"


@dataclass(frozen=True, slots=True)
class OffloadConfig:
    host: str
    port: int
    user: str
    key_path: Path
    known_hosts_path: Path
    blender: str
    device: str
    host_key_alias: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> OffloadConfig | None:
        """The fixed host's connection; in pod mode a template without host or port,
        completed per pod with `for_pod`."""
        mode = settings.render_offload_mode
        if mode == "off":
            return None
        return cls(
            host=settings.render_offload_host or "",
            port=settings.render_offload_port,
            user=settings.render_offload_user or "",
            key_path=settings.render_offload_key_path or Path(),
            known_hosts_path=settings.render_offload_known_hosts_path or Path(),
            blender=settings.render_offload_blender or "",
            device=settings.render_offload_cycles_device,
            host_key_alias=POD_HOST_KEY_ALIAS if mode == "pod" else None,
        )

    def for_pod(self, host: str, port: int) -> OffloadConfig:
        return replace(self, host=host, port=port)

    @property
    def target(self) -> str:
        return f"{self.user}@{self.host}"

    @property
    def label(self) -> str:
        return f"{self.user}@{self.host}:{self.port}"


def _options(config: OffloadConfig) -> list[str]:
    """Key only, never a prompt, the pinned host key, no agent identities."""
    alias = ["-o", f"HostKeyAlias={config.host_key_alias}"] if config.host_key_alias else []
    return [
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={config.known_hosts_path}",
        *alias,
        "-o", "IdentitiesOnly=yes",
        "-o", f"ConnectTimeout={CONNECT_TIMEOUT_SECONDS}",
        "-i", str(config.key_path),
    ]


def ssh_argv(config: OffloadConfig, command: str) -> list[str]:
    return ["ssh", *_options(config), "-p", str(config.port), config.target, command]


def put_argv(config: OffloadConfig, local: Path, remote: str) -> list[str]:
    return ["scp", *_options(config), "-P", str(config.port), str(local), f"{config.target}:{remote}"]


def get_argv(config: OffloadConfig, remote: str, local: Path) -> list[str]:
    return ["scp", "-r", *_options(config), "-P", str(config.port), f"{config.target}:{remote}", str(local)]


def quoted(*parts: object) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def job_path(job_id: str) -> str:
    return f"{REMOTE_ROOT}/{job_id}"


class Transport:
    """The three remote operations a job needs, each one subprocess."""

    def __init__(self, config: OffloadConfig, launch: Launch, *, cwd: Path | None = None) -> None:
        self.config = config
        self._launch = launch
        self._cwd = cwd or Path.cwd()

    async def ssh(self, command: str, timeout: float) -> LaunchResult:
        return await self._launch(ssh_argv(self.config, command), self._cwd, timeout)

    async def put(self, local: Path, remote: str, timeout: float) -> LaunchResult:
        return await self._launch(put_argv(self.config, local, remote), self._cwd, timeout)

    async def get(self, remote: str, local: Path, timeout: float) -> LaunchResult:
        return await self._launch(get_argv(self.config, remote, local), self._cwd, timeout)
