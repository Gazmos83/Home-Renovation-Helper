"""Small real models for the model-library tests: a box as GLB, a glTF zip and an OBJ zip."""

from __future__ import annotations

import io
import json
import struct
import zipfile

from tests.blender_fakes import png_bytes

# A box 0.9 × 0.8 × 1.0 m (x, y, z), 8 corners and 12 triangles, standing on z = 0.
SIZE = (0.9, 0.8, 1.0)
_CORNERS = [(x, y, z) for z in (0.0, SIZE[2]) for y in (0.0, SIZE[1]) for x in (0.0, SIZE[0])]
_FACES = [
    (0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
    (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5),
]


def _gltf(buffer_uri: str | None) -> tuple[dict, bytes]:
    """glTF's Y is up: the box's z height becomes y, its y depth becomes -z."""
    positions = b"".join(struct.pack("<3f", x, z, -y) for x, y, z in _CORNERS)
    indices = b"".join(struct.pack("<3H", *face) for face in _FACES)
    data = positions + indices
    buffer = {"byteLength": len(data)}
    if buffer_uri is not None:
        buffer["uri"] = buffer_uri
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "Box"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [buffer],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
            {"buffer": 0, "byteOffset": len(positions), "byteLength": len(indices)},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
             "min": [0.0, 0.0, -SIZE[1]], "max": [SIZE[0], SIZE[2], 0.0]},
            {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"},
        ],
    }
    return document, data


def glb(extra: dict | None = None, version: int = 2) -> bytes:
    document, data = _gltf(None)
    document.update(extra or {})
    chunk = json.dumps(document).encode("utf-8")
    chunk += b" " * (-len(chunk) % 4)
    data += b"\x00" * (-len(data) % 4)
    body = struct.pack("<II", len(chunk), 0x4E4F534A) + chunk + struct.pack("<II", len(data), 0x004E4942) + data
    return struct.pack("<4sII", b"glTF", version, 12 + len(body)) + body


def zipped(entries: dict[str, bytes | str]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content if isinstance(content, bytes) else content.encode("utf-8"))
    return out.getvalue()


def gltf_zip(image_uri: str | None = None) -> bytes:
    document, data = _gltf("box.bin")
    entries: dict[str, bytes | str] = {"box.bin": data}
    if image_uri is not None:
        document["images"] = [{"uri": image_uri}]
    document_text = json.dumps(document)
    entries["box.gltf"] = document_text
    return zipped(entries)


def obj_text(mtllib: str = "box.mtl") -> str:
    lines = [f"mtllib {mtllib}", "o Box"]
    lines += [f"v {x} {z} {-y}" for x, y, z in _CORNERS]  # OBJ is Y-up as well
    lines.append("usemtl Wood")
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in _FACES]
    return "\n".join(lines) + "\n"


def obj_zip(*, mtl: bool = True, texture: str = "wood.png") -> bytes:
    entries: dict[str, bytes | str] = {"box.obj": obj_text()}
    if mtl:
        entries["box.mtl"] = f"newmtl Wood\nKd 0.6 0.4 0.2\nmap_Kd {texture}\n"
    entries["wood.png"] = png_bytes(4, 4)
    return zipped(entries)
