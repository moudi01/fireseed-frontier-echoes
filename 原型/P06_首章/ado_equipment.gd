extends RefCounted

const SWORD_GRIP := Vector3(0, 0.078, -0.074)
const SHIELD_GRIP := Vector3(0, 0.080, -0.075)
const SHIELD_WRIST_ROLL := -1.21


static func attach(skeleton: Skeleton3D) -> bool:
	for bone in ["hand.R", "hand.L", "forearm.L"]:
		if skeleton.find_bone(bone) < 0:
			return false
	var stone := _material(Color("494b47"), 0.05)
	var iron := _material(Color("778184"), 0.32)
	var brass := _material(Color("aa8753"), 0.26)
	var leather := _material(Color("59432d"), 0.0)
	var left_bone := skeleton.find_bone("hand.L")
	var wrist_roll := Quaternion(Vector3.UP, SHIELD_WRIST_ROLL)
	var left := skeleton.get_bone_global_rest(left_bone)
	left.basis *= Basis(wrist_roll)
	skeleton.set_bone_pose_rotation(left_bone, skeleton.get_bone_pose_rotation(left_bone) * wrist_roll)
	var forearm := skeleton.get_bone_global_rest(skeleton.find_bone("forearm.L"))
	var normal := (forearm.basis.x * 0.93 - forearm.basis.z * 0.37).normalized()
	var spine := (left.origin - forearm.origin).slide(normal).normalized()
	var shield_mount := Transform3D(Basis(spine.cross(normal), spine, normal),
		forearm.origin.lerp(left.origin, 0.68) + normal * 0.232)
	var shield := _mount(skeleton, "forearm.L", forearm.affine_inverse() * shield_mount)
	shield.name = "DoorShield"
	_profile(shield, [Vector2(-0.31, -0.50), Vector2(-0.37, -0.33), Vector2(-0.37, 0.33),
		Vector2(-0.24, 0.48), Vector2(0.24, 0.48), Vector2(0.37, 0.33),
		Vector2(0.37, -0.34), Vector2(0.22, -0.50)], 0.082, stone)
	for x in [-0.26, 0.26]:
		_bar(shield, Vector3(x, 0, 0.083), Vector3(0.065, 0.83, 0.035), iron)
	_bar(shield, Vector3(0, 0.17, 0.092), Vector3(0.44, 0.10, 0.04), brass)
	_bar(shield, Vector3(0, -0.16, 0.092), Vector3(0.12, 0.48, 0.04), iron)
	_shield_bindings(shield, shield_mount.affine_inverse() * left,
		shield_mount.affine_inverse() * forearm.origin.lerp(left.origin, 0.28), iron, brass, leather)

	var blade_axis := Vector3(1, 0.20, 0).normalized()
	var blade_normal := Vector3.FORWARD
	var blade := _mount(skeleton, "hand.R",
		Transform3D(Basis(blade_axis.cross(blade_normal), blade_axis, blade_normal), SWORD_GRIP))
	blade.name = "CrossBlade"
	_profile(blade, [Vector2(-0.10, 0.19), Vector2(-0.12, 0.86), Vector2(0.13, 0.77),
		Vector2(0.20, 0.53), Vector2(0.13, 0.20)], 0.046, iron)
	_bar(blade, Vector3(0, 0.169, 0), Vector3(0.28, 0.056, 0.095), brass)
	_link(blade, Vector3(0, -0.164, 0), Vector3(0, 0.164, 0), 0.030, leather).name = "SwordGrip"
	_link(blade, Vector3(0, -0.185, 0), Vector3(0, -0.151, 0), 0.042, brass)
	_link(blade, Vector3(0, 0.142, 0), Vector3(0, 0.161, 0), 0.034, iron)
	_batch_parts(shield)
	_batch_parts(blade)
	return true


static func _batch_parts(attachment: Node3D) -> void:
	# Each part is rigid relative to this attachment. Keep one surface per material.
	var surfaces := {}
	for part: MeshInstance3D in attachment.get_children():
		var material := part.mesh.surface_get_material(0)
		if not surfaces.has(material):
			var surface := SurfaceTool.new()
			surface.begin(Mesh.PRIMITIVE_TRIANGLES)
			surfaces[material] = surface
		_append_part(surfaces[material], part)
		if part.name in ["SwordGrip", "ShieldGrip"]:
			part.mesh = null
		else:
			attachment.remove_child(part)
			part.queue_free()
	var mesh := ArrayMesh.new()
	for material: Material in surfaces:
		var surface: SurfaceTool = surfaces[material]
		surface.set_material(material)
		surface.index()
		surface.commit(mesh)
	var batch := MeshInstance3D.new()
	batch.mesh = mesh
	attachment.add_child(batch)


static func _append_part(surface: SurfaceTool, part: MeshInstance3D) -> void:
	var arrays := part.mesh.surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var indices: Variant = arrays[Mesh.ARRAY_INDEX]
	# The handmade profiles are unindexed; the stock bars and stems are indexed.
	var indexed: bool = indices != null and not indices.is_empty()
	var corners: int = indices.size() if indexed else vertices.size()
	var placement := part.transform
	for corner in range(corners):
		var index: int = indices[corner] if indexed else corner
		surface.set_normal(placement.basis * normals[index])
		surface.add_vertex(placement * vertices[index])


static func _shield_bindings(shield: Node3D, hand: Transform3D, arm: Vector3,
	iron: Material, brass: Material, leather: Material) -> void:
	var grip := hand * SHIELD_GRIP
	var bar := hand.basis.x.normalized() * 0.151
	_link(shield, grip - bar, grip + bar, 0.029, leather).name = "ShieldGrip"
	for stop in [grip - bar, grip + bar]:
		var anchor := Vector3(stop.x, stop.y, -0.076)
		_link(shield, stop, anchor, 0.025, iron)
		_bar(shield, anchor, Vector3(0.081, 0.092, 0.031), brass)
	# The rear strap wraps the forearm rather than hanging from the wrist.
	var previous := Vector3(arm.x - 0.133, arm.y, -0.076)
	for i in range(7):
		var angle := PI * float(i) / 6.0
		var point := arm + Vector3(-0.133 * cos(angle), 0.0, -0.115 * sin(angle))
		_strap_segment(shield, previous, point, leather)
		previous = point
	_strap_segment(shield, previous, Vector3(previous.x, previous.y, -0.076), leather)


static func _strap_segment(parent: Node3D, a: Vector3, b: Vector3, material: Material) -> void:
	var direction := (b - a).normalized()
	var fixed := Vector3.UP
	var node := _bar(parent, (a + b) * 0.5, Vector3(a.distance_to(b) + 0.008, 0.096, 0.026), material)
	node.basis = Basis(direction, fixed, direction.cross(fixed))


static func _mount(skeleton: Skeleton3D, name: String, local: Transform3D) -> Node3D:
	var attachment := BoneAttachment3D.new()
	attachment.bone_name = name
	skeleton.add_child(attachment)
	var item := Node3D.new()
	attachment.add_child(item)
	item.transform = local
	return item


static func _material(color: Color, metal: float) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.metallic = metal
	material.roughness = 0.77
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material


static func _bar(parent: Node3D, at: Vector3, extent: Vector3, material: Material) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = extent
	mesh.material = material
	var node := MeshInstance3D.new()
	node.mesh = mesh
	parent.add_child(node)
	node.position = at
	return node


static func _link(parent: Node3D, a: Vector3, b: Vector3, radius: float, material: Material) -> MeshInstance3D:
	var mesh := CylinderMesh.new()
	mesh.height = a.distance_to(b)
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.radial_segments = 12
	mesh.rings = 1
	mesh.material = material
	var node := MeshInstance3D.new()
	node.mesh = mesh
	parent.add_child(node)
	node.position = (a + b) * 0.5
	node.quaternion = Quaternion(Vector3.UP, (b - a).normalized())
	return node


static func _profile(parent: Node3D, list: Array, depth: float, material: Material) -> void:
	var points := PackedVector2Array(list)
	var triangles := Geometry2D.triangulate_polygon(points)
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(0, triangles.size(), 3):
		for j in [0, 2, 1]:
			var front := points[triangles[i + j]]
			surface.add_vertex(Vector3(front.x, front.y, depth))
		for j in [0, 1, 2]:
			var back := points[triangles[i + j]]
			surface.add_vertex(Vector3(back.x, back.y, -depth))
	for i in range(points.size()):
		var a := points[i]
		var b := points[(i + 1) % points.size()]
		for v in [Vector3(a.x, a.y, depth), Vector3(b.x, b.y, -depth), Vector3(b.x, b.y, depth),
			Vector3(a.x, a.y, depth), Vector3(a.x, a.y, -depth), Vector3(b.x, b.y, -depth)]:
			surface.add_vertex(v)
	surface.generate_normals()
	surface.set_material(material)
	var node := MeshInstance3D.new()
	node.mesh = surface.commit()
	parent.add_child(node)
