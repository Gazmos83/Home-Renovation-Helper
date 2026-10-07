"""The plugin folder manifest: built-in and declarative HTTPS kinds.

A malformed manifest is refused by field path. Loader errors name the file.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Final, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

ROLES: Final = frozenset({"intake", "designer", "builder", "researcher", "reviewer", "lighting"})
HTTPS_TOOL_PATTERN: Final = r"^plugin_[a-z0-9_]{1,40}$"
PROPERTY_PATTERN: Final = r"^[A-Za-z][A-Za-z0-9_]{0,40}$"
_PLACEHOLDER: Final = re.compile(r"\{([^{}]*)\}")
FOLDER_NAME_PATTERN: Final = r"^[a-z][a-z0-9_]{0,62}$"

Primitive = Literal["string", "integer", "number", "boolean"]
PropertyType = Literal["string", "integer", "number", "boolean", "array"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ItemSchema(_Strict):
    type: Primitive
    enum: list[str | int | float | bool] | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=300)


class PropertySchema(_Strict):
    type: PropertyType | list[PropertyType | Literal["null"]]
    description: str | None = Field(default=None, max_length=300)
    enum: list[str | int | float | bool] | None = Field(default=None, max_length=100)
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = Field(default=None, max_length=200)
    max_length: int | None = Field(default=None, alias="maxLength", ge=1, le=10_000)
    items: ItemSchema | None = None
    max_items: int | None = Field(default=None, alias="maxItems", ge=1, le=500)

    @field_validator("type", mode="after")
    @classmethod
    def _one_real_type(cls, value: Any) -> Any:
        if isinstance(value, list):
            real = [item for item in value if item != "null"]
            if len(real) != 1 or len(value) > 2:
                raise ValueError("a type list may name one type and optionally null")
        return value

    @field_validator("pattern", mode="after")
    @classmethod
    def _compiles(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                re.compile(value)
            except re.error as error:
                raise ValueError(f"the pattern does not compile: {error}") from None
        return value

    @model_validator(mode="after")
    def _array_has_items(self) -> PropertySchema:
        if self.base_type == "array":
            if self.items is None:
                raise ValueError("an array property must declare items")
            if self.max_items is None:
                raise ValueError("an array property must declare maxItems")
        elif self.items is not None or self.max_items is not None:
            raise ValueError("items and maxItems apply only to an array property")
        return self

    @property
    def base_type(self) -> str:
        if isinstance(self.type, list):
            return next(item for item in self.type if item != "null")
        return self.type

    @property
    def nullable(self) -> bool:
        return isinstance(self.type, list) and "null" in self.type


class ObjectSchema(_Strict):
    type: Literal["object"]
    description: str | None = Field(default=None, max_length=500)
    properties: dict[str, PropertySchema] = Field(min_length=1, max_length=30)
    required: list[str] = Field(default_factory=list)
    additional_properties: bool = Field(default=False, alias="additionalProperties")

    @field_validator("properties", mode="after")
    @classmethod
    def _names(cls, value: dict[str, PropertySchema]) -> dict[str, PropertySchema]:
        bad = [name for name in value if not re.fullmatch(PROPERTY_PATTERN, name)]
        if bad:
            raise ValueError(f"property names must match {PROPERTY_PATTERN}: {', '.join(bad)}")
        return value

    @model_validator(mode="after")
    def _required_are_declared(self) -> ObjectSchema:
        unknown = [name for name in self.required if name not in self.properties]
        if unknown:
            raise ValueError(f"required names undeclared properties: {', '.join(unknown)}")
        return self


class ArrayOutputSchema(_Strict):
    type: Literal["array"]
    description: str | None = Field(default=None, max_length=500)
    items: ObjectSchema
    max_items: int = Field(alias="maxItems", ge=1, le=500)


class RequestSpec(_Strict):
    method: Literal["GET"]
    url: str = Field(min_length=1, max_length=500)
    query: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("url", mode="after")
    @classmethod
    def _https_template(cls, value: str) -> str:
        parts = urlsplit(_PLACEHOLDER.sub("x", value))
        if parts.scheme != "https":
            raise ValueError("the URL must use https")
        if parts.username is not None or parts.password is not None or "@" in parts.netloc:
            raise ValueError("the URL must not carry credentials")
        if parts.port is not None:
            raise ValueError("the URL must not name a port")
        if parts.query or parts.fragment:
            raise ValueError("the URL must not carry a query string or fragment; use `query`")
        host = urlsplit(value).hostname or ""
        if not host or "{" in host or "}" in value.split("/", 3)[2]:
            raise ValueError("the host must be a fixed name, never a placeholder")
        return value

    @property
    def host(self) -> str:
        return (urlsplit(self.url).hostname or "").lower()

    def placeholders(self) -> set[str]:
        names = set(_PLACEHOLDER.findall(self.url))
        for template in self.query.values():
            names |= set(_PLACEHOLDER.findall(template))
        return names


class _Common(_Strict):
    name: str = Field(pattern=FOLDER_NAME_PATTERN)
    description: str = Field(min_length=1, max_length=500)
    role: Literal["intake", "designer", "builder", "researcher", "reviewer", "lighting"]
    tools: list[str] = Field(min_length=1, max_length=20)
    enabled_by_default: bool
    toggleable: bool = True


class BuiltinManifest(_Common):
    kind: Literal["builtin"]
    # Other agents whose instruction headers may name this plugin's tools too
    # (a tool both the Builder and Lighting & materials use). Binding is still by header.
    also_for: list[Literal["intake", "designer", "builder", "researcher", "reviewer", "lighting"]] = Field(
        default_factory=list, max_length=5
    )

    @model_validator(mode="after")
    def _also_for_names_other_agents(self) -> BuiltinManifest:
        if len(self.also_for) != len(set(self.also_for)):
            raise ValueError("also_for must not repeat an agent")
        if self.role in self.also_for:
            raise ValueError("also_for must name agents other than the role")
        return self

    @field_validator("tools", mode="after")
    @classmethod
    def _tool_names(cls, value: list[str]) -> list[str]:
        bad = [name for name in value if not re.fullmatch(r"^[a-z][a-z0-9_]{0,62}$", name)]
        if bad:
            raise ValueError(f"tool names must be snake_case: {', '.join(bad)}")
        if len(value) != len(set(value)):
            raise ValueError("tools must be unique within a plugin")
        return value


class HttpsManifest(_Common):
    kind: Literal["https"]
    input_schema: ObjectSchema
    output_schema: ObjectSchema | ArrayOutputSchema = Field(discriminator="type")
    request: RequestSpec

    @field_validator("enabled_by_default", mode="after")
    @classmethod
    def _never_on_by_default(cls, value: bool) -> bool:
        if value:
            raise ValueError("an HTTPS plugin must not be enabled by default")
        return value

    @field_validator("input_schema", mode="after")
    @classmethod
    def _closed_input(cls, value: ObjectSchema) -> ObjectSchema:
        if value.additional_properties:
            raise ValueError("input_schema must set additionalProperties to false")
        return value

    @model_validator(mode="after")
    def _one_https_tool(self) -> HttpsManifest:
        expected = f"plugin_{self.name}"
        if self.tools != [expected]:
            raise ValueError(f"an HTTPS plugin must declare exactly one tool named {expected!r}")
        if not re.fullmatch(HTTPS_TOOL_PATTERN, expected):
            raise ValueError(f"the derived tool name {expected!r} is outside plugin_[a-z0-9_]{{1,40}}")
        declared = set(self.input_schema.properties)
        unbound = sorted(self.request.placeholders() - declared)
        if unbound:
            raise ValueError("request placeholders name no declared input: " + ", ".join(unbound))
        for name in self.request.placeholders():
            if self.input_schema.properties[name].base_type == "array":
                raise ValueError(f"placeholder {name!r} names an array input")
        return self


Manifest = Annotated[BuiltinManifest | HttpsManifest, Field(discriminator="kind")]
_ADAPTER: TypeAdapter[BuiltinManifest | HttpsManifest] = TypeAdapter(Manifest)


class ManifestRefused(ValueError):
    """A manifest outside the supported contract; `errors` name each field."""

    def __init__(self, errors: list[dict[str, str]], *, path: str | None = None) -> None:
        self.errors = errors
        self.path = path
        detail = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
        prefix = f"{path}: " if path else ""
        super().__init__(prefix + detail)


def _field(loc: tuple[Any, ...], message: str = "") -> str:
    parts = [str(part) for part in loc if part not in ("object", "array", "builtin", "https")]
    if parts:
        return ".".join(parts)
    if "kind" in message or "tag" in message or "discriminator" in message:
        return "kind"
    return "manifest"


def parse_manifest(data: Any, *, path: str | None = None) -> BuiltinManifest | HttpsManifest:
    """Validate a folder manifest; raise `ManifestRefused` with field paths."""
    try:
        return _ADAPTER.validate_python(data)
    except ValidationError as error:
        raise ManifestRefused(
            [
                {"field": _field(detail["loc"], detail["msg"]), "message": detail["msg"]}
                for detail in error.errors(include_url=False)
            ],
            path=path,
        ) from None
