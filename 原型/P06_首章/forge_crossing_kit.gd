extends RefCounted

# Low-poly P04B MultiMesh architectural kit for RG05 · G · FORGE_CROSSING (铸律工场).
# Uses weathered basalt-slate, forged iron, and muted bronze (keeping bright orange reserved for warnings).

const BASALT_DARK := Color("4f4b47")
const BASALT_MID := Color("6e6862")
const STONE_LIGHT := Color("9a9389")
const STONE_PALE := Color("c4bdb1")
const IRON := Color("464340")
const BRONZE := Color("9a7e52")
const ANCHOR_RING := Color("b8985e")

static var _pieces: Dictionary = {}
static var _box: BoxMesh


static func supports(kind: String) -> bool:
	return kind in [
		"forge-pillar",
		"forge-anvil",
		"forge-gantry",
		"forge-anchor",
	]


static func piece(kind: String) -> Node3D:
	if not supports(kind):
		return null
	if not _pieces.has(kind):
		_pieces[kind] = _build_mesh(kind)
	var mesh: MultiMesh = _pieces[kind]
	if mesh == null:
		return null
	var node := MultiMeshInstance3D.new()
	node.multimesh = mesh
	return node


static func _build_mesh(kind: String) -> MultiMesh:
	var items: Array[Dictionary] = []
	match kind:
		"forge-pillar":
			# HIGH_OBSTACLE: tall forged basalt/iron kiln column (distinct tall LOS-blocking silhouette)
			_add(items, BASALT_DARK, Vector3(0, 0.14, 0), Vector3(0.94, 0.28, 0.80))
			_add(items, BASALT_MID, Vector3(0, 0.84, 0), Vector3(0.68, 1.18, 0.56))
			_add(items, IRON, Vector3(0, 0.62, 0), Vector3(0.76, 0.14, 0.62))
			_add(items, BRONZE, Vector3(0, 1.18, 0), Vector3(0.74, 0.10, 0.60))
			_add(items, STONE_LIGHT, Vector3(0, 1.48, 0), Vector3(0.82, 0.14, 0.68))
		"forge-anvil":
			# LOW_OBSTACLE: low iron-bound forge anvil / slag-trough barrier (clearly shorter than pillar & units)
			_add(items, BASALT_DARK, Vector3(0, 0.10, 0), Vector3(0.96, 0.20, 0.60))
			_add(items, IRON, Vector3(0, 0.30, 0), Vector3(0.84, 0.24, 0.44))
			_add(items, STONE_LIGHT, Vector3(0, 0.44, 0), Vector3(0.92, 0.08, 0.48))
			_add(items, BRONZE, Vector3(0, 0.30, 0.23), Vector3(0.38, 0.08, 0.04))
		"forge-gantry":
			# HIGH_GROUND: stepped pale stone-and-iron foundry gantry pad (flat top for units)
			_add(items, BASALT_MID, Vector3(0, 0.08, 0), Vector3(1.16, 0.16, 1.02))
			_add(items, STONE_PALE, Vector3(0, 0.20, 0), Vector3(0.98, 0.10, 0.86))
			_add(items, BRONZE, Vector3(0, 0.26, 0.42), Vector3(0.66, 0.03, 0.04))
		"forge-anchor":
			# Low flush bronze leyline anchor pad (does not obscure units or danger warnings)
			_add(items, BASALT_DARK, Vector3(0, 0.03, 0), Vector3(0.82, 0.06, 0.82))
			_add(items, ANCHOR_RING, Vector3(0, 0.07, 0), Vector3(0.68, 0.04, 0.12))
			_add(items, ANCHOR_RING, Vector3(0, 0.07, 0), Vector3(0.12, 0.04, 0.68))
	return _pack(items)


static func _add(items: Array[Dictionary], color: Color, pos: Vector3, size: Vector3,
		yaw := 0.0, pitch := 0.0, roll := 0.0) -> void:
	var basis := Basis.from_euler(Vector3(pitch, yaw, roll)).scaled(size)
	items.append({"xform": Transform3D(basis, pos), "color": color})


static func _pack(items: Array[Dictionary]) -> MultiMesh:
	if _box == null:
		_box = BoxMesh.new()
		_box.size = Vector3.ONE
		var mat := StandardMaterial3D.new()
		mat.vertex_color_use_as_albedo = true
		mat.roughness = 0.84
		mat.metallic = 0.10
		_box.material = mat
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = _box
	mm.instance_count = items.size()
	for i in items.size():
		mm.set_instance_transform(i, items[i].xform)
		mm.set_instance_color(i, items[i].color)
	return mm
