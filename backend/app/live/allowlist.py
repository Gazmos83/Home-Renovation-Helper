"""The `bpy` allow-list (CLAUDE.md §8; photoreal-detail design decision 3).

A static check on a script's source, before it reaches the live Blender's
socket. It is pure: no `bpy`, no I/O. It answers `Allowed` or `Refused` naming
the first offending construct and its line.

This guards against an agent's mistakes. It is not a sandbox: the addon runs as
the owner's user, and the owner can switch the plugin off.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Final

MAX_SOURCE_CHARACTERS: Final = 20_000

ALLOWED_MODULES: Final = frozenset({"bpy", "bmesh", "mathutils", "math", "random"})
# `from bpy import X` binds a name that could hide `bpy.ops`; only these are safe.
ALLOWED_BPY_NAMES: Final = frozenset({"data", "context", "types", "props"})

REFUSED_BUILTINS: Final = frozenset(
    {
        "open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
        "getattr", "setattr", "delattr", "input", "breakpoint", "memoryview",
    }
)

# Refused on any base, which also defeats aliasing (`d = bpy.data; d.texts`).
REFUSED_ATTRIBUTES: Final = frozenset(
    {
        "texts", "libraries", "app", "utils", "handlers", "timers", "preferences", "addons",
        "load", "save", "save_as", "save_render", "unpack", "pack", "reload", "filepath_raw",
        "as_module", "driver_namespace",
    }
)

OPERATOR_NAMESPACES: Final = frozenset({"mesh", "object", "material", "node", "uv", "transform"})

SAVE_MAINFILE: Final = "bpy.ops.wm.save_mainfile"
OPEN_MAINFILE: Final = "bpy.ops.wm.open_mainfile"


@dataclass(frozen=True, slots=True)
class Allowed:
    """The script may be sent."""


@dataclass(frozen=True, slots=True)
class Refused:
    """The script must not be sent. `construct` names the first offender."""

    construct: str
    line: int

    @property
    def reason(self) -> str:
        return f"refused by the allow-list: {self.construct} (line {self.line})"


Verdict = Allowed | Refused


class _Found(Exception):
    def __init__(self, construct: str, line: int) -> None:
        super().__init__(construct)
        self.refused = Refused(construct, line)


def _chain(node: ast.expr) -> list[str] | None:
    """`a.b.c` as `["a", "b", "c"]`, or `None` when the base is not a plain name."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return None


class _Checker(ast.NodeVisitor):
    def __init__(self, detail_blend: str) -> None:
        self._detail_blend = detail_blend
        self._operator_nodes: set[int] = set()

    def _refuse(self, construct: str, node: ast.AST) -> None:
        raise _Found(construct, getattr(node, "lineno", 1))

    # --- statements that are never allowed -----------------------------------

    def visit_Global(self, node: ast.Global) -> None:
        self._refuse("global", node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self._refuse("nonlocal", node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._refuse("async def", node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._refuse("async for", node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._refuse("async with", node)

    def visit_Await(self, node: ast.Await) -> None:
        self._refuse("await", node)

    # --- imports ---------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in ALLOWED_MODULES:
                self._refuse(root, node)
            if alias.asname == "bpy" or (root == "bpy" and alias.asname):
                self._refuse(f"import {alias.name} as {alias.asname}", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level or not node.module:
            self._refuse("relative import", node)
        root = node.module.split(".")[0]
        if root not in ALLOWED_MODULES:
            self._refuse(root, node)
        if root == "bpy":
            for alias in node.names:
                if node.module != "bpy" or alias.name not in ALLOWED_BPY_NAMES:
                    self._refuse(f"from {node.module} import {alias.name}", node)

    # --- names and attributes --------------------------------------------------

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in REFUSED_BUILTINS:
            self._refuse(node.id, node)
        if node.id.startswith("__") and node.id.endswith("__"):
            self._refuse(node.id, node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if id(node) in self._operator_nodes:
            return
        chain = _chain(node)
        if chain and chain[:2] == ["bpy", "ops"]:
            self._refuse(".".join(chain), node)
        # Inner attributes first, so the first offender in reading order is named.
        self.generic_visit(node)
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self._refuse(node.attr, node)
        if node.attr in REFUSED_ATTRIBUTES:
            self._refuse(node.attr, node)
        if node.attr == "ops":
            # `x = bpy; x.ops...` would slip past the operator rule.
            self._refuse("ops", node)

    # --- operators ---------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        chain = _chain(node.func)
        if chain and chain[:2] == ["bpy", "ops"]:
            self._check_operator(node, chain)
            # Mark the callee's attribute nodes as dealt with, then check arguments.
            callee: ast.expr = node.func
            while isinstance(callee, ast.Attribute):
                self._operator_nodes.add(id(callee))
                callee = callee.value
            for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
                self.visit(argument)
            return
        self.generic_visit(node)

    def _check_operator(self, node: ast.Call, chain: list[str]) -> None:
        dotted = ".".join(chain)
        if len(chain) != 4:
            self._refuse(dotted, node)
        namespace = chain[2]
        if namespace in OPERATOR_NAMESPACES:
            return
        if dotted == SAVE_MAINFILE:
            if node.args or node.keywords:
                self._refuse(dotted, node)
            return
        if dotted == OPEN_MAINFILE:
            literal = (
                len(node.keywords) == 1
                and not node.args
                and node.keywords[0].arg == "filepath"
                and isinstance(node.keywords[0].value, ast.Constant)
                and node.keywords[0].value.value == self._detail_blend
            )
            if not literal:
                self._refuse(dotted, node)
            return
        self._refuse(dotted, node)


def check(source: str, *, detail_blend: str) -> Verdict:
    """Allow or refuse `source`. `detail_blend` is the one file `open_mainfile` may open."""
    if len(source) > MAX_SOURCE_CHARACTERS:
        return Refused(f"a script longer than {MAX_SOURCE_CHARACTERS} characters", 1)
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return Refused("a script that does not parse", error.lineno or 1)
    except (ValueError, RecursionError):
        return Refused("a script that does not parse", 1)
    try:
        _Checker(detail_blend).visit(tree)
    except _Found as found:
        return found.refused
    except RecursionError:
        return Refused("a script nested too deeply", 1)
    return Allowed()
