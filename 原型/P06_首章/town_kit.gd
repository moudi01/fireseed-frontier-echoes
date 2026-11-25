extends RefCounted

const TOWN_ASSET_PATHS := {
	"town-muster": "res://assets/town/SM_Town_Muster.glb",
	"town-store": "res://assets/town/SM_Town_Store.glb",
	"town-gate": "res://assets/town/SM_Town_Gate.glb",
}

static var _scenes: Dictionary = {}
static var _ink_pass: StandardMaterial3D
static var _glass_material: StandardMaterial3D


static func supports(kind: String) -> bool:
	return TOWN_ASSET_PATHS.has(kind)


static func piece(kind: String) -> Node3D:
	if not TOWN_ASSET_PATHS.has(kind):
		return null
	var path: String = TOWN_ASSET_PATHS[kind]
	if not _scenes.has(path):
		if ResourceLoader.exists(path):
			_scenes[path] = load(path) as PackedScene
		else:
			_scenes[path] = null
	var packed: PackedScene = _scenes.get(path)
	if packed == null:
		return null
	var root := packed.instantiate() as Node3D
	if root == null:
		return null
	_tune_materials(root)
	return root


static func _tune_materials(node: Node) -> void:
	if node is MeshInstance3D:
		var mi := node as MeshInstance3D
		var mesh := mi.mesh
		if mesh != null:
			for surf in range(mesh.get_surface_count()):
				var mat := mesh.surface_get_material(surf)
				if mat != null and mat.resource_name.contains("LanternGlass"):
					mi.set_surface_override_material(surf, _get_glass_material())
				elif mat is StandardMaterial3D:
					var std := (mat as StandardMaterial3D).duplicate() as StandardMaterial3D
					std.roughness = 0.90
					std.metallic = 0.0
					std.albedo_color = Color("fff6e8")
					# Subtle warm shadow lift + crisp frontier ink contour via next_pass
					std.emission_enabled = true
					std.emission = Color("3b2e21")
					std.emission_energy_multiplier = 0.22
					std.next_pass = _get_ink_pass()
					mi.set_surface_override_material(surf, std)
	for child in node.get_children():
		_tune_materials(child)


static func _get_ink_pass() -> StandardMaterial3D:
	if _ink_pass == null:
		_ink_pass = StandardMaterial3D.new()
		_ink_pass.albedo_color = Color("362a21")
		_ink_pass.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_ink_pass.cull_mode = BaseMaterial3D.CULL_FRONT
		_ink_pass.grow = true
		_ink_pass.grow_amount = 0.015
	return _ink_pass


static func _get_glass_material() -> StandardMaterial3D:
	if _glass_material == null:
		_glass_material = StandardMaterial3D.new()
		_glass_material.albedo_color = Color("f6cc88")
		_glass_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return _glass_material
