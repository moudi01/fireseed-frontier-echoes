extends RefCounted

const TownKit = preload("res://town_kit.gd")

const STONE := [Color("70675a"), Color("898071"), Color("9c8c74"), Color("aaa08b")]
const TIMBER := Color("4f4537")
const CLOTH := Color("794e43")
const RUST := Color("937953")
const LINEN := Color("b8a688")
const LAMP := Color("e6b775")
const TOWN_WOOD := Color("805f45")
const TOWN_ROOF := Color("595b50")
const AMBER_GLASS := Color("ca884a")
const LIT_GLASS := Color("f0c382")

static var _pieces: Dictionary = {}
static var _lamp_meshes: Dictionary = {}
static var _box: BoxMesh
static var _lamp_box: BoxMesh
static var _backdrop: StandardMaterial3D


static func piece(kind: String) -> Node3D:
	if TownKit.supports(kind):
		var town_node := TownKit.piece(kind)
		if town_node != null:
			return town_node
	if not _pieces.has(kind):
		_pieces[kind] = _build_mesh(kind)
	var mesh: MultiMesh = _pieces[kind]
	if mesh == null:
		return null
	var node := MultiMeshInstance3D.new()
	node.multimesh = mesh
	if _lamp_meshes.has(kind):
		var panes := MultiMeshInstance3D.new()
		panes.name = "LampGlass"
		panes.multimesh = _lamp_meshes[kind]
		panes.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.add_child(panes)
	return node


static func backdrop_material() -> StandardMaterial3D:
	if _backdrop == null:
		_backdrop = _box.material.duplicate()
		_backdrop.albedo_color = Color("d1cec8")
	return _backdrop


static func _build_mesh(kind: String) -> MultiMesh:
	var groups: Dictionary = {}
	var lamps: Dictionary = {}
	match kind:
		"fortress-camp":
			_block(groups, STONE[1], Vector3(-0.13, 0.08, 0), Vector3(1.90, 0.16, 1.42))
			for x in [-0.82, 0.64]:
				for z in [-0.51, 0.51]:
					var height := 1.18 if z < 0 else 0.90
					_block(groups, TIMBER, Vector3(x, height * 0.5, z), Vector3(0.11, height, 0.11))
			_block(groups, LINEN, Vector3(-0.09, 1.10, 0), Vector3(1.75, 0.09, 1.29), 0.0, 0.26)
			_block(groups, CLOTH, Vector3(-0.61, 1.15, 0), Vector3(0.25, 0.094, 1.29), 0.0, 0.26)
			_lamp(groups, 0.96, 0.28)
		"fortress-watch":
			_tower(groups, -0.50, 6)
			_tower(groups, 0.60, 3)
			_block(groups, TIMBER, Vector3(0.05, 0.82, -0.02), Vector3(0.90, 0.18, 0.33))
			_block(groups, CLOTH, Vector3(-0.22, 0.93, 0.39), Vector3(0.26, 0.52, 0.05))
		"fortress-aid":
			_block(groups, STONE[1], Vector3(0, 0.10, 0), Vector3(1.51, 0.20, 1.04))
			_block(groups, TIMBER, Vector3(0, 0.45, 0), Vector3(1.22, 0.57, 0.85))
			_block(groups, STONE[2], Vector3(0, 0.77, 0), Vector3(1.29, 0.12, 0.90))
			for x in [-0.40, 0.40]:
				_block(groups, CLOTH, Vector3(x, 0.84, 0), Vector3(0.14, 0.04, 0.91))
				_block(groups, CLOTH, Vector3(x, 0.49, 0.44), Vector3(0.14, 0.65, 0.04))
			_block(groups, RUST, Vector3(0, 0.60, 0.45), Vector3(0.18, 0.20, 0.055))
			_block(groups, LINEN, Vector3(0, 0.87, 0), Vector3(0.34, 0.08, 0.37))
		"fortress-palisade":
			_block(groups, STONE[0], Vector3(0, 0.11, 0.08), Vector3(2.53, 0.22, 0.67))
			_block(groups, TIMBER, Vector3(0, 0.42, -0.12), Vector3(2.54, 0.16, 0.16))
			for i in range(6):
				var height := [1.13, 1.0, 0.67, 0.38, 0.96, 1.16][i] as float
				_block(groups, TIMBER if i % 2 == 0 else STONE[1],
					Vector3(-0.98 + i * 0.39, 0.20 + height * 0.5, 0),
					Vector3(0.31, height, 0.27), 0.11 * (i - 2))
			_block(groups, CLOTH, Vector3(-0.74, 0.68, 0.16), Vector3(0.61, 0.21, 0.055))
		"fortress-gate":
			_tower(groups, -1.10, 5)
			_tower(groups, 1.10, 5)
			for i in range(7):
				var angle := PI * (float(i) + 0.5) / 7.0
				var center := Vector3(0.79 * cos(angle), 1.28 + 0.79 * sin(angle), 0)
				_block(groups, STONE[2 + i % 2], center, Vector3(0.36, 0.49, 0.82),
					0.0, 0.0, angle - PI * 0.5)
			_block(groups, STONE[1], Vector3(0, 0.07, 0.16), Vector3(1.94, 0.14, 0.93))
			_block(groups, LINEN, Vector3(0, 2.12, 0.015), Vector3(0.23, 0.35, 0.85))
		"fortress-exit":
			_block(groups, STONE[1], Vector3(0, 0.08, 0.17), Vector3(1.94, 0.16, 0.98))
			_block(groups, STONE[2], Vector3(0, 0.14, -0.14), Vector3(1.79, 0.16, 0.69))
			for x in [-0.77, 0.77]:
				_lamp(groups, x, 0)
		"fortress-ledger-post":
			_block(groups, STONE[0], Vector3(0, 0.11, 0), Vector3(1.44, 0.22, 1.15))
			for x in [-0.57, 0.57]:
				_block(groups, TIMBER, Vector3(x, 0.68, -0.31), Vector3(0.13, 1.25, 0.13))
			_block(groups, TIMBER, Vector3(0, 0.69, 0.15), Vector3(1.23, 0.15, 0.78))
			_block(groups, CLOTH, Vector3(0, 1.35, 0.04), Vector3(1.58, 0.10, 1.14), 0.0, 0.19)
			_block(groups, LINEN, Vector3(0.09, 0.79, 0.22), Vector3(0.45, 0.08, 0.32), 0.18)
			_block(groups, RUST, Vector3(0.09, 0.83, 0.22), Vector3(0.04, 0.023, 0.28), 0.18)
		"fortress-padding-shed":
			_block(groups, STONE[1], Vector3(0, 0.09, 0), Vector3(1.89, 0.18, 1.16))
			_block(groups, TIMBER, Vector3(-0.03, 0.34, 0.07), Vector3(1.59, 0.45, 0.73))
			for i in range(3):
				var at := Vector3(-0.51 + i * 0.47, 0.66, 0.12)
				_block(groups, LINEN if i % 2 == 0 else STONE[2], at, Vector3(0.42, 0.23, 0.74), i * 0.09)
				_block(groups, CLOTH, at + Vector3(0, 0.115, 0), Vector3(0.08, 0.025, 0.77), i * 0.09)
			_block(groups, TIMBER, Vector3(-0.85, 0.71, -0.39), Vector3(0.13, 1.27, 0.13))
			_block(groups, TIMBER, Vector3(0.81, 0.71, -0.39), Vector3(0.13, 1.27, 0.13))
			_block(groups, STONE[0], Vector3(-0.04, 1.37, -0.29), Vector3(1.94, 0.15, 0.92), 0.0, 0.24)
		"fortress-recovery-wall":
			_block(groups, STONE[0], Vector3(0, 0.12, 0), Vector3(2.27, 0.24, 0.75))
			for i in range(4):
				_block(groups, STONE[1 + i % 2], Vector3(0, 0.32 + 0.20 * i, 0), Vector3(2.13 - i * 0.08, 0.20, 0.51))
			for x in [-0.63, 0.0, 0.63]:
				_block(groups, TIMBER, Vector3(x, 0.77, 0.257), Vector3(0.24, 0.31, 0.035))
				_block(groups, RUST, Vector3(x, 0.67, 0.287), Vector3(0.10, 0.07, 0.07))
			_block(groups, STONE[3], Vector3(-0.09, 1.095, -0.02), Vector3(1.84, 0.16, 0.62))
		"fortress-shift-door":
			_tower(groups, -0.69, 3)
			_tower(groups, 0.69, 3)
			_block(groups, TIMBER, Vector3(0, 1.16, 0), Vector3(1.71, 0.18, 0.39), 0.0, 0.0, -0.08)
			_block(groups, TIMBER, Vector3(-0.28, 0.99, 0.11), Vector3(0.59, 0.14, 0.17), 0.0, 0.0, 0.76)
		"fortress-ditch-rampart":
			_block(groups, STONE[0], Vector3(0, 0.10, 0), Vector3(2.63, 0.20, 0.98))
			for i in range(4):
				var height := [0.56, 0.75, 0.73, 0.58][i] as float
				_block(groups, STONE[1 + i % 2], Vector3(-0.88 + i * 0.57, 0.18 + height * 0.5, 0),
					Vector3(0.53, height, 0.79), 0.12 * (i - 1))
			_block(groups, TIMBER, Vector3(-0.85, 0.82, -0.19), Vector3(0.13, 1.47, 0.13))
			_block(groups, TIMBER, Vector3(0.87, 0.82, -0.19), Vector3(0.13, 1.47, 0.13))
			_block(groups, CLOTH, Vector3(-0.02, 1.24, -0.14), Vector3(1.70, 0.51, 0.07))
		"fortress-wall":
			_block(groups, STONE[0], Vector3(0, 0.13, 0), Vector3(3.2, 0.26, 0.81))
			for course in range(3):
				for i in range(4):
					var x := -1.17 + i * 0.77 + (0.13 if course == 1 else 0.0)
					_block(groups, STONE[(i + course) % STONE.size()], Vector3(x, 0.39 + 0.25 * course, 0),
						Vector3(0.755, 0.25, 0.61 - course * 0.045))
			_block(groups, STONE[1], Vector3(0, 1.03, 0), Vector3(3.22, 0.18, 0.69))
			for i in range(4):
				_block(groups, STONE[2], Vector3(-1.18 + i * 0.77, 1.26, 0), Vector3(0.41, 0.32 - (0.14 if i == 3 else 0.0), 0.58))
		"fortress-rubble":
			_block(groups, STONE[0], Vector3(0.00, 0.13, 0), Vector3(0.93, 0.26, 0.73), -0.19)
			_block(groups, STONE[2], Vector3(-0.12, 0.33, 0), Vector3(0.62, 0.30, 0.58), 0.30)
			_block(groups, STONE[1], Vector3(-0.22, 0.51, 0.02), Vector3(0.38, 0.18, 0.42), -0.24)
			_block(groups, STONE[3], Vector3(0.34, 0.11, 0.35), Vector3(0.29, 0.23, 0.32), -0.5)
		"fortress-standard":
			_block(groups, STONE[1], Vector3(0, 0.12, 0), Vector3(0.63, 0.24, 0.58))
			_block(groups, TIMBER, Vector3(0, 1.23, 0), Vector3(0.10, 2.32, 0.12))
			_block(groups, TIMBER, Vector3(0.30, 2.26, 0), Vector3(0.70, 0.095, 0.10))
			_block(groups, CLOTH, Vector3(0.33, 1.87, -0.018), Vector3(0.53, 0.72, 0.055))
			_block(groups, CLOTH, Vector3(0.20, 1.43, -0.001), Vector3(0.25, 0.25, 0.055), 0.08)
			_block(groups, STONE[2], Vector3(0.25, 1.91, 0.019), Vector3(0.09, 0.43, 0.012))
		"town-muster":
			_block(groups, STONE[1], Vector3(0, 0.07, 0), Vector3(2.43, 0.14, 1.33))
			for x in [-1.12, 1.12]:
				_block(groups, TIMBER, Vector3(x, 0.99, -0.53), Vector3(0.09, 1.83, 0.09))
				_block(groups, TIMBER, Vector3(x, 0.92, 0.45), Vector3(0.09, 1.69, 0.09))
			_block(groups, Color("95534a"), Vector3(0, 1.77, -0.04), Vector3(2.46, 0.045, 1.16), 0.0, -0.14)
			_block(groups, Color("804135"), Vector3(0, 1.68, 0.52), Vector3(2.46, 0.10, 0.045))
			for x in [-0.80, 0.0, 0.80]:
				_block(groups, Color("a06053"), Vector3(x, 1.795, -0.04), Vector3(0.016, 0.012, 1.09), 0.0, -0.14)
			for x in [-0.91, 0.91]:
				for z in [-0.42, 0.34]:
					_block(groups, TOWN_WOOD, Vector3(x, 0.48, z), Vector3(0.11, 0.82, 0.11))
			_block(groups, TOWN_WOOD, Vector3(0, 0.91, -0.04), Vector3(2.15, 0.16, 1.00))
			_block(groups, LINEN, Vector3(-0.25, 1.002, -0.02), Vector3(1.06, 0.028, 0.61), 0.14)
			_block(groups, RUST, Vector3(-0.23, 1.023, 0.035), Vector3(0.07, 0.014, 0.47), -0.19)
			_block(groups, TIMBER, Vector3(0.61, 0.86, 0.448), Vector3(0.52, 0.15, 0.051))
			_block(groups, TOWN_WOOD, Vector3(0.61, 0.859, 0.480), Vector3(0.40, 0.064, 0.016))
			_block(groups, CLOTH, Vector3(0.47, 1.13, -0.29), Vector3(0.39, 0.25, 0.31), 0.22)
			_lamp(groups, -1.41, -0.16)
			_block(lamps, LIT_GLASS, Vector3(-1.41, 0.78, -0.050), Vector3(0.113, 0.178, 0.012))
		"town-store":
			_block(groups, STONE[1], Vector3(0, 0.09, -0.11), Vector3(2.16, 0.18, 1.50))
			_block(groups, TIMBER, Vector3(0, 0.71, -0.71), Vector3(2.02, 1.18, 0.19))
			for x in [-0.91, 0.91]:
				_block(groups, TOWN_WOOD, Vector3(x, 0.79, -0.12), Vector3(0.18, 1.37, 1.35))
			_block(groups, TOWN_WOOD, Vector3(0, 1.39, 0.46), Vector3(2.04, 0.19, 0.14))
			_town_slate_roof(groups, Vector3(0, 1.72, -0.13), 2.37, 1.60)
			_block(groups, TOWN_WOOD, Vector3(0.57, 0.83, 0.41), Vector3(0.55, 0.92, 0.06))
			_block(groups, TIMBER, Vector3(0.56, 1.02, 0.464), Vector3(0.57, 0.48, 0.09))
			_block(groups, RUST, Vector3(0.56, 0.755, 0.508), Vector3(0.62, 0.08, 0.14))
			for x in [0.433, 0.677]:
				_block(lamps, AMBER_GLASS, Vector3(x, 1.026, 0.514), Vector3(0.182, 0.316, 0.014))
				_block(lamps, LIT_GLASS, Vector3(x, 0.98, 0.523), Vector3(0.134, 0.165, 0.010))
			_block(groups, TIMBER, Vector3(0.56, 1.089, 0.533), Vector3(0.49, 0.039, 0.027))
			for x in [-0.52, 0.02]:
				_block(groups, TOWN_WOOD, Vector3(x, 0.34, 0.23), Vector3(0.45, 0.49, 0.46), x * 0.13)
				_block(groups, RUST, Vector3(x, 0.39, 0.468), Vector3(0.31, 0.085, 0.023), x * 0.13)
			_block(groups, LINEN, Vector3(-0.50, 0.656, 0.19), Vector3(0.34, 0.15, 0.30), -0.20)
		"town-gate":
			for x in [-1.03, 1.03]:
				_block(groups, STONE[1], Vector3(x, 0.23, 0), Vector3(0.41, 0.46, 0.55))
				_block(groups, TOWN_WOOD, Vector3(x, 0.93, 0), Vector3(0.26, 1.12, 0.31))
				_block(groups, TIMBER, Vector3(x, 1.15, 0.25), Vector3(0.19, 0.26, 0.15))
				_block(lamps, LIT_GLASS, Vector3(x, 1.14, 0.331), Vector3(0.117, 0.174, 0.012))
				_block(groups, RUST, Vector3(x, 1.034, 0.31), Vector3(0.22, 0.060, 0.13))
				_block(groups, TIMBER, Vector3(x, 1.30, 0.26), Vector3(0.23, 0.07, 0.22))
			_block(groups, TOWN_WOOD, Vector3(0, 1.54, 0), Vector3(2.45, 0.22, 0.34))
			_town_slate_roof(groups, Vector3(0, 1.88, 0), 2.64, 0.91)
			_block(groups, STONE[0], Vector3(0, 0.06, 0.21), Vector3(1.86, 0.12, 0.58))
		"town-house":
			var plaster := Color("716b57")
			var roof := Color("515547")
			_block(groups, STONE[0], Vector3(0, 0.12, 0), Vector3(2.47, 0.24, 1.30))
			_block(groups, plaster, Vector3(0, 0.72, 0), Vector3(2.29, 1.0, 1.19))
			for x in [-1.08, 1.08]:
				_block(groups, TIMBER, Vector3(x, 0.72, 0.60), Vector3(0.095, 1.0, 0.079))
			_block(groups, TIMBER, Vector3(0, 1.18, 0.61), Vector3(2.35, 0.12, 0.12))
			_block(groups, TIMBER, Vector3(-0.40, 0.68, 0.616), Vector3(0.47, 0.37, 0.065))
			_block(groups, Color("938066"), Vector3(-0.40, 0.68, 0.655), Vector3(0.31, 0.23, 0.022))
			_block(groups, TIMBER, Vector3(-0.40, 0.68, 0.67), Vector3(0.045, 0.28, 0.023))
			_block(groups, roof, Vector3(0, 1.34, -0.37), Vector3(2.62, 0.14, 0.89), 0.0, 0.42)
			_block(groups, roof, Vector3(0, 1.34, 0.37), Vector3(2.62, 0.14, 0.89), 0.0, -0.42)
		"town-fence":
			var fence := Color("645542")
			for x in [-1.52, -0.50, 0.49, 1.51]:
				_block(groups, fence, Vector3(x, 0.34, 0), Vector3(0.15, 0.68, 0.20))
				_block(groups, STONE[0], Vector3(x, 0.072, 0), Vector3(0.28, 0.144, 0.31))
			_block(groups, fence, Vector3(0, 0.46, 0.04), Vector3(3.04, 0.13, 0.12), 0.0, 0.0, 0.019)
			_block(groups, fence, Vector3(0, 0.24, 0.04), Vector3(3.04, 0.11, 0.12), 0.0, 0.0, -0.014)
		_:
			return null
	if _box == null:
		var material := StandardMaterial3D.new()
		material.vertex_color_use_as_albedo = true
		material.roughness = 0.89
		_box = BoxMesh.new()
		_box.material = material
	if not lamps.is_empty():
		if _lamp_box == null:
			var glass := StandardMaterial3D.new()
			glass.vertex_color_use_as_albedo = true
			glass.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			_lamp_box = BoxMesh.new()
			_lamp_box.material = glass
		_lamp_meshes[kind] = _mesh_instances(lamps, _lamp_box)
	return _mesh_instances(groups, _box)


static func _town_slate_roof(groups: Dictionary, ridge: Vector3, width: float, depth: float) -> void:
	var half := depth * 0.5
	var pitch := 0.34
	var tile_width := width / 8.0
	var course_depth := half / 4.0
	var shades := [TOWN_ROOF, TOWN_ROOF.darkened(0.09), TOWN_ROOF.lightened(0.06)]
	for side in [-1.0, 1.0]:
		_block(groups, TIMBER, ridge + Vector3(0, -tan(pitch) * half * 0.5 - 0.06, side * half * 0.5),
			Vector3(width, 0.08, half / cos(pitch)), 0.0, side * pitch)
		for course in range(4):
			var distance := (course + 0.5) * course_depth
			for tile in range(8):
				var at := ridge + Vector3((tile - 3.5) * tile_width, -tan(pitch) * distance, side * distance)
				_block(groups, shades[(tile + 2 * course) % shades.size()], at,
					Vector3(tile_width - 0.009, 0.047, course_depth * 0.98), 0.0, side * pitch)
	_block(groups, TOWN_ROOF.darkened(0.12), ridge + Vector3(0, 0.015, 0), Vector3(width + 0.045, 0.065, 0.085))


static func _mesh_instances(groups: Dictionary, mesh: BoxMesh) -> MultiMesh:
	var count := 0
	for tone in groups:
		count += groups[tone].size()
	var instances := MultiMesh.new()
	instances.transform_format = MultiMesh.TRANSFORM_3D
	instances.use_colors = true
	instances.mesh = mesh
	instances.instance_count = count
	var index := 0
	for tone: Color in groups:
		for transform: Transform3D in groups[tone]:
			instances.set_instance_transform(index, transform)
			instances.set_instance_color(index, tone)
			index += 1
	return instances


static func _tower(groups: Dictionary, x: float, courses: int) -> void:
	_block(groups, STONE[0], Vector3(x, 0.12, 0), Vector3(0.96, 0.24, 1.03))
	for i in range(courses):
		_block(groups, STONE[1 + i % 3], Vector3(x + 0.022 * (i % 2), 0.37 + 0.27 * i, 0),
			Vector3(0.77 - 0.027 * i, 0.27, 0.82 - 0.025 * i))
	_block(groups, STONE[2], Vector3(x, 0.27 + 0.27 * courses, 0), Vector3(0.87, 0.14, 0.87))
	for z in [-0.28, 0.28]:
		_block(groups, STONE[3], Vector3(x, 0.44 + 0.27 * courses, z), Vector3(0.45, 0.20, 0.26))


static func _lamp(groups: Dictionary, x: float, z: float) -> void:
	_block(groups, STONE[0], Vector3(x, 0.12, z), Vector3(0.39, 0.24, 0.39))
	_block(groups, TIMBER, Vector3(x, 0.43, z), Vector3(0.11, 0.56, 0.11))
	_block(groups, LAMP, Vector3(x, 0.79, z), Vector3(0.20, 0.30, 0.21))
	for rail in [-0.10, 0.10]:
		_block(groups, TIMBER, Vector3(x + rail, 0.79, z + 0.09), Vector3(0.045, 0.36, 0.06))
	_block(groups, RUST, Vector3(x, 0.97, z), Vector3(0.32, 0.09, 0.32))


static func _block(groups: Dictionary, tone: Color, center: Vector3, extent: Vector3,
	yaw := 0.0, pitch := 0.0, roll := 0.0) -> void:
	if not groups.has(tone):
		groups[tone] = []
	var rotation := Basis.from_euler(Vector3(pitch, yaw, roll))
	groups[tone].append(Transform3D(rotation.scaled_local(extent), center))
