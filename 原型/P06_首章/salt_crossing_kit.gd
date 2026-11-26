extends RefCounted

# Low-poly P04B MultiMesh architectural kit for RG04 · SALT_CROSSING (沉息湖区 · 盐渡).
# Matches the MultiMesh pattern of fortress_kit.gd and mirror_court_kit.gd with pale salt-crust
# limestone, weathered ferry timber, and tarnished bell-bronze.

const STONE_DARK := Color("6e685e")
const STONE_MID := Color("948d7f")
const STONE_LIGHT := Color("bbb4a4")
const SALT_CRUST := Color("dfd9c9")
const TIMBER := Color("66523e")
const BRONZE := Color("92784e")

static var _pieces: Dictionary = {}
static var _box: BoxMesh


static func supports(kind: String) -> bool:
	return kind in [
		"salt-bollard",
		"salt-dais",
		"salt-pier",
		"salt-bell-post",
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
		"salt-bollard":
			# LOW_OBSTACLE: weathered salt-encrusted ferry bollard & low timber bumper
			_add(items, STONE_DARK, Vector3(0, 0.10, 0), Vector3(0.94, 0.20, 0.58))
			_add(items, SALT_CRUST, Vector3(0, 0.23, 0), Vector3(0.88, 0.08, 0.52))
			_add(items, TIMBER, Vector3(-0.24, 0.42, 0), Vector3(0.24, 0.44, 0.24))
			_add(items, TIMBER, Vector3(0.24, 0.38, 0), Vector3(0.24, 0.36, 0.24))
			_add(items, STONE_LIGHT, Vector3(0, 0.36, 0), Vector3(0.76, 0.14, 0.20))
		"salt-dais":
			# HIGH_GROUND: pale salt-limestone stepped crossing platform (flat top for units)
			_add(items, STONE_MID, Vector3(0, 0.07, 0), Vector3(1.16, 0.14, 1.02))
			_add(items, SALT_CRUST, Vector3(0, 0.18, 0), Vector3(0.98, 0.10, 0.86))
			_add(items, BRONZE, Vector3(0, 0.24, 0.42), Vector3(0.62, 0.03, 0.04))
		"salt-pier":
			# North-bank weathered timber ferry pier landmark
			_add(items, TIMBER, Vector3(0, 0.32, 0), Vector3(2.20, 0.14, 0.92))
			for x in [-0.88, 0.0, 0.88]:
				_add(items, TIMBER, Vector3(x, 0.24, -0.36), Vector3(0.16, 0.58, 0.16))
				_add(items, SALT_CRUST, Vector3(x, 0.07, -0.36), Vector3(0.22, 0.14, 0.22))
		"salt-bell-post":
			# Silent-lake stone marker & tarnished bronze bell
			_add(items, STONE_MID, Vector3(0, 0.12, 0), Vector3(0.56, 0.24, 0.56))
			_add(items, STONE_LIGHT, Vector3(0, 0.72, 0), Vector3(0.28, 1.08, 0.28))
			_add(items, SALT_CRUST, Vector3(0, 0.28, 0), Vector3(0.42, 0.10, 0.42))
			_add(items, BRONZE, Vector3(0.20, 1.08, 0), Vector3(0.28, 0.06, 0.06))
			_add(items, BRONZE, Vector3(0.28, 0.94, 0), Vector3(0.14, 0.18, 0.14))
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
