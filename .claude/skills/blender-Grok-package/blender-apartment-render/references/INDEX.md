---
description: "Knowledge graph index for blender-apartment-render. Start here when choosing which reference to load."
connections: [mcp-connection, measurement-intake, shell-and-openings, photo-match, photoreal, materials]
---

# Apartment Render Knowledge Graph

## Core Concepts

- [[measurement-intake]] — turn blueprints and photos into a metric manifest before touching Blender
- [[mcp-connection]] — find the Blender MCP tools, send code in chunks, and recover from a dead socket
- [[shell-and-openings]] — walls, slabs, doors, and windows from the manifest
- [[photo-match]] — place cameras and reference images so a still can be compared to a photo
- [[photoreal]] — Cycles, AgX, portals, and the preview-then-final loop
- [[materials]] — Principled BSDF starting points that do not read as plastic

## Suggested path

1. Read [[measurement-intake]] until the manifest validates.
2. Read [[mcp-connection]] and confirm a live Blender session.
3. Generate the shell, then read [[shell-and-openings]] only if boolean cuts fail.
4. Read [[photo-match]] before claiming a view matches a photograph.
5. Read [[photoreal]] and [[materials]] before the final stills.
