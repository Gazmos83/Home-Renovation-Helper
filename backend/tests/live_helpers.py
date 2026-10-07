"""A fake Blender MCP addon: a loopback TCP server answering one JSON command per connection."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.live.detail_pass import FILE_TEMPLATE, REPORT_TEMPLATE

Handler = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


class FakeAddon:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.received: list[dict[str, Any]] = []
        self._server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> FakeAddon:
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        raw = await reader.read(65536)
        command = json.loads(raw.decode("utf-8"))
        self.received.append(command)
        answer = self.handler(command)
        if asyncio.iscoroutine(answer):
            answer = await answer
        writer.write(json.dumps(answer).encode("utf-8"))
        await writer.drain()
        writer.close()


def sync(test):
    """Run an `async def` test on its own loop (the project has no async test plugin)."""
    import functools

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        asyncio.run(test(*args, **kwargs))

    return wrapper


class FakeBlender:
    """What the pass talks to: one open file, scripts answered by shape."""

    def __init__(self) -> None:
        self.open_file = ""
        self.scripts: list[str] = []
        self.fail_with: Exception | None = None

    async def command(self, kind: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        if kind == "get_viewport_screenshot":
            Path(params["filepath"]).write_bytes(b"\x89PNG-fake")
            return {"success": True}
        assert kind == "execute_code"
        code = params["code"]
        self.scripts.append(code)
        if self.fail_with is not None and "AGENT" in code:
            raise self.fail_with
        if "open_mainfile" in code:
            self.open_file = re.search(r"filepath='(.*)'", code).group(1)
            return {"executed": True, "result": ""}
        if code == FILE_TEMPLATE:
            return {"executed": True, "result": f"FILE {self.open_file}\n"}
        if code == REPORT_TEMPLATE:
            return {"executed": True, "result": "objects: 2\n- bench | MESH | materials: none | modifiers: none\n"}
        return {"executed": True, "result": "ran\n" if "AGENT" in code else ""}
