"""The detail pass on a version (photoreal-detail design decisions 1, 2, 5 and 6).

A pass works on `<version>/detail/detail.blend`, a copy of the built
`model.blend`, open in the owner's live Blender. Every script sent there — the
Lighting agent's and this module's own templates — goes through the allow-list
first and is logged. The agent reads the scene as a text report; screenshots are
for the owner. Nothing here reads or writes the spec.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Protocol
from uuid import uuid4

from app.agent.prompts import Passage, wrap_passage
from app.blender import storage
from app.live import allowlist
from app.live.socket_client import AddonError, LiveRefused

logger = logging.getLogger("app")

MAX_REPORT_CHARACTERS: Final = 8000
MAX_OUTPUT_CHARACTERS: Final = 4000
SCREENSHOT_MAX_SIZE: Final = 800
_SCREEN_NAME: Final = re.compile(r"^screen_(\d{3,})\.png$")

# Fixed scripts the service sends itself. Each goes through the allow-list like any other.
OPEN_TEMPLATE: Final = "import bpy\nbpy.ops.wm.open_mainfile(filepath={path})\n"
SAVE_TEMPLATE: Final = "import bpy\nbpy.ops.wm.save_mainfile()\n"
FILE_TEMPLATE: Final = 'import bpy\nprint("FILE", bpy.data.filepath)\n'
REPORT_TEMPLATE: Final = """\
import bpy
objects = list(bpy.data.objects)
print("objects:", len(objects))
for o in objects[:80]:
    materials = [s.material.name for s in o.material_slots if s.material]
    modifiers = [m.type for m in o.modifiers]
    print("-", o.name, "|", o.type, "| materials:", ", ".join(materials) or "none", "| modifiers:", ", ".join(modifiers) or "none")
if len(objects) > 80:
    print("... and", len(objects) - 80, "more objects")
lights = [o.name for o in objects if o.type == "LIGHT"]
print("lights:", ", ".join(lights) or "none")
world = bpy.context.scene.world
print("world:", world.name if world else "none")
print("engine:", bpy.context.scene.render.engine)
"""


class DetailPassError(Exception):
    """The pass cannot continue. `reason` is safe to show the owner and the agent."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LiveClient(Protocol):
    async def command(self, kind: str, params: dict[str, Any] | None = None) -> Any: ...


def _now() -> str:
    return datetime.now(UTC).isoformat()


def untrusted(text: str, *, source: str = "live Blender") -> str:
    """Text that came out of Blender, delimited so the model reads it as data."""
    stamp = _now()
    return wrap_passage(
        Passage(content=text, url="blender://localhost", scraped_at=stamp, source_site=source), stamp
    )


class DetailPass:
    def __init__(self, folder: Path, client: LiveClient, *, tracing: Any = None) -> None:
        self._folder = folder
        self._client = client
        self._tracing = tracing
        self._dir = storage.detail_dir(folder)
        self._blend = storage.detail_blend_path(folder)

    @property
    def blend(self) -> Path:
        return self._blend

    # --- the pass ----------------------------------------------------------------

    def prepare(self) -> bool:
        """Copy `model.blend` to `detail/detail.blend` unless a pass already did.

        Returns whether a copy was made. `model.blend` is only ever read.
        """
        state = storage.read_status(self._folder) or {}
        source = self._folder / "model.blend"
        if state.get("status") != "succeeded" or not source.is_file():
            raise DetailPassError("this version has not been built successfully yet; build it first")
        if self._blend.is_file():
            return False
        self._dir.mkdir(exist_ok=True)
        temp = self._dir / f".{storage.DETAIL_BLEND}.{uuid4().hex}.tmp"
        shutil.copy2(source, temp)
        os.replace(temp, self._blend)
        return True

    async def start(self) -> str:
        """Prepare the copy, open it in the live Blender and report the scene."""
        self.prepare()
        await self._send(OPEN_TEMPLATE.format(path=repr(str(self._blend))), "open detail.blend", "service")
        await self._ensure_open()
        return await self._report()

    async def run_script(self, code: str, purpose: str) -> str:
        """Check, run and log one agent script; answer with what the agent should read."""
        verdict = allowlist.check(code, detail_blend=str(self._blend))
        if isinstance(verdict, allowlist.Refused):
            self._log(origin="agent", purpose=purpose, code=code, verdict=verdict, outcome=None, seconds=0.0)
            return (
                f"Script refused by the allow-list: {verdict.construct} (line {verdict.line}). "
                "Nothing was sent to Blender. Rewrite the script without it, or tell the owner "
                "this cannot be done here."
            )
        try:
            await self._ensure_open()
            output = await self._send(code, purpose, "agent")
            report = await self._report()
        except AddonError as error:
            return f"The script failed in Blender:\n{untrusted(error.message)}"
        except (LiveRefused, DetailPassError) as error:
            return error.reason
        shown = output[:MAX_OUTPUT_CHARACTERS]
        return (
            "The script ran.\n"
            + (f"Its output:\n{untrusted(shown)}\n" if shown.strip() else "")
            + f"The scene now:\n{untrusted(report)}"
        )

    async def screenshot(self) -> tuple[int, Path]:
        """Capture the live viewport into `detail/screens/`, numbered in order."""
        folder = self._dir / storage.DETAIL_SCREENS_DIRNAME
        folder.mkdir(parents=True, exist_ok=True)
        taken = [int(m.group(1)) for p in folder.iterdir() if (m := _SCREEN_NAME.match(p.name))]
        index = max(taken, default=-1) + 1
        path = folder / f"screen_{index:03d}.png"
        try:
            await self._client.command(
                "get_viewport_screenshot",
                {"max_size": SCREENSHOT_MAX_SIZE, "filepath": str(path), "format": "png"},
            )
        except AddonError as error:
            raise DetailPassError(f"Blender could not take the screenshot: {error.message[:200]}") from None
        except LiveRefused as error:
            raise DetailPassError(error.reason) from None
        if not path.is_file() or path.stat().st_size == 0:
            raise DetailPassError("Blender did not write the screenshot")
        return index, path

    async def save(self) -> bool:
        """Save the open detail file before a render. Never raises: a closed Blender
        or another open file means the copy on disk is rendered as it is."""
        try:
            await self._ensure_open()
            await self._send(SAVE_TEMPLATE, "save detail.blend", "service")
        except (AddonError, LiveRefused, DetailPassError):
            return False
        return True

    # --- internals -----------------------------------------------------------------

    async def _report(self) -> str:
        text = await self._send(REPORT_TEMPLATE, "report the scene", "service")
        return text[:MAX_REPORT_CHARACTERS]

    async def _ensure_open(self) -> None:
        printed = await self._send(FILE_TEMPLATE, "check the open file", "service")
        match = re.search(r"^FILE (.*)$", printed, re.MULTILINE)
        opened = match.group(1).strip() if match else ""
        try:
            same = bool(opened) and Path(opened).resolve() == self._blend.resolve()
        except OSError:
            same = False
        if not same:
            raise DetailPassError(
                "The pass was interrupted: the file open in Blender is not this version's "
                "detail.blend. Ask the owner to reopen it or start the detail pass again."
            )

    async def _send(self, code: str, purpose: str, origin: str) -> str:
        verdict = allowlist.check(code, detail_blend=str(self._blend))
        if isinstance(verdict, allowlist.Refused):
            if origin == "service":  # a template that fails its own allow-list is a bug
                raise AssertionError(f"detail-pass template refused: {verdict.reason}")
            raise DetailPassError(verdict.reason)
        started = time.perf_counter()
        outcome: dict[str, Any] = {"status": "ok"}
        try:
            result = await self._client.command("execute_code", {"code": code})
        except AddonError as error:
            outcome = {"status": "error", "error": error.message[:500]}
            raise
        except LiveRefused as error:
            outcome = {"status": "error", "error": error.reason}
            raise
        finally:
            self._log(
                origin=origin, purpose=purpose, code=code, verdict=verdict, outcome=outcome,
                seconds=time.perf_counter() - started,
            )
        if isinstance(result, dict):
            return str(result.get("result") or "")
        return str(result or "")

    def _log(
        self, *, origin: str, purpose: str, code: str, verdict: allowlist.Verdict,
        outcome: dict[str, Any] | None, seconds: float,
    ) -> None:
        refused = isinstance(verdict, allowlist.Refused)
        entry: dict[str, Any] = {
            "time": _now(),
            "origin": origin,
            "purpose": purpose[:300],
            "code": code,
            "verdict": "refused" if refused else "allowed",
            "construct": verdict.construct if isinstance(verdict, allowlist.Refused) else None,
            "line": verdict.line if isinstance(verdict, allowlist.Refused) else None,
            "outcome": outcome["status"] if outcome else None,
            "error": outcome.get("error") if outcome else None,
            "seconds": round(seconds, 3),
        }
        try:
            self._dir.mkdir(exist_ok=True)
            with (self._dir / storage.DETAIL_LOG).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("detail.log_failed")
        if self._tracing is not None:
            self._tracing.record_detail_script(**{k: v for k, v in entry.items() if k != "code"})
