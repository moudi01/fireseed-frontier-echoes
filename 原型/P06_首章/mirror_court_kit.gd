extends RefCounted

# Low-poly P04B MultiMesh architectural kit for RG03 / G · MIRROR_COURT (镜关战场).
# Follows the exact MultiMesh pattern of fortress_kit.gd with warm limestone,
# weathered bronze mirror frames, and matte silver-slate mirror slabs.

const STONE_DARK := Color("635b4f")
const STONE_MID := Color("847a6a")
const STONE_LIGHT := Color("a89c86")
const STONE_PALE := Color("c4b79e")
const BRONZE := Color("8c714d")
const MIRROR_SLATE := Color("9aa3a0")
const TIMBER := Color("564738")
const LAMP_GLOW := Color("ecc07a")

static var _pieces: Dictionary = {}
static var _box: BoxMesh


static func supports(kind: String) -> bool:
	return kind in [
		"mirror-shrine",
		"mirror-stele",
		"mirror-plinth",
		"mirror-dais",
		"mirror-lantern",
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
		"mirror-shrine":
			# Mid-rear landmark: stepped old mirror dais + twin pillars + cracked mirror plate
			_add(items, STONE_MID, Vector3(0, 0.11, 0), Vector3(2.40, 0.22, 1.30))
			_add(items, STONE_LIGHT, Vector3(0, 0.28, -0.05), Vector3(2.05, 0.14, 1.02))
			for x in [-0.74, 0.74]:
				_add(items, STONE_DARK, Vector3(x, 0.92, -0.18), Vector3(0.32, 1.18, 0.34))
				_add(items, STONE_LIGHT, Vector3(x, 1.56, -0.18), Vector3(0.40, 0.12, 0.42))
			_add(items, BRONZE, Vector3(0, 1.66, -0.18), Vector3(1.78, 0.14, 0.24))
			_add(items, MIRROR_SLATE, Vector3(0, 0.98, -0.18), Vector3(1.12, 1.18, 0.08))
		"mirror-stele":
			# HIGH_OBSTACLE: tall fractured mirror stele (clearly taller than low cover, blocks LOS)
			_add(items, STONE_DARK, Vector3(0, 0.12, 0), Vector3(0.92, 0.24, 0.74))
			_add(items, STONE_MID, Vector3(0, 0.78, 0), Vector3(0.68, 1.16, 0.42))
			_add(items, BRONZE, Vector3(0, 0.84, 0.21), Vector3(0.50, 0.88, 0.05))
			_add(items, MIRROR_SLATE, Vector3(0, 0.84, 0.24), Vector3(0.38, 0.72, 0.03))
			_add(items, STONE_LIGHT, Vector3(-0.08, 1.44, 0), Vector3(0.56, 0.18, 0.44), 0.0, 0.0, 0.12)
		"mirror-plinth":
			# LOW_OBSTACLE: low carved stone parapet (clearly shorter than high stele & units)
			_add(items, STONE_DARK, Vector3(0, 0.09, 0), Vector3(0.96, 0.18, 0.62))
			_add(items, STONE_MID, Vector3(0, 0.28, 0), Vector3(0.84, 0.24, 0.46))
			_add(items, STONE_LIGHT, Vector3(0, 0.43, 0), Vector3(0.90, 0.09, 0.50))
			_add(items, BRONZE, Vector3(0, 0.29, 0.24), Vector3(0.42, 0.08, 0.04))
		"mirror-dais":
			# HIGH_GROUND: stepped pale limestone elevation pad (readable height cue, flat top for units)
			_add(items, STONE_MID, Vector3(0, 0.07, 0), Vector3(1.14, 0.14, 1.02))
			_add(items, STONE_PALE, Vector3(0, 0.19, 0), Vector3(0.96, 0.11, 0.86))
			_add(items, BRONZE, Vector3(0, 0.25, 0.43), Vector3(0.68, 0.03, 0.04))
		"mirror-lantern":
			_add(items, STONE_DARK, Vector3(0, 0.10, 0), Vector3(0.38, 0.20, 0.38))
			_add(items, TIMBER, Vector3(0, 0.68, 0), Vector3(0.10, 1.04, 0.10))
			_add(items, BRONZE, Vector3(0.14, 1.12, 0), Vector3(0.34, 0.07, 0.07))
			_add(items, LAMP_GLOW, Vector3(0.24, 0.98, 0), Vector3(0.14, 0.20, 0.14))
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
		mat.roughness = 0.86
		mat.metallic = 0.04
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
