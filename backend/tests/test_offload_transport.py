"""render-offload: ssh and scp commands are built from code only."""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path

import pytest

from app.blender.launch import LaunchResult
from app.render.offload.transport import (
    OffloadConfig,
    Transport,
    get_argv,
    job_path,
    put_argv,
    quoted,
    ssh_argv,
)

CONFIG = OffloadConfig(
    host="gpu.example.org", port=2222, user="render", key_path=Path("/keys/id"),
    known_hosts_path=Path("/keys/known_hosts"), blender="/opt/blender-5.2.1/blender", device="OPTIX",
)
REQUIRED = [
    "BatchMode=yes", "StrictHostKeyChecking=yes", "UserKnownHostsFile=/keys/known_hosts",
    "IdentitiesOnly=yes", "ConnectTimeout=10",
]


def options_of(argv: list[str]) -> list[str]:
    return [argv[i + 1] for i, part in enumerate(argv) if part == "-o"]


@pytest.mark.parametrize(
    "argv",
    [
        ssh_argv(CONFIG, "true"),
        put_argv(CONFIG, Path("/tmp/a.tar"), "hra-render/j/a.tar"),
        get_argv(CONFIG, "hra-render/j/out", Path("/tmp/stage")),
    ],
)
def test_every_call_is_key_only_batch_mode_with_the_pinned_host_key(argv: list[str]) -> None:
    assert options_of(argv) == REQUIRED
    assert argv[argv.index("-i") + 1] == "/keys/id"
    assert "-o" in argv and "PasswordAuthentication=yes" not in argv
    assert argv[0] in {"ssh", "scp"}


def test_ports_are_given_in_each_tools_own_spelling() -> None:
    assert ssh_argv(CONFIG, "true")[ssh_argv(CONFIG, "true").index("-p") + 1] == "2222"
    assert "-P" in put_argv(CONFIG, Path("a"), "b") and "-P" in get_argv(CONFIG, "a", Path("b"))


def test_the_target_is_user_at_host_and_the_command_is_one_argument() -> None:
    argv = ssh_argv(CONFIG, "cd job && ls")
    assert argv[-2] == "render@gpu.example.org" and argv[-1] == "cd job && ls"
    assert put_argv(CONFIG, Path("/tmp/a"), "hra-render/j/a")[-1] == "render@gpu.example.org:hra-render/j/a"
    assert get_argv(CONFIG, "hra-render/j/out", Path("/s"))[-2] == "render@gpu.example.org:hra-render/j/out"
    assert "-r" in get_argv(CONFIG, "x", Path("y"))


@pytest.mark.parametrize("hostile", ["a; rm -rf /", "$(id)", "`id`", "x y", "it's", 'q"q', "a\nb", "&& id"])
def test_quoted_pieces_survive_a_shell_as_single_words(hostile: str) -> None:
    command = quoted("echo", hostile, 36, "CYCLES")
    assert shlex.split(command) == ["echo", hostile, "36", "CYCLES"]


def test_the_job_path_sits_under_the_fixed_remote_root() -> None:
    assert job_path("abc123") == "hra-render/abc123"


def test_the_transport_runs_each_call_through_the_launcher() -> None:
    seen: list[tuple[list[str], float]] = []

    async def launch(argv, cwd, timeout):
        seen.append((argv, timeout))
        return LaunchResult(0, "", False)

    transport = Transport(CONFIG, launch)

    async def go():
        await transport.ssh("true", 5)
        await transport.put(Path("/tmp/a"), "hra-render/j/a", 7)
        await transport.get("hra-render/j/out", Path("/tmp/s"), 9)

    asyncio.run(go())
    assert [argv[0] for argv, _ in seen] == ["ssh", "scp", "scp"]
    assert [timeout for _, timeout in seen] == [5, 7, 9]
