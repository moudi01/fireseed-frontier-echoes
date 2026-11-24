extends Node3D
## Pure presentation. Inputs are snapshots in the Board's local coordinate system.
## The Board owns advancement, pause, visibility and removal; no target tracking.
var age: float = 0.0
var duration: float = 0.22
var finished: bool = false
var kind: String = "hit"
var from: Vector3 = Vector3.ZERO
var to: Vector3 = Vector3.ZERO
var tint: Color = Color("f3d9a0")
var parts: Array[MeshInstance3D] = []
var materials: Array[StandardMaterial3D] = []

func configure(spec: Dictionary) -> void:
	for part in parts:
		remove_child(part)
		part.queue_free()
	parts.clear()
	materials.clear()
	kind = str(spec.get("kind", "hit"))
	if kind not in ["arrow", "hit", "ground"]:
		kind = "hit"
	from = spec.get("from", Vector3.ZERO)
	to = spec.get("to", from)
	duration = maxf(0.001, float(spec.get("duration", 0.22)))
	tint = spec.get("tint", Color("f3d9a0"))
	set_meta("visual_owner", int(spec.get("owner", -1)))
	age = 0.0
	finished = false
	visible = true
	transform = Transform3D.IDENTITY
	if kind == "arrow":
		_make_arrow()
	elif kind == "ground":
		_make_ground()
	else:
		_make_hit()
	_draw_age()

func advance(seconds: float) -> void:
	age = minf(duration, age + maxf(0.0, seconds))
	finished = age >= duration
	_draw_age()

func _material(color: Color, translucent: bool = false) -> StandardMaterial3D:
	var result = StandardMaterial3D.new()
	result.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	result.albedo_color = color
	result.cull_mode = BaseMaterial3D.CULL_DISABLED
	if translucent:
		result.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		result.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	materials.append(result)
	return result

func _mesh(mesh: Mesh, material: StandardMaterial3D) -> MeshInstance3D:
	var part = MeshInstance3D.new()
	part.mesh = mesh
	part.material_override = material
	part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(part)
	parts.append(part)
	return part

func _cylinder(radius: float, length: float, tip: bool = false) -> CylinderMesh:
	var result = CylinderMesh.new()
	result.radial_segments = 6
	result.rings = 1
	result.top_radius = 0.0 if tip else radius
	result.bottom_radius = radius
	result.height = length
	return result

func _make_arrow() -> void:
	# All geometry lies behind local -Z tip, so position == exact arrow tip.
	var shaft = _mesh(_cylinder(0.009, 0.26), _material(Color("a98c62")))
	shaft.rotation.x = PI * 0.5
	shaft.position.z = 0.19
	var head = _mesh(_cylinder(0.026, 0.075, true), _material(tint))
	head.rotation.x = -PI * 0.5
	head.position.z = 0.0375
	var tail_color = tint
	tail_color.a = 0.32
	var tail = _mesh(_cylinder(0.006, 0.13), _material(tail_color, true))
	tail.rotation.x = PI * 0.5
	tail.position.z = 0.365

func _make_hit() -> void:
	# A brief spatial glint remains readable from both fixed camera directions.
	for i in range(3):
		var box = BoxMesh.new()
		box.size = Vector3(0.23, 0.018, 0.018)
		var color = tint
		color.a = 0.78
		var part = _mesh(box, _material(color, true))
		if i == 0:
			part.rotation.z = PI * 0.25
		elif i == 1:
			part.rotation.z = -PI * 0.25
		else:
			part.rotation.y = PI * 0.5

func _make_ground() -> void:
	# Three broken dust arcs, not a filled disc or a persistent gameplay radius.
	var vertices = PackedVector3Array()
	for arc in range(3):
		for step in range(8):
			var a = float(arc) * TAU / 3.0 + float(step) * 0.12
			var b = a + 0.12
			var outer_a = Vector3(cos(a), 0.0, sin(a)) * 0.30
			var outer_b = Vector3(cos(b), 0.0, sin(b)) * 0.30
			var inner_a = Vector3(cos(a), 0.0, sin(a)) * 0.275
			var inner_b = Vector3(cos(b), 0.0, sin(b)) * 0.275
			vertices.append_array(PackedVector3Array([inner_a, outer_a, outer_b, inner_a, outer_b, inner_b]))
	var arrays = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	var mesh = ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var color = tint
	color.a = 0.52
	_mesh(mesh, _material(color, true))

func _draw_age() -> void:
	var progress = clampf(age / duration, 0.0, 1.0)
	if kind == "arrow":
		# Quadratic height is zero at both ends; tangent gives correct facing.
		position = from.lerp(to, progress) + Vector3.UP * (0.32 * progress * (1.0 - progress))
		var tangent = to - from + Vector3.UP * (0.32 * (1.0 - 2.0 * progress))
		if tangent.length_squared() > 0.000001:
			var up = Vector3.RIGHT if absf(tangent.normalized().dot(Vector3.UP)) > 0.98 else Vector3.UP
			basis = Basis.looking_at(tangent.normalized(), up)
		parts[2].visible = progress > 0.03 and not finished
	else:
		position = to
		if kind == "ground":
			position.y += 0.018
			var spread = lerpf(0.50, 1.12, progress)
			scale = Vector3(spread, 1.0, spread)
		else:
			var glint_scale = lerpf(0.50, 1.15, smoothstep(0.0, 0.24, progress))
			scale = Vector3.ONE * glint_scale
		for mat in materials:
			var color = tint
			color.a = (0.52 if kind == "ground" else 0.78) * (1.0 - smoothstep(0.08, 1.0, progress))
			mat.albedo_color = color
	# Keep final transform inspectable while the Board removes the expired node.
	visible = not finished
