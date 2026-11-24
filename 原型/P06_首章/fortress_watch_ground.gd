extends RefCounted

const Ground = preload("res://town_ground.gd")


static func paint_gatehouse(canvas: CanvasItem, size: Vector2) -> void:
	Ground.land(canvas, size, Color("36362e"), [
		Vector2(0.018, 0.192), Vector2(0.076, 0.190), Vector2(0.076, 0.168), Vector2(0.118, 0.171),
		Vector2(0.118, 0.189), Vector2(0.179, 0.186), Vector2(0.179, 0.161), Vector2(0.226, 0.163),
		Vector2(0.226, 0.185), Vector2(0.335, 0.181), Vector2(0.659, 0.179), Vector2(0.754, 0.184),
		Vector2(0.754, 0.160), Vector2(0.803, 0.163), Vector2(0.803, 0.186), Vector2(0.881, 0.188),
		Vector2(0.881, 0.169), Vector2(0.927, 0.172), Vector2(0.927, 0.190), Vector2(0.982, 0.196),
		Vector2(0.982, 0.289), Vector2(0.018, 0.289)])
	Ground.land(canvas, size, Color("494438"), [
		Vector2(0.379, 0.276), Vector2(0.383, 0.169), Vector2(0.420, 0.148), Vector2(0.567, 0.146),
		Vector2(0.606, 0.163), Vector2(0.609, 0.276)])
	_tower(canvas, size, 0.365, 0.093, 0.090)
	_tower(canvas, size, 0.551, 0.077, 0.097)
	for seam in [0.173, 0.190]:
		canvas.draw_line(Vector2(0.455, seam) * size, Vector2(0.551, seam - 0.005) * size,
			Color("595040"), 1.15, true)
	Ground.land(canvas, size, Color("5f5543"), [
		Vector2(0.452, 0.237), Vector2(0.457, 0.188), Vector2(0.468, 0.171), Vector2(0.489, 0.155),
		Vector2(0.512, 0.153), Vector2(0.535, 0.166), Vector2(0.547, 0.186), Vector2(0.553, 0.237)])
	Ground.land(canvas, size, Color("292b27"), [
		Vector2(0.463, 0.237), Vector2(0.467, 0.191), Vector2(0.478, 0.176), Vector2(0.496, 0.165),
		Vector2(0.512, 0.164), Vector2(0.528, 0.176), Vector2(0.538, 0.194), Vector2(0.542, 0.237)])
	for upright in [0.479, 0.493, 0.507, 0.521, 0.535]:
		canvas.draw_line(Vector2(upright, 0.194 - 0.020 * (1.0 - absf(upright - 0.507) / 0.03)) * size,
			Vector2(upright, 0.234) * size, Color("413a30"), 1.7, true)
	canvas.draw_line(Vector2(0.468, 0.208) * size, Vector2(0.539, 0.208) * size, Color("3c372e"), 1.5, true)


static func _tower(canvas: CanvasItem, size: Vector2, left: float, top: float, width: float) -> void:
	var right := left + width
	var front := right - 0.020
	Ground.land(canvas, size, Color("3f3b32"), [
		Vector2(left, top + 0.025), Vector2(front, top), Vector2(right, top + 0.024),
		Vector2(right, 0.279), Vector2(left, 0.279)])
	Ground.land(canvas, size, Color("514838"), [
		Vector2(left, top + 0.022), Vector2(left, top - 0.008), Vector2(left + 0.018, top - 0.008),
		Vector2(left + 0.018, top + 0.013), Vector2(left + 0.041, top + 0.012),
		Vector2(left + 0.041, top - 0.010), Vector2(front, top - 0.012), Vector2(front, 0.270),
		Vector2(left, 0.275)])
	for course in range(3):
		var y := top + 0.050 + float(course) * 0.036
		canvas.draw_line(Vector2(left + 0.002, y) * size, Vector2(front, y - 0.007) * size,
			Color("443d31"), 1.15, true)
	var slit := Vector2(left + 0.028, top + 0.060)
	canvas.draw_rect(Rect2(slit * size, Vector2(0.011, 0.048) * size), Color("2a2d28"))
	canvas.draw_rect(Rect2((slit + Vector2(0.002, 0.008)) * size, Vector2(0.004, 0.032) * size),
		Color("84704e"))


static func paint_approach(canvas: CanvasItem, size: Vector2, first_cell: float, cell_size: float) -> void:
	var start := size.y * 0.237
	var end := first_cell - cell_size * 0.58
	var length := end - start
	if length < 10.0:
		return
	var axis := size.x * 0.502
	canvas.draw_colored_polygon(PackedVector2Array([
		Vector2(axis - cell_size * 0.96, start), Vector2(axis + cell_size * 0.95, start),
		Vector2(axis + cell_size * 1.58, end), Vector2(axis - cell_size * 1.77, end)
	]), Color("494237"))
	for course in range(3):
		var depth := (float(course) + 0.51) / 3.0
		var span := cell_size * lerpf(0.81, 1.24, depth)
		var y := lerpf(start, end, depth)
		for lane in [-1.0, 0.0, 1.0]:
			var at := Vector2(axis + lane * span + float(course - 1) * 3.8, y + 1.8 * lane)
			var stone_color := Color("585044") if lane == 0.0 else Color("51483b")
			var extent := Vector2(span * (0.82 + lane * 0.09), length * 0.24)
			canvas.draw_colored_polygon(PackedVector2Array([at + Vector2(-0.53, 0.41) * extent,
				at + Vector2(-0.42, -0.41) * extent, at + Vector2(0.42, -0.48) * extent,
				at + Vector2(0.51, 0.12) * extent, at + Vector2(0.34, 0.48) * extent]), stone_color)
