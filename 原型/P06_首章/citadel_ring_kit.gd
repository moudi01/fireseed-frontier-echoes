class_name CitadelRingKit
extends RefCounted

## Shared 3D terrain prop kit for CITADEL_RING (90 cells, used by both DEMON and ADMIN finale battles).
## Styled in P04B warm borderland storybook sandstone, weathered umber stone, and aged bronze trim:
## - citadel-pillar (HIGH_OBSTACLE [2,4],[3,4]): stepped weathered sandstone monolith with bronze ring bands
## - citadel-plinth (LOW_OBSTACLE [2,3],[5,3]): carved warm-stone barrier plinth with threshold cap & wear lip
## - citadel-dais   (HIGH_GROUND  [0,4],[5,4]): tiered sandstone platform with warm bronze edge inlay

const ASSETS := ["citadel-pillar", "citadel-plinth", "citadel-dais"]


static func supports(asset_name: String) -> bool:
	return asset_name in ASSETS


static func piece(asset_name: String) -> Node3D:
	var root := Node3D.new()
	root.name = asset_name
	var mat_umber := _mat(Color(0.39, 0.34, 0.29), 0.82)
	var mat_sand := _mat(Color(0.64, 0.57, 0.48), 0.78)
	var mat_cap := _mat(Color(0.75, 0.69, 0.59), 0.74)
	var mat_bronze := _mat(Color(0.71, 0.52, 0.29), 0.42)

	match asset_name:
		"citadel-pillar":
			# Stepped weathered base + fluted sandstone shaft + twin bronze collar bands + stepped cornice
			_box(root, Vector3(0.78, 0.14, 0.78), Vector3(0.0, 0.07, 0.0), mat_umber)
			_box(root, Vector3(0.66, 0.16, 0.66), Vector3(0.0, 0.22, 0.0), mat_sand)
			_box(root, Vector3(0.54, 1.24, 0.54), Vector3(0.0, 0.92, 0.0), mat_umber)
			_box(root, Vector3(0.60, 0.08, 0.60), Vector3(0.0, 0.72, 0.0), mat_bronze)
			_box(root, Vector3(0.60, 0.10, 0.60), Vector3(0.0, 1.26, 0.0), mat_bronze)
			_box(root, Vector3(0.68, 0.14, 0.68), Vector3(0.0, 1.61, 0.0), mat_cap)
		"citadel-plinth":
			# Weathered threshold base + warm stone core + bronze trim strip + bevelled sandstone slab cap
			_box(root, Vector3(0.82, 0.14, 0.70), Vector3(0.0, 0.07, 0.0), mat_umber)
			_box(root, Vector3(0.72, 0.30, 0.58), Vector3(0.0, 0.29, 0.0), mat_sand)
			_box(root, Vector3(0.76, 0.06, 0.62), Vector3(0.0, 0.47, 0.0), mat_bronze)
			_box(root, Vector3(0.78, 0.09, 0.64), Vector3(0.0, 0.545, 0.0), mat_cap)
		"citadel-dais":
			# Two-tier stepped sandstone platform with warm bronze perimeter trim
			_box(root, Vector3(0.96, 0.12, 0.90), Vector3(0.0, 0.06, 0.0), mat_umber)
			_box(root, Vector3(0.88, 0.14, 0.82), Vector3(0.0, 0.19, 0.0), mat_sand)
			_box(root, Vector3(0.90, 0.04, 0.84), Vector3(0.0, 0.28, 0.0), mat_bronze)
			_box(root, Vector3(0.82, 0.05, 0.76), Vector3(0.0, 0.325, 0.0), mat_cap)
	return root


static func _mat(color: Color, roughness: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	return m


static func _box(parent: Node3D, size: Vector3, pos: Vector3, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.position = pos
	mi.material_override = mat
	parent.add_child(mi)
