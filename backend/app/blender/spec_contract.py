"""The validation error shared by the dependency-free contracts.

Blender owns its Python runtime, which can differ from the backend interpreter,
so the contracts a background `bpy` process reads (`room_contract`,
`custom_build.derive`) stay standard-library-only. This module holds the one
exception they raise and the backend's Pydantic adapters catch.
"""

from __future__ import annotations


class SpecValidationError(ValueError):
    """A caller supplied a document this furniture type cannot construct."""
