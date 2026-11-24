"""Build standardized static meshes from the Fireseed high-poly character set."""

import argparse
import json
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix

PROCESS_VERSION = 2

# Working stature in engine units. For hats, the added clearance is included
# in the bounds so the body is not made shorter to fit the tip of the hat.
HEIGHTS = {
    "L01": 1.75, "L02": 1.79,
    "S01-M": 1.80, "S01-F": 1.73, "S02-M": 1.79, "S02-F": 1.73,
    "S03-M": 1.77, "S03-F": 1.72,
    "M01": 1.84, "M02": 1.69, "M03": 1.76, "M04": 1.76,
    "M05": 1.72, "M06": 1.79, "M07": 1.73, "M08": 1.78,
    "H01": 1.81, "H02": 1.73, "H03": 1.70, "H04": 1.75,
    "H05": 1.87, "H06": 1.77, "H07": 1.82, "H08": 1.80,
    "H09": 1.75, "H10": 1.68, "H11": 1.81, "H12": 1.94,
}


def material_for(body, provider):
    old = body.data.materials[0]
    old_shader = next(node for node in old.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    source = old_shader.inputs["Base Color"].links[0].from_node.image
    source.scale(2048, 2048)

    # Adjust the overall cast gently in sRGB. Keep highlights, shadows, and
    # distinctive color blocks from the source artwork.
    values = np.empty(2048 * 2048 * 4, dtype=np.float32)
    source.pixels.foreach_get(values)
    rgb = values.reshape(-1, 4)[:, :3]
    if source.colorspace_settings.name != "sRGB":
        raise ValueError(f"Unexpected base color space: {source.colorspace_settings.name}")
    balance = np.array((1.015, 1.005, 0.99) if provider == "Meshy" else (0.98, 1.004, 1.023))
    # The weight vanishes at black and white, preventing clipping and keeping
    # cream trim from taking on the platform's corrective tint.
    rgb[:] = rgb + (balance - 1.0) * rgb * (1.0 - rgb)
    source.pixels.foreach_set(values)
    source.update()
    source.pack()
    source.name = "BaseColor_2K"

    mat = bpy.data.materials.new("Fireseed_Character")
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Metallic"].default_value = 0.0
    shader.inputs["Roughness"].default_value = 0.85
    color = mat.node_tree.nodes.new("ShaderNodeTexImage")
    color.image = source
    mat.node_tree.links.new(color.outputs["Color"], shader.inputs["Base Color"])
    mat.node_tree.nodes.active = color
    body.data.materials.clear()
    body.data.materials.append(mat)


def build(source, destination, code, provider, budget):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    body, = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    vertices = len(body.data.vertices)
    faces = len(body.data.polygons)
    body.data.transform(body.matrix_world.copy())
    body.parent = None
    body.matrix_world = Matrix.Identity(4)
    body.name = f"{code}_Body"
    body.data.name = body.name
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)

    # glTF splits coincident vertices at texture seams. Restore the shared
    # geometry before collapse to keep those seams from cracking open.
    mesh_edit = bmesh.new()
    mesh_edit.from_mesh(body.data)
    bmesh.ops.remove_doubles(mesh_edit, verts=list(mesh_edit.verts), dist=0.000001)
    mesh_edit.to_mesh(body.data)
    mesh_edit.free()

    reduction = body.modifiers.new("Reduce mesh", "DECIMATE")
    reduction.ratio = min(1.0, budget / faces)
    bpy.ops.object.modifier_apply(modifier=reduction.name)

    coordinates = np.empty(len(body.data.vertices) * 3, dtype=np.float32)
    body.data.vertices.foreach_get("co", coordinates)
    xyz = coordinates.reshape(-1, 3)
    low, high = xyz.min(axis=0), xyz.max(axis=0)
    # Center the horizontal footprint and move the lowest vertex onto the
    # ground. Blender's -Y front exports to glTF's +Z front.
    center = (low + high) * 0.5
    center[2] = low[2]
    xyz[:] = (xyz - center) * (HEIGHTS[code] / float(high[2] - low[2]))
    body.data.vertices.foreach_set("co", coordinates)
    body.data.update()
    material_for(body, provider)
    body.data.calc_loop_triangles()
    triangles = len(body.data.loop_triangles)
    if triangles > budget or triangles < 1:
        raise ValueError(f"{code}: {triangles} triangles with target {budget}")
    bpy.ops.export_scene.gltf(
        filepath=str(destination), export_format="GLB", use_selection=True,
        export_animations=False, export_image_format="JPEG", export_jpeg_quality=92,
    )
    return {
        "process_version": PROCESS_VERSION,
        "character": code, "provider": provider, "source": source.name,
        "file": destination.name, "source_vertices": vertices, "source_faces": faces,
        "triangles": triangles, "height": HEIGHTS[code], "budget": budget,
        "bytes": destination.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--pattern", default="*.glb")
    parser.add_argument("--existing-male", type=Path)
    parser.add_argument("--partition", type=int, choices=range(3))
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.destination.mkdir(parents=True, exist_ok=True)
    sources = [(path, *path.stem.split("_")) for path in sorted(args.source.glob(args.pattern))]
    if args.existing_male:
        sources.append((args.existing_male, "L02", "Tripo"))
    if args.partition is not None:
        sources = sources[args.partition::3]
    if not sources:
        parser.error("No input GLBs")

    for source, code, provider in sources:
        target = args.destination / f"{code}_{provider}.glb"
        report = target.with_suffix(".json")
        if (target.is_file() and report.is_file()
                and json.loads(report.read_text(encoding="utf-8")).get("process_version") == PROCESS_VERSION):
            continue
        tmp = target.with_suffix(".building.glb")
        budget = 14200 if code.startswith("L") else 12000
        try:
            result = build(source, tmp, code, provider, budget)
            tmp.replace(target)
            result["file"] = target.name
            report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("CHARACTER", json.dumps(result), flush=True)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise


if __name__ == "__main__":
    main()
