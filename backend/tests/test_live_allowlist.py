"""The `bpy` allow-list (photoreal-detail): permitted and refused constructs."""

from __future__ import annotations

import pytest

from app.live.allowlist import MAX_SOURCE_CHARACTERS, Allowed, Refused, check

DETAIL = "/renders/hall-bench/v2/detail/detail.blend"


def verdict(source: str):
    return check(source, detail_blend=DETAIL)


ALLOWED = {
    "material": (
        "import bpy\n"
        "mat = bpy.data.materials.new('Oak')\n"
        "mat.use_nodes = True\n"
        "bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')\n"
        "bsdf.inputs['Base Color'].default_value = (0.5, 0.35, 0.2, 1)\n"
        "bsdf.inputs['Roughness'].default_value = 0.4\n"
        "bpy.data.objects['hall-bench'].data.materials.append(mat)\n"
    ),
    "modifier": (
        "import bpy\nobj = bpy.data.objects['a']\n"
        "mod = obj.modifiers.new('Bevel', 'BEVEL')\nmod.width = 0.002\n"
    ),
    "math and random": "import math, random\nfrom mathutils import Vector\nx = Vector((math.pi, random.random(), 0))\n",
    "world and render settings": (
        "import bpy\nscene = bpy.context.scene\nscene.cycles.samples = 64\n"
        "scene.world.use_nodes = True\n"
    ),
    "mesh operator": "import bpy\nbpy.ops.mesh.primitive_cube_add(size=1)\nbpy.ops.object.shade_smooth()\n",
    "save with no arguments": "import bpy\nbpy.ops.wm.save_mainfile()\n",
    "open the pass's file": f"import bpy\nbpy.ops.wm.open_mainfile(filepath={DETAIL!r})\n",
    "read the open file path": "import bpy\nprint(bpy.data.filepath)\n",
    "from bpy import data": "from bpy import data\nprint(len(data.objects))\n",
}


@pytest.mark.parametrize("source", ALLOWED.values(), ids=ALLOWED.keys())
def test_allowed(source):
    assert verdict(source) == Allowed()


REFUSED = {
    "import subprocess": ("import subprocess\n", "subprocess", 1),
    "import os": ("import bpy\nimport os\n", "os", 2),
    "from shutil": ("from shutil import rmtree\n", "shutil", 1),
    "from os.path": ("from os.path import join\n", "os", 1),
    "import sys": ("import sys\n", "sys", 1),
    "relative import": ("from . import x\n", "relative import", 1),
    "open": ("x = open('/etc/passwd')\n", "open", 1),
    "exec": ("exec('1')\n", "exec", 1),
    "eval": ("eval('1')\n", "eval", 1),
    "compile": ("compile('1', 'x', 'eval')\n", "compile", 1),
    "__import__": ("__import__('os')\n", "__import__", 1),
    "getattr": ("import bpy\ngetattr(bpy, 'ops')\n", "getattr", 2),
    "setattr": ("setattr(1, 'a', 2)\n", "setattr", 1),
    "globals": ("globals()\n", "globals", 1),
    "vars": ("vars()\n", "vars", 1),
    "dunder attribute": ("x = ().__class__\n", "__class__", 1),
    "dunder name": ("__builtins__\n", "__builtins__", 1),
    "render operator": ("import bpy\nbpy.ops.render.render(write_still=True)\n", "bpy.ops.render.render", 2),
    "script operator": ("import bpy\nbpy.ops.script.python_file_run(filepath='x')\n", "bpy.ops.script.python_file_run", 2),
    "wm operator": ("import bpy\nbpy.ops.wm.quit_blender()\n", "bpy.ops.wm.quit_blender", 2),
    "ops bound to a name": ("import bpy\nops = bpy.ops\nops.render.render()\n", "bpy.ops", 2),
    "ops reached through an alias": ("import bpy\nb = bpy\nb.ops.render.render()\n", "ops", 3),
    "ops imported": ("from bpy import ops\n", "from bpy import ops", 1),
    "import bpy as": ("import bpy as b\n", "import bpy as b", 1),
    "text block": ("import bpy\nbpy.data.texts.new('x')\n", "texts", 2),
    "aliased text block": ("import bpy\nd = bpy.data\nd.texts.new('x')\n", "texts", 3),
    "library load": ("import bpy\nbpy.data.libraries.load('/x')\n", "libraries", 2),
    "application handlers": ("import bpy\nbpy.app.handlers.load_post.append(1)\n", "app", 2),
    "timers": ("import bpy\nbpy.app.timers.register(print)\n", "app", 2),
    "preferences": ("import bpy\nbpy.context.preferences.addons\n", "preferences", 2),
    "image save": ("import bpy\nbpy.data.images['a'].save_render('/tmp/x.png')\n", "save_render", 2),
    "save with a path": (
        "import bpy\nbpy.ops.wm.save_mainfile(filepath='/tmp/x.blend')\n",
        "bpy.ops.wm.save_mainfile",
        2,
    ),
    "save as": ("import bpy\nbpy.ops.wm.save_as_mainfile(filepath='/tmp/x.blend')\n", "bpy.ops.wm.save_as_mainfile", 2),
    "open another file": (
        "import bpy\nbpy.ops.wm.open_mainfile(filepath='/renders/hall-bench/v2/model.blend')\n",
        "bpy.ops.wm.open_mainfile",
        2,
    ),
    "open a variable path": ("import bpy\np = 'x'\nbpy.ops.wm.open_mainfile(filepath=p)\n", "bpy.ops.wm.open_mainfile", 3),
    "open with an extra argument": (
        f"import bpy\nbpy.ops.wm.open_mainfile(filepath={DETAIL!r}, load_ui=True)\n",
        "bpy.ops.wm.open_mainfile",
        2,
    ),
    "open positionally": (f"import bpy\nbpy.ops.wm.open_mainfile({DETAIL!r})\n", "bpy.ops.wm.open_mainfile", 2),
    "operator passed as value": ("import bpy\nf = bpy.ops.object.delete\n", "bpy.ops.object.delete", 2),
    "global": ("def f():\n    global x\n    x = 1\n", "global", 2),
    "async": ("async def f():\n    pass\n", "async def", 1),
    "syntax error": ("def (:\n", "a script that does not parse", 1),
    "operator hidden in an argument": (
        "import bpy\nbpy.ops.object.select_all(action=open('x'))\n",
        "open",
        2,
    ),
}


@pytest.mark.parametrize(
    ("source", "construct", "line"), REFUSED.values(), ids=REFUSED.keys()
)
def test_refused_naming_the_construct_and_line(source, construct, line):
    result = verdict(source)
    assert isinstance(result, Refused)
    assert (result.construct, result.line) == (construct, line)
    assert construct in result.reason


def test_too_long_is_refused():
    result = verdict("x = 1\n" * (MAX_SOURCE_CHARACTERS // 5))
    assert isinstance(result, Refused)
    assert "longer than" in result.construct


def test_just_under_the_cap_is_allowed():
    source = "x = 1\n" * 3000
    assert len(source) < MAX_SOURCE_CHARACTERS
    assert verdict(source) == Allowed()
