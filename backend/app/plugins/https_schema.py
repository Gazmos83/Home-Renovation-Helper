"""The HTTPS plugin's schema subset, as Pydantic models.

`args_model` is the tool's argument schema: the model sees it as parameters, and
the same class validates every model-generated argument (CLAUDE.md §8).
`output_adapter` validates what the external API returned; undeclared fields are
dropped rather than passed to the model.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, create_model

from app.plugins.manifest import (
    ArrayOutputSchema,
    HttpsManifest,
    ItemSchema,
    ObjectSchema,
    PropertySchema,
)

_PRIMITIVES: dict[str, type] = {"string": str, "integer": int, "number": float, "boolean": bool}


def _item_type(item: ItemSchema) -> Any:
    if item.enum:
        return Literal[tuple(item.enum)]  # type: ignore[valid-type]
    return _PRIMITIVES[item.type]


def _property_type(prop: PropertySchema) -> Any:
    base = prop.base_type
    if base == "array":
        assert prop.items is not None
        annotation: Any = Annotated[
            list[_item_type(prop.items)], Field(max_length=prop.max_items)
        ]
    elif prop.enum:
        annotation = Literal[tuple(prop.enum)]  # type: ignore[valid-type]
    else:
        constraints: dict[str, Any] = {}
        if prop.minimum is not None:
            constraints["ge"] = prop.minimum
        if prop.maximum is not None:
            constraints["le"] = prop.maximum
        if base == "string":
            if prop.pattern is not None:
                constraints["pattern"] = prop.pattern
            if prop.max_length is not None:
                constraints["max_length"] = prop.max_length
        annotation = Annotated[_PRIMITIVES[base], Field(strict=base != "number", **constraints)]
    if prop.nullable:
        annotation = annotation | None
    return annotation


def _object_model(name: str, schema: ObjectSchema, *, extra: Literal["forbid", "ignore"]) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for prop_name, prop in schema.properties.items():
        annotation = _property_type(prop)
        required = prop_name in schema.required
        if not required and not prop.nullable:
            annotation = annotation | None
        default = ... if required else None
        fields[prop_name] = (annotation, Field(default, description=prop.description))
    return create_model(
        name,
        __config__=ConfigDict(extra=extra),
        __doc__=schema.description,
        **fields,
    )


def _camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def args_model(manifest: HttpsManifest) -> type[BaseModel]:
    return _object_model(f"{_camel(manifest.name)}Args", manifest.input_schema, extra="forbid")


def output_adapter(manifest: HttpsManifest) -> TypeAdapter[Any]:
    schema = manifest.output_schema
    if isinstance(schema, ArrayOutputSchema):
        item = _object_model(f"{_camel(manifest.name)}Item", schema.items, extra="ignore")
        return TypeAdapter(Annotated[list[item], Field(max_length=schema.max_items)])  # type: ignore[valid-type]
    return TypeAdapter(_object_model(f"{_camel(manifest.name)}Output", schema, extra="ignore"))


def output_field_notes(manifest: HttpsManifest) -> str:
    schema = manifest.output_schema
    properties = schema.items.properties if isinstance(schema, ArrayOutputSchema) else schema.properties
    lines = [
        f"- {name}: {prop.description}"
        for name, prop in properties.items()
        if prop.description
    ]
    return ("Returned fields:\n" + "\n".join(lines)) if lines else ""
