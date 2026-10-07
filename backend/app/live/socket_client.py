"""The live Blender's socket (photoreal-detail design decision 4).

The Blender MCP addon listens on a loopback port and answers one JSON command
per connection: `{"type": ..., "params": {...}}` in, `{"status": "success",
"result": ...}` or `{"status": "error", "message": ...}` out. This client sends
exactly one command per connection and shares the one-Blender-process lock with
the headless runner: a command is refused while a headless job holds it, and it
holds the lock itself while it runs, so a headless job requested meanwhile waits.

Nothing here decides what may be sent. The allow-list (`allowlist.py`) and the
detail pass do that before a script reaches `execute_code`.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Final

MAX_RESPONSE_BYTES: Final = 4 * 1024 * 1024
BLENDER_BUSY: Final = "a Blender job is running; try again when it finishes"
NOT_OPEN: Final = "Blender is not open with the MCP addon"


class LiveRefused(Exception):
    """The command was not sent, or got no usable answer. `reason` is safe to show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AddonError(Exception):
    """The addon answered with an error. `message` is untrusted text from Blender."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LiveBlender:
    """One loopback connection per command, under the app's Blender semaphore."""

    def __init__(
        self, host: str, port: int, *, semaphore: asyncio.Semaphore, timeout: float = 120.0
    ) -> None:
        self._host = host
        self._port = port
        self._semaphore = semaphore
        self._timeout = timeout

    async def command(self, kind: str, params: dict[str, Any] | None = None) -> Any:
        """Send one command and return the addon's `result`."""
        if self._semaphore.locked():
            raise LiveRefused(BLENDER_BUSY)
        async with self._semaphore:
            try:
                return await asyncio.wait_for(self._exchange(kind, params or {}), self._timeout)
            except TimeoutError:
                raise LiveRefused(
                    f"Blender did not answer within {self._timeout:g} seconds; "
                    "it may still be running the script"
                ) from None

    async def _exchange(self, kind: str, params: dict[str, Any]) -> Any:
        try:
            reader, writer = await asyncio.open_connection(self._host, self._port)
        except OSError:
            raise LiveRefused(NOT_OPEN) from None
        try:
            writer.write(json.dumps({"type": kind, "params": params}).encode("utf-8"))
            await writer.drain()
            answer = await self._read_json(reader)
        except OSError:
            raise LiveRefused("the connection to Blender was lost") from None
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        if not isinstance(answer, dict):
            raise LiveRefused("Blender answered with something that is not a command result")
        if answer.get("status") == "error":
            raise AddonError(str(answer.get("message") or "the addon reported an error"))
        return answer.get("result")

    @staticmethod
    async def _read_json(reader: asyncio.StreamReader) -> Any:
        decoder = json.JSONDecoder()
        buffer = ""
        raw = b""
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                raise LiveRefused("Blender closed the connection without a complete answer")
            raw += chunk
            if len(raw) > MAX_RESPONSE_BYTES:
                raise LiveRefused("Blender's answer was larger than the allowed size")
            try:
                buffer = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue  # a multi-byte character split across reads
            try:
                value, _end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                continue
            return value
