"""Bake a fixed equipment grip into a copy of the MG01 bind mesh."""

from pathlib import Path
import json
import struct

import numpy as np


HERE = Path(__file__).resolve().parent
HINGE = {"hand.R": 0.052, "hand.L": 0.055}
CURL_RADIUS = 0.057
CURL_CENTER = -0.074


def accessor(document, data, index, dtype, columns):
    record = document["accessors"][index]
    view = document["bufferViews"][record["bufferView"]]
    assert "sparse" not in record and "byteStride" not in view and view["buffer"] == 0
    return np.frombuffer(
        data, dtype=dtype, count=record["count"] * columns,
        offset=view.get("byteOffset", 0) + record.get("byteOffset", 0),
    ).reshape(-1, columns)


def form_grip(points, normals, bind, weights, hinge):
    # In both wrists +Y follows the fingers, +Z points through the knuckles
    # and X runs across the fingers. Fold the fingers under the palm.
    local = points @ bind[:3, :3].T + bind[:3, 3]
    finger = (local[:, 1] > hinge) & (weights > 0.52)
    before = local[finger]
    # The curled arc starts gradually at the knuckles to avoid a hard crease.
    distance = before[:, 1] - hinge
    angle = distance / CURL_RADIUS
    distance_from_center = before[:, 2] - CURL_CENTER
    curved = before.copy()
    curved[:, 1] = hinge + distance_from_center * np.sin(angle)
    curved[:, 2] = CURL_CENTER + distance_from_center * np.cos(angle)
    blend = np.clip(distance / 0.020, 0, 1)
    blend = blend * blend * (3 - 2 * blend)
    blend *= np.clip((weights[finger] - 0.52) / 0.38, 0, 1)
    after = before + (curved - before) * blend[:, None]
    assert len(before) > 500 and np.max(np.linalg.norm(after - before, axis=1)) < 0.14
    unbind = np.linalg.inv(bind)
    points[finger] = after @ unbind[:3, :3].T + unbind[:3, 3]

    # Turn the existing smooth normals with the edited finger surface.
    local_normals = normals[finger] @ bind[:3, :3].T
    ny, nz = local_normals[:, 1].copy(), local_normals[:, 2].copy()
    turn = angle * blend
    local_normals[:, 1] = ny * np.cos(turn) + nz * np.sin(turn)
    local_normals[:, 2] = -ny * np.sin(turn) + nz * np.cos(turn)
    turned = local_normals @ unbind[:3, :3].T
    normals[finger] = turned / np.linalg.norm(turned, axis=1)[:, None]
    return len(before)


def main():
    source = (HERE / "MG01_skinned.glb").read_bytes()
    magic, version, _ = struct.unpack_from("<4sII", source)
    json_length, json_type = struct.unpack_from("<I4s", source, 12)
    binary_length, binary_type = struct.unpack_from("<I4s", source, 20 + json_length)
    assert (magic, version, json_type, binary_type) == (b"glTF", 2, b"JSON", b"BIN\0")
    data = bytearray(source[28 + json_length:])
    assert len(data) == binary_length
    document = json.loads(source[20:20 + json_length])
    node = next(row for row in document["nodes"] if row.get("name") == "SK_MG01")
    skin = document["skins"][node["skin"]]
    primitive, = document["meshes"][node["mesh"]]["primitives"]
    attributes = primitive["attributes"]
    vertices = accessor(document, data, attributes["POSITION"], "<f4", 3)
    normals = accessor(document, data, attributes["NORMAL"], "<f4", 3)
    joints = accessor(document, data, attributes["JOINTS_0"], "u1", 4)
    weights = accessor(document, data, attributes["WEIGHTS_0"], "<f4", 4)
    inverse_binds = accessor(document, data, skin["inverseBindMatrices"], "<f4", 16)
    for name, hinge in HINGE.items():
        slot = next(
            slot for slot, joint in enumerate(skin["joints"])
            if document["nodes"][joint]["name"] == name
        )
        hand_weights = np.sum(weights * (joints == slot), axis=1)
        bind = inverse_binds[slot].reshape(4, 4, order="F")
        print(f"{name}: {form_grip(vertices, normals, bind, hand_weights, hinge)} vertices")
    bounds = document["accessors"][attributes["POSITION"]]
    bounds["min"], bounds["max"] = vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()
    metadata = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    metadata += b" " * (-len(metadata) % 4)
    total = 28 + len(metadata) + len(data)
    output = (struct.pack("<4sII", magic, version, total)
              + struct.pack("<I4s", len(metadata), json_type) + metadata
              + struct.pack("<I4s", len(data), binary_type) + data)
    (HERE / "MG01_grip.glb").write_bytes(output)


if __name__ == "__main__":
    main()
