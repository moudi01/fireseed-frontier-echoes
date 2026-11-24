extends RefCounted

const YARD := Color("4b4939")
const TRACK := Color("63523d")
const TRACK_EDGE := Color("746048")
const STONE := [Color("756a54"), Color("7e7159"), Color("70634e")]
const LANTERN_WARMTH := Color("cb9c66")


static func paint(canvas: CanvasItem, extent: Vector2, landmarks: Dictionary, cell_size: float, models: bool) -> void:
	var frame := Rect2(Vector2(14, 14), extent - Vector2(28, 28))
	canvas.draw_polygon(PackedVector2Array([frame.position, Vector2(frame.end.x, frame.position.y), frame.end,
		Vector2(frame.position.x, frame.end.y)]), PackedColorArray([
		Color("303d3e"), Color("344040"), Color("625844"), Color("545045")]))
	land(canvas, extent, Color("3b4740"), [Vector2(0.017, 0.31), Vector2(0.13, 0.19),
		Vector2(0.25, 0.14), Vector2(0.39, 0.23), Vector2(0.48, 0.22), Vector2(0.66, 0.12),
		Vector2(0.81, 0.18), Vector2(0.98, 0.30), Vector2(0.98, 0.51), Vector2(0.017, 0.51)])
	land(canvas, extent, Color("3c4835"), [Vector2(0.017, 0.39), Vector2(0.13, 0.32),
		Vector2(0.31, 0.34), Vector2(0.49, 0.29), Vector2(0.72, 0.33), Vector2(0.98, 0.27),
		Vector2(0.98, 0.975), Vector2(0.017, 0.975)])
	_paint_backstreet(canvas, extent)
	land(canvas, extent, YARD, [Vector2(0.017, 0.64), Vector2(0.13, 0.49), Vector2(0.20, 0.36),
		Vector2(0.35, 0.35), Vector2(0.47, 0.32), Vector2(0.63, 0.38), Vector2(0.76, 0.34),
		Vector2(0.88, 0.38), Vector2(0.98, 0.55), Vector2(0.98, 0.89),
		Vector2(0.87, 0.975), Vector2(0.20, 0.975), Vector2(0.017, 0.89)])
	land(canvas, extent, Color("484a39"), [Vector2(0.017, 0.82), Vector2(0.12, 0.76),
		Vector2(0.21, 0.85), Vector2(0.32, 0.90), Vector2(0.38, 0.975), Vector2(0.017, 0.975)])
	land(canvas, extent, Color("444536"), [Vector2(0.43, 0.975), Vector2(0.62, 0.896),
		Vector2(0.78, 0.866), Vector2(0.95, 0.89), Vector2(0.98, 0.93), Vector2(0.98, 0.975)])
	if landmarks.is_empty():
		return
	var muster: Vector2 = landmarks.muster.pixel
	var store: Vector2 = landmarks.store.pixel
	var gate: Vector2 = landmarks["departure-gate"].pixel
	var width := minf(1.0, extent.x / 865.0)
	var footpath := PackedVector2Array([muster + Vector2(-28, 17) * width, muster + Vector2(9, 34) * width,
		store + Vector2(-30, 84) * width, store + Vector2(29, 80) * width,
		gate + Vector2(-42, 43) * width, gate + Vector2(-26, 7) * width,
		gate + Vector2(29, 8) * width, gate + Vector2(43, 48) * width, store + Vector2(66, 105) * width,
		store + Vector2(-28, 112) * width, muster + Vector2(-1, 63) * width, muster + Vector2(-52, 49) * width])
	var store_approach := PackedVector2Array([store + Vector2(-32, 11) * width, store + Vector2(26, 11) * width,
		store + Vector2(23, 54) * width, store + Vector2(42, 92) * width, store + Vector2(-19, 95) * width,
		store + Vector2(-38, 57) * width])
	canvas.draw_colored_polygon(store_approach, TRACK)
	canvas.draw_colored_polygon(footpath, TRACK)
	canvas.draw_polyline(PackedVector2Array([footpath[11], footpath[10], footpath[9], footpath[8], footpath[7]]),
		TRACK_EDGE, 1.35, true)
	var ramp := PackedVector2Array([gate + Vector2(-26, 6) * width, gate + Vector2(27, 6) * width,
		Vector2(extent.x * 0.939, extent.y * 0.974), Vector2(extent.x * 0.80, extent.y * 0.974),
		gate + Vector2(1, 107) * width, gate + Vector2(-29, 50) * width])
	canvas.draw_colored_polygon(ramp, TRACK)
	for side in [-1.0, 1.0]:
		canvas.draw_polyline(PackedVector2Array([gate + Vector2(side * 14, 19) * width, gate + Vector2(9 + side * 19, 85) * width,
			Vector2(extent.x * (0.87 + side * 0.032), extent.y * 0.966)]), Color("514636"), 2.2, true)
	_paint_road_repairs(canvas, extent, gate, cell_size)
	paint_landmark_lighting(canvas, landmarks, cell_size, models)

	# Quiet surfaces under the formation, with chips and grass confined to the edges.
	for margin in [Vector2(0.075, 0.61), Vector2(0.112, 0.78), Vector2(0.37, 0.39),
		Vector2(0.62, 0.41), Vector2(0.91, 0.58), Vector2(0.948, 0.78)]:
		var at: Vector2 = margin * extent
		for i in range(4):
			var shift := Vector2(i * 8.8 - 12.0, float(i % 3) * 2.7)
			flagstone(canvas, at + shift, Vector2(6.0 + i % 2 * 3.0, 2.6), Color("665e49"))
		canvas.draw_polyline(PackedVector2Array([at + Vector2(-8, 2), at + Vector2(-13, -6),
			at + Vector2(-8, 2), at + Vector2(-6, -9), at + Vector2(-8, 2), at + Vector2(-2, -5)]), Color("5b6345"), 1.55, true)


static func paint_landmark_lighting(canvas: CanvasItem, landmarks: Dictionary, cell_size: float, models: bool) -> void:
	if landmarks.is_empty():
		return
	var muster: Vector2 = landmarks.muster.pixel
	var store: Vector2 = landmarks.store.pixel
	var gate: Vector2 = landmarks["departure-gate"].pixel

	for entrance: Vector2 in [muster, store, gate]:
		if models:
			var shadow := PackedVector2Array([Vector2(-1.29, -0.13), Vector2(-0.93, -0.32), Vector2(0.99, -0.29),
				Vector2(1.26, -0.04), Vector2(1.12, 0.24), Vector2(-0.94, 0.26)])
			for i in shadow.size():
				shadow[i] = entrance + shadow[i] * cell_size
			canvas.draw_colored_polygon(shadow, Color(0.09, 0.12, 0.09, 0.40))
		var threshold := entrance + Vector2(0, maxf(6.0, cell_size * 0.24))
		for i in range(5):
			var offset := Vector2((i - 2) * cell_size * 0.26, (i % 2 - 1) * cell_size * 0.031)
			flagstone(canvas, threshold + offset, Vector2(cell_size * (0.223 + (i % 3) * 0.019), cell_size * 0.105), STONE[i % STONE.size()])
	if models:
		var muster_unit: float = cell_size * landmarks.muster.scale
		var store_unit: float = cell_size * landmarks.store.scale
		var gate_unit: float = cell_size * landmarks["departure-gate"].scale
		_lamp_pool(canvas, muster + Vector2(-1.62, 0.31) * muster_unit, Vector2(1.13, 0.53) * muster_unit)
		_lamp_pool(canvas, store + Vector2(0.59, 0.87) * store_unit, Vector2(1.44, 0.69) * store_unit)
		_lamp_pool(canvas, gate + Vector2(-1.03, 0.57) * gate_unit, Vector2(1.20, 0.53) * gate_unit)
		_lamp_pool(canvas, gate + Vector2(0.97, 0.49) * gate_unit, Vector2(1.20, 0.54) * gate_unit)
static func _paint_backstreet(canvas: CanvasItem, extent: Vector2) -> void:
	# Keep the rear buildings unlit so the active entrances have the warmest light.
	_distant_house(canvas, extent, Vector2(0.078, 0.317), Vector2(0.130, 0.085), Color("485045"))
	_distant_house(canvas, extent, Vector2(0.160, 0.342), Vector2(0.119, 0.102), Color("555447"))
	_distant_house(canvas, extent, Vector2(0.653, 0.315), Vector2(0.132, 0.091), Color("515449"))
	_distant_house(canvas, extent, Vector2(0.784, 0.298), Vector2(0.113, 0.072), Color("494e44"))
	land(canvas, extent, Color("353f34"), [Vector2(0.026, 0.360), Vector2(0.168, 0.310),
		Vector2(0.323, 0.333), Vector2(0.511, 0.302), Vector2(0.710, 0.346), Vector2(0.943, 0.304),
		Vector2(0.975, 0.324), Vector2(0.711, 0.373), Vector2(0.515, 0.330), Vector2(0.323, 0.360),
		Vector2(0.170, 0.335), Vector2(0.026, 0.378)])
	for stretch in [[Vector2(0.025, 0.360), Vector2(0.168, 0.310), Vector2(0.323, 0.333)],
			[Vector2(0.586, 0.319), Vector2(0.710, 0.346), Vector2(0.943, 0.304)]]:
		var cap := PackedVector2Array()
		for point: Vector2 in stretch:
			cap.append(point * extent)
		canvas.draw_polyline(cap, Color("565b4c"), 2.2, true)


static func _distant_house(canvas: CanvasItem, extent: Vector2, left: Vector2, size: Vector2, roof: Color) -> void:
	var front_left := left + Vector2(0.0, -size.y * 0.55)
	var front_right := front_left + Vector2(size.x, 0.0)
	var back := Vector2(size.x * 0.22, -size.y * 0.22)
	var ridge := Vector2(size.x * 0.20, -size.y * 0.48)
	var right := left + Vector2(size.x, 0.0)
	land(canvas, extent, Color("3e473b"), [front_left, front_right, right, left])
	land(canvas, extent, Color("363e35"), [front_right, front_right + back, right + back, right])
	land(canvas, extent, roof.darkened(0.19), [front_left, front_left + ridge, front_right + ridge, front_right])
	land(canvas, extent, roof, [front_left + ridge, front_left + ridge + back, front_right + back, front_right])
	canvas.draw_line(front_left * extent, front_right * extent, Color("303b33"), 2.0, true)
	flagstone(canvas, (left + Vector2(size.x * 0.65, -size.y * 0.33)) * extent,
		Vector2(size.x * 0.13, size.y * 0.18) * extent, Color("343c33"))


static func _paint_road_repairs(canvas: CanvasItem, extent: Vector2, gate: Vector2, cell_size: float) -> void:
	var end := Vector2(extent.x * 0.912, extent.y * 0.959)
	for sample: Vector3 in [Vector3(0.27, -0.48, 0.24), Vector3(0.32, 0.52, 0.19),
			Vector3(0.48, -0.44, 0.32), Vector3(0.52, -0.56, 0.20), Vector3(0.72, 0.40, 0.32),
			Vector3(0.77, 0.48, 0.22), Vector3(0.90, -0.36, 0.29)]:
		var at := gate.lerp(end, sample.x) + Vector2(sample.y, 0.0) * cell_size
		var measure := Vector2(sample.z, sample.z * 0.40) * cell_size
		flagstone(canvas, at + Vector2(0.0, 1.6), measure, Color("594c3a"))
		flagstone(canvas, at, measure, Color("706149"))


static func land(canvas: CanvasItem, extent: Vector2, color: Color, points: Array[Vector2]) -> void:
	var contour := PackedVector2Array()
	for point in points:
		contour.append((point * extent).clamp(Vector2(14, 14), extent - Vector2(14, 14)))
	canvas.draw_colored_polygon(contour, color)


static func _lamp_pool(canvas: CanvasItem, position: Vector2, size: Vector2) -> void:
	flagstone(canvas, position, size, Color(LANTERN_WARMTH, 0.08))
	flagstone(canvas, position, size * 0.72, Color(LANTERN_WARMTH, 0.115))
	flagstone(canvas, position, size * 0.43, Color(LANTERN_WARMTH, 0.13))


static func flagstone(canvas: CanvasItem, at: Vector2, measure: Vector2, color: Color) -> void:
	canvas.draw_colored_polygon(PackedVector2Array([at + Vector2(-0.54, 0.07) * measure,
		at + Vector2(-0.38, -0.45) * measure, at + Vector2(0.37, -0.43) * measure,
		at + Vector2(0.54, 0.16) * measure, at + Vector2(0.34, 0.52) * measure,
		at + Vector2(-0.38, 0.47) * measure]), color)
