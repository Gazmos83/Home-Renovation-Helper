"""The generator files a render server needs (render-offload design decision 3).

The render generators run inside Blender's own Python and import a few modules
from `app`. This finds exactly that closure by reading the imports (nothing
heavier than the laptop's own Blender run needs), so the server renders with the
same code as the laptop and a persistent install cannot drift from it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final = Path(__file__).resolve().parents[3]
GENERATORS: Final = Path("app/blender/generators")
# The scripts a remote render runs.
ENTRY_SCRIPTS: Final = tuple(
    GENERATORS / name for name in ("render_still.py", "render_turntable.py", "build_room_scene.py")
)
# Files read at run time that are not imports.
DATA_FILES: Final = (Path("app/render/viewer.html"),)


def _module_file(backend: Path, dotted: str) -> Path | None:
    """The file `app.x.y` names, relative to `backend`, or `None` when it is not ours."""
    relative = Path(*dotted.split("."))
    for candidate in (relative.with_suffix(".py"), relative / "__init__.py"):
        if (backend / candidate).is_file():
            return candidate
    return None


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names if alias.name.split(".")[0] == "app")
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
            and node.module.split(".")[0] == "app"
        ):
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def bundle_files(backend: Path = BACKEND_ROOT, entries: tuple[Path, ...] = ENTRY_SCRIPTS) -> list[Path]:
    """Every file to upload, relative to `backend`, sorted."""
    pending = list(entries)
    seen: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        # Importing a module runs every parent package's `__init__.py`.
        for parent in current.parents:
            init = parent / "__init__.py"
            if parent != Path(".") and init not in seen and (backend / init).is_file():
                pending.append(init)
        for dotted in _imports(backend / current):
            target = _module_file(backend, dotted)
            if target is not None:
                pending.append(target)
    seen.update(path for path in DATA_FILES if (backend / path).is_file())
    return sorted(seen)
