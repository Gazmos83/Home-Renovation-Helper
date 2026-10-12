"""Read exact stored geometry; a cut rectangle alone is not a structural span."""

import hashlib
import json

from app.agent.tools.shared import read_input
from app.blender import storage
from app.blender.custom_build.derive import derive
from app.blender.schemas import CustomBuildSpec
from app.engineering.registry import EvidenceRefused


def digest(data: object) -> str:
    return hashlib.sha256(
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def stored_geometry(root, package_id, version) -> dict:
    document = read_input(storage.version_dir(root, package_id, version))
    if document is None:
        raise EvidenceRefused(
            "version", "exact stored input specification is unavailable"
        )
    try:
        spec = CustomBuildSpec.model_validate(document).model_dump(
            mode="json", exclude_none=True
        )
    except ValueError:
        raise EvidenceRefused(
            "spec",
            "stored specification does not support deterministic custom-build derivation",
        ) from None
    inputs_file = (
        storage.version_dir(root, package_id, version) / "hardware_inputs.json"
    )
    try:
        inputs = json.loads(inputs_file.read_text()) if inputs_file.exists() else None
    except OSError, ValueError:
        raise EvidenceRefused(
            "hardware_inputs", "stored derivation inputs are unreadable"
        ) from None
    parts, _, _ = derive(spec, inputs)
    return {
        "spec_hash": digest({"spec": spec, "derivation_inputs": inputs}),
        "spec": spec,
        "derivation_inputs": inputs,
        "parts": parts,
    }


def part_domain(geometry: dict, part_id: str) -> list[str]:
    parts = [part for part in geometry["parts"] if part["id"] == part_id]
    if not parts:
        return ["part_id is absent from the exact stored derivation"]
    spec = geometry["spec"]
    if spec.get("part_overrides"):
        return ["part overrides require an explicitly reviewed structural domain"]
    module = next(
        (
            module
            for module in spec["modules"]
            if part_id.startswith(module["id"] + "-")
        ),
        None,
    )
    if module is not None:
        if module.get("side_folds"):
            return ["folded/polygonal section is outside the rectangular shelf domain"]
        if module.get("dividers") or module.get("divider_spans"):
            return [
                "divider geometry does not establish a reviewed support/joint load path"
            ]
    if "shelf" not in part_id:
        return ["part is outside the rectangular shelf domain"]
    return []
