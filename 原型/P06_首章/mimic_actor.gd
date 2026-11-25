extends Node3D

const MIMIC_SCALE := Vector3(1.26, 1.55, 1.26)

var model: Node3D
var leaves: Array[Node3D] = []
var leaf_rest: Array[Basis] = []
var materials: Array[StandardMaterial3D] = []
var core_materials: Array[StandardMaterial3D] = []
var outline_material: StandardMaterial3D
var colors: Array[Color] = []
var base_tints: Array[Color] = []
var destination: Vector3
var heading := 0.0
var reduced := false
var fallen := false
var winding := false
var age := 0.0
var pulse_left := 0.0
var impact_left := 0.0
var applied_tone := Color.TRANSPARENT
var applied_winding := false
var applied_fallen := false
var motion: Tween


func assemble(scene: PackedScene) -> bool:
	model = scene.instantiate() as Node3D
	add_child(model)
	var core := model.find_child("Core", true, false) as MeshInstance3D
	if core == null:
		return false
	for index in range(1, 6):
		var leaf := model.find_child("LeafPalm_%02d" % index, true, false) as Node3D
		if leaf == null:
			return false
		leaves.append(leaf)
		leaf_rest.append(leaf.basis)
	outline_material = StandardMaterial3D.new()
	outline_material.cull_mode = BaseMaterial3D.CULL_FRONT
	outline_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	outline_material.grow = true
	outline_material.grow_amount = 0.022
	outline_material.albedo_color = Color("1d1510")
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := node as MeshInstance3D
		if mesh_instance == null or mesh_instance.mesh == null:
			continue
		var is_core := mesh_instance == core
		for index in range(mesh_instance.mesh.get_surface_count()):
			var source := mesh_instance.get_active_material(index) as StandardMaterial3D
			if source == null:
				continue
			var material := source.duplicate() as StandardMaterial3D
			material.rim_enabled = true
			material.rim = 0.32
			material.rim_tint = 0.45
			material.next_pass = outline_material
			mesh_instance.set_surface_override_material(index, material)
			materials.append(material)
			colors.append(material.albedo_color)
			var tint := Color.WHITE
			if material.albedo_texture != null:
				tint = Color("e8d2b0") if is_core else Color("b6d4a4")
			base_tints.append(tint)
			if is_core:
				core_materials.append(material)
	scale = MIMIC_SCALE
	return true


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	if motion != null and motion.is_valid():
		motion.kill()
	position = point
	destination = point
	rotation.y = yaw
	heading = yaw
	fallen = down
	reduced = still
	pulse_left = 0.0
	impact_left = 0.0
	model.scale = Vector3(1, 0.22, 1) if fallen else Vector3.ONE
	_update_pose()


func travel(point: Vector3, yaw: float) -> void:
	if fallen:
		return
	if motion != null and motion.is_valid():
		motion.kill()
	destination = point
	heading = yaw
	motion = create_tween()
	motion.tween_property(self, "position", point, 0.23)
	motion.parallel().tween_property(self, "rotation:y", rotation.y + angle_difference(rotation.y, yaw), 0.10)


func set_winding(value: bool) -> void:
	winding = value
	_update_pose()


func pulse() -> void:
	if not fallen and not reduced:
		pulse_left = 0.28


func impact() -> void:
	if not fallen:
		impact_left = 0.16


func _process(delta: float) -> void:
	if model == null or fallen:
		return
	age += delta
	pulse_left = maxf(0.0, pulse_left - delta)
	impact_left = maxf(0.0, impact_left - delta)
	_update_pose()


func _update_pose() -> void:
	var tone := Color("7e7b74") if fallen else Color("ffd0b2") if impact_left > 0.0 else Color("ffcf86") if winding else Color.WHITE
	if tone != applied_tone or winding != applied_winding or fallen != applied_fallen:
		applied_tone = tone
		applied_winding = winding
		applied_fallen = fallen
		for index in range(materials.size()):
			var base_tint := Color.WHITE if fallen or index >= base_tints.size() else base_tints[index]
			materials[index].albedo_color = colors[index] * base_tint * tone
		for material in core_materials:
			var glow := winding and not fallen
			material.emission_enabled = glow
			if glow:
				material.emission = Color("a85b22")
				material.emission_energy_multiplier = 0.75
		if outline_material != null:
			outline_material.albedo_color = Color("5c5850") if fallen else Color("4a1f0e") if winding else Color("1c140e")
	for index in range(leaves.size()):
		var angle := -0.10 if fallen else -0.14 if winding else 0.0
		if not fallen and not reduced:
			if pulse_left > 0.0:
				angle = sin(pulse_left / 0.28 * PI) * 0.22
			elif not winding:
				angle = sin(age * 2.0 + float(index) * 1.2) * 0.022
		leaves[index].basis = leaf_rest[index] * Basis(Vector3.RIGHT, angle)
