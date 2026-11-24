extends Node3D

var model: Node3D
var leaves: Array[Node3D] = []
var leaf_rest: Array[Basis] = []
var materials: Array[StandardMaterial3D] = []
var colors: Array[Color] = []
var destination: Vector3
var heading := 0.0
var reduced := false
var fallen := false
var winding := false
var age := 0.0
var pulse_left := 0.0
var impact_left := 0.0
var applied_tone := Color.TRANSPARENT
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
	for index in range(core.mesh.get_surface_count()):
		var source := core.get_active_material(index) as StandardMaterial3D
		if source != null:
			var material := source.duplicate() as StandardMaterial3D
			core.set_surface_override_material(index, material)
			materials.append(material)
			colors.append(material.albedo_color)
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
	var tone := Color("a39b8a") if fallen else Color("ffc4a5") if impact_left > 0.0 else Color("ffd496") if winding else Color.WHITE
	if tone != applied_tone:
		applied_tone = tone
		for index in range(materials.size()):
			materials[index].albedo_color = colors[index] * tone
	for index in range(leaves.size()):
		var angle := -0.10 if fallen or winding else 0.0
		if not fallen and not reduced:
			if pulse_left > 0.0:
				angle = sin(pulse_left / 0.28 * PI) * 0.18
			elif not winding:
				angle = sin(age * 2.0 + float(index) * 1.2) * 0.012
		leaves[index].basis = leaf_rest[index] * Basis(Vector3.RIGHT, angle)
