"""Shared helpers for the `--blender` tests (pinned Blender 5.2.1 LTS)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.blender.schemas import CustomBuildSpec
from app.render.tiers import Tier, load_tiers

BACKEND = Path(__file__).resolve().parents[1]
GENERATORS = BACKEND / "app/blender/generators"
TEMPLATE = BACKEND / "fixtures/packages/templates/fold-down-desk.json"
DRAFT = load_tiers().get("draft")


def tier_args(tier: Tier = DRAFT) -> list[str]:
    return [
        "--tier-frames", str(tier.frames),
        "--tier-resolution", str(tier.resolution),
        "--tier-engine", tier.blender_engine,
    ]


def run_generator(
    blender_bin: Path, script: str, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    import os

    return subprocess.run(
        [str(blender_bin), "--background", "--python", str(GENERATORS / script), "--", *args],
        capture_output=True, text=True, timeout=900, check=False,
        env={**os.environ, **(env or {})},
    )


def build_template(blender_bin: Path, tmp: Path) -> Path:
    """Build the fold-down-desk template (no render) and return its directory."""
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    spec = tmp / "spec.json"
    spec.write_text(
        json.dumps(CustomBuildSpec.model_validate(document).model_dump(mode="json")),
        encoding="utf-8",
    )
    out = tmp / "build"
    result = run_generator(blender_bin, "build_custom_build.py", "--spec", str(spec), "--out", str(out))
    assert result.returncode == 0, result.stderr[-800:]
    return out
