---
description: "How to discover and drive Blender through MCP, including official and community servers. Read before the first Blender call."
connections: [shell-and-openings, photoreal, photo-match]
---

# Blender MCP connection

Do not hard-code one server. Discover tools, then map the job onto whatever is connected.

## Servers the user may have

| Server | Typical entry | What to prefer |
|---|---|---|
| Community `mcp-for-blender` / ahujasid | addon socket `127.0.0.1:9876`, client `uvx mcp-for-blender` | `get_scene_info`, `execute_blender_code`, `get_viewport_screenshot`, Poly Haven, Hyper3D, Hunyuan |
| Official Blender Lab MCP | Blender 5.1+ addon, Claude connector | blend-file summaries, `execute_blender_code`, area screenshots, Python API lookup |
| Forks (blender-mcp-ultra, mcp-blender, atelier) | local addon + stdio proxy | typed room/light/material tools if present; else code execution |

## Connect

1. Call `search_connected_tools` for Blender scene, execute code, and screenshot.
2. If nothing is connected, ask the user to open the `.blend` in Blender and start the MCP addon. Do not invent a socket client.
3. Confirm the link with scene info or a one-line print: `import bpy; print(bpy.app.version_string)`.
4. Save a copy before the first edit: `bpy.ops.wm.save_as_mainfile(filepath=...)`.

Community addon default is localhost port 9876. Only one MCP client should own that socket. Safe mode blocks file and network calls inside `execute_blender_code`; if a chunk fails on `open(` or `urllib`, ask the user to turn safe mode off for that session or write files from the agent side.

## Execution rules

- Send generated chunks from `scripts/generate_shell.py` one file at a time. A full apartment in one payload times out.
- After each chunk, read the tool result. A silent success is not enough — call scene info or a screenshot.
- Viewport screenshot after the shell, after openings, and after every camera move.
- Undo is available on most servers. If a boolean explodes the mesh, undo once and switch that cutter to the FLOAT solver, already used by the generator.
- Poly Haven HDRIs and CC0 textures are preferred over generated bitmaps. Hyper3D / Hunyuan image-to-3D is only for a hero prop that cannot be built from primitives. Do not generate the whole apartment as one mesh.

## Code payload pattern

```python
import bpy
print(bpy.context.scene.name, len(bpy.data.objects))
```

Keep each payload under about 150 lines. Repeat helper functions in every chunk; MCP calls do not share locals across executions. Data-blocks in `bpy.data` do persist.
