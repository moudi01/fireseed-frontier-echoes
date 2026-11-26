class_name CitadelRingKit
extends RefCounted

## Shared 3D terrain prop kit for CITADEL_RING (90 cells, used by both DEMON and ADMIN finale battles).
## - citadel-pillar (HIGH_OBSTACLE [2,4],[3,4]): tall basalt-and-bronze ring monolith
## - citadel-plinth (LOW_OBSTACLE [2,3],[5,3]): low carved stone-and-bronze barrier plinth
## - citadel-dais   (HIGH_GROUND  [0,4],[5,4]): stepped pale-limestone elevated ring platform

const ASSETS := ["citadel-pillar", "citadel-plinth", "citadel-dais"]


static func supports(asset_name: String) -> bool:
	return asset_name in ASSETS


static func piece(asset_name: String) -> Node3D:
	var root := Node3D.new()
	root.name = asset_name
	var mat_stone := _mat(Color(0.36, 0.35, 0.34), 0.78)
	var mat_light := _mat(Color(0.68, 0.66, 0.61), 0.80)
	var mat_bronze := _mat(Color(0.66, 0.48, 0.28), 0.45)

	match asset_name:
		"citadel-pillar":
			_box(root, Vector3(0.70, 0.20, 0.70), Vector3(0.0, 0.10, 0.0), mat_stone)
			_box(root, Vector3(0.54, 1.38, 0.54), Vector3(0.0, 0.89, 0.0), mat_stone)
			_box(root, Vector3(0.60, 0.10, 0.60), Vector3(0.0, 1.18, 0.0), mat_bronze)
			_box(root, Vector3(0.66, 0.16, 0.66), Vector3(0.0, 1.66, 0.0), mat_light)
		"citadel-plinth":
			_box(root, Vector3(0.76, 0.16, 0.66), Vector3(0.0, 0.08, 0.0), mat_stone)
			_box(root, Vector3(0.68, 0.36, 0.56), Vector3(0.0, 0.34, 0.0), mat_stone)
			_box(root, Vector3(0.72, 0.08, 0.60), Vector3(0.0, 0.54, 0.0), mat_bronze)
		"citadel-dais":
			_box(root, Vector3(0.92, 0.14, 0.86), Vector3(0.0, 0.07, 0.0), mat_stone)
			_box(root, Vector3(0.84, 0.16, 0.78), Vector3(0.0, 0.22, 0.0), mat_light)
			_box(root, Vector3(0.86, 0.04, 0.80), Vector3(0.0, 0.31, 0.0), mat_bronze)
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
