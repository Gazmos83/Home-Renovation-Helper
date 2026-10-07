"""Design import documents (design-import): parse, the shipped template, export.

An import document is a bare `custom_build` document, or the wrapper `package_import`
holding one as its `build` with an optional `guide` for whoever fills it in. Design
only: a room `survey` is refused, because Intake records rooms. Nothing in a
document is executed; the build is validated by the custom-build schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.blender.schemas import CustomBuildSpec, describe_validation_error
from app.blender.spec_contract import SpecValidationError

if TYPE_CHECKING:
    from app.agent.tools.base import ToolContext

TEMPLATE_PATH: Final = Path(__file__).resolve().parents[1] / "fixtures/packages/templates/import-template.json"
KINDS: Final = ("custom_build", "package_import")
SURVEY_REFUSAL: Final = (
    "survey: rooms are not imported; remove the survey section. "
    "Intake records a room from its measurements or a plan"
)


class ImportDocument(BaseModel):
    """The wrapper form. `build` is validated separately, as a design."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["package_import"]
    schema_version: Literal[1]
    units: Literal["mm"]
    guide: Annotated[list[Annotated[str, StringConstraints(max_length=500)]], Field(max_length=40)] = []
    build: dict[str, Any]


def unwrap(document: Any) -> tuple[Any, str]:
    """The design inside `document` (not yet validated), or a refusal."""
    if not isinstance(document, dict) or document.get("kind") not in KINDS:
        return None, "kind: an import document is a custom_build document or a package_import wrapper"
    if document["kind"] == "custom_build":
        return document, ""
    if "survey" in document:
        return None, SURVEY_REFUSAL
    try:
        return ImportDocument.model_validate(document).build, ""
    except ValidationError as error:
        return None, describe_validation_error(error)


def parse_import(
    document: Any, ctx: ToolContext | None = None, package_id: str | None = None
) -> tuple[dict[str, Any] | None, str]:
    """The validated, normalised design, or a refusal naming every problem.

    With a tool context, an unknown design field is also recorded as a
    generator-extension request (ladder step 2), as for a design written here.
    """
    build, refusal = unwrap(document)
    if refusal:
        return None, refusal
    if ctx is not None:
        from app.agent.tools.shared import validated_custom_build

        return validated_custom_build(ctx, build, package_id)
    try:
        return CustomBuildSpec.model_validate(build).model_dump(mode="json"), ""
    except ValidationError as error:
        return None, describe_validation_error(error)
    except SpecValidationError as error:
        return None, str(error)


def load_template() -> dict[str, Any]:
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def export_document(design: dict[str, Any]) -> dict[str, Any]:
    """A stored design as an import document that re-imports unchanged (no guide)."""
    return {"kind": "package_import", "schema_version": 1, "units": "mm", "build": design}
