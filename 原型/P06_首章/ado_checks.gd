extends Node

const Actor = preload("res://ado_actor.gd")
const Stage = preload("res://shield_stage.gd")
const Gear = preload("res://ado_equipment.gd")
const BINDINGS := {
	"SwordGrip": ["hand.R", Gear.SWORD_GRIP, 0.030],
	"ShieldGrip": ["hand.L", Gear.SHIELD_GRIP, 0.029],
}

var actor: Node3D
var body: MeshInstance3D
var grips: Dictionary = {}
var camera: Camera3D
var viewport: SubViewport
var largest_offset := 0.0
var skin_contacts: Dictionary = {}
var checked_poses := 0


func verify(app: Control, capture: bool) -> String:
	var panel := SubViewportContainer.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	panel.stretch = true
	app.add_child(panel)
	viewport = SubViewport.new()
	viewport.own_world_3d = true
	panel.add_child(viewport)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var fill := WorldEnvironment.new()
	fill.environment = Environment.new()
	fill.environment.background_mode = Environment.BG_COLOR
	fill.environment.background_color = Color("252c2a")
	fill.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	fill.environment.ambient_light_color = Color("ebddc8")
	fill.environment.ambient_light_energy = 0.76
	viewport.add_child(fill)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-44, -18, 0)
	sun.light_energy = 1.17
	sun.light_color = Color("ffe6bb")
	viewport.add_child(sun)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	viewport.add_child(camera)
	actor = Actor.new()
	viewport.add_child(actor)
	if not actor.assemble(load(Stage.FORTRESS + Stage.ADO_ASSET)):
		return "The exported Ado grip model failed to assemble"
	body = actor.model.find_child("SK_MG01", true, false)
	for id in BINDINGS:
		grips[id] = actor.skeleton.find_child(id, true, false)
		if grips[id] == null:
			return "Missing geometry for " + id
	if body == null:
		return "The Ado skin mesh is missing"

	for name in actor.POSES:
		if name == "fallen":
			continue
		actor._pose(name)
		if not await _check_pose():
			return "Ado's grip drifted in " + name
		if name in ["MG01-B", "brace"]:
			var shield: Node3D = actor.skeleton.find_child("DoorShield", true, false)
			if shield.global_basis.z.normalized().dot(Vector3.BACK) < 0.6:
				return "The guard pose did not present the shield face"
	# Exercise the same interpolation used by the real windup, release and recovery.
	for move in actor.RELEASES:
		var ready: Array[Quaternion] = actor._orientations("ready")
		var windup: Array[Quaternion] = actor._orientations(move)
		var release: Array[Quaternion] = actor._orientations(actor.RELEASES[move])
		for pair in [[ready, windup], [windup, release], [release, ready]]:
			for i in range(1, 8):
				actor._set_bones(float(i) / 8.0, pair[0], pair[1])
				if not await _check_pose():
					return "Ado's grip drifted during " + move
	actor.snap(Vector3.ZERO, 0.0, true, true)
	if not await _check_pose():
		return "Ado's grip drifted when falling"

	actor.snap(Vector3.ZERO, 0.0, false, true)
	await get_tree().process_frame
	if DisplayServer.get_name() != "headless":
		var baked := body.bake_mesh_from_current_skeleton_pose()
		if baked == null:
			return "Cannot inspect the skinned hand surface"
		for id in grips:
			var count := _contact_vertices(baked, grips[id], BINDINGS[id][2])
			if count < 12:
				return "The glove surface did not meet " + id
			skin_contacts[id] = count
	if capture:
		var sword: Node3D = grips.SwordGrip
		var shield_handle: Node3D = grips.ShieldGrip
		var left_elbow: Transform3D = actor.skeleton.get_bone_global_pose(actor.skeleton.find_bone("forearm.L"))
		if not await _capture(app, "横刃握柄", sword.global_position, Vector3(-0.30, 0.12, 1.0), 0.70):
			return "Could not capture the sword grip"
		if not await _capture(app, "门盾握把与臂带", shield_handle.global_position.lerp(actor.skeleton.to_global(left_elbow.origin), 0.35),
			Vector3(0.32, 0.20, -1.0), 0.86):
			return "Could not capture the shield bindings"
		actor._pose("brace")
		if not await _capture(app, "壁垒架盾", Vector3(0, 1.60, 0), Vector3(-0.25, 0.22, 1.0), 2.95):
			return "Could not capture the guard"
	panel.queue_free()
	return ""


func _check_pose() -> bool:
	actor.skeleton.force_update_all_bone_transforms()
	await get_tree().process_frame
	for id in BINDINGS:
		var row: Array = BINDINGS[id]
		var hand: Transform3D = actor.skeleton.get_bone_global_pose(actor.skeleton.find_bone(row[0]))
		var expected: Vector3 = actor.skeleton.to_global(hand * row[1])
		largest_offset = maxf(largest_offset, expected.distance_to(grips[id].global_position))
		if largest_offset > 0.0005:
			return false
	checked_poses += 1
	return true


func _contact_vertices(baked: ArrayMesh, grip: Node3D, radius: float) -> int:
	var count := 0
	var to_grip := grip.global_transform.affine_inverse() * body.global_transform
	for surface in range(baked.get_surface_count()):
		var vertices: PackedVector3Array = baked.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX]
		for vertex in vertices:
			var point := to_grip * vertex
			if absf(point.y) < 0.125 and absf(Vector2(point.x, point.z).length() - radius) < 0.008:
				count += 1
	return count


func _capture(app: Control, mark: String, center: Vector3, direction: Vector3, extent: float) -> bool:
	camera.size = extent
	camera.position = center + direction * 5.0
	camera.look_at(center)
	await RenderingServer.frame_post_draw
	return viewport.get_texture().get_image().save_png(app.data_dir.path_join(app.case_name + "." + mark + ".png")) == OK
