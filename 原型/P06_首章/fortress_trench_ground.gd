extends RefCounted

const Ground = preload("res://town_ground.gd")


static func paint_earthwork(canvas: CanvasItem, size: Vector2) -> void:
	Ground.land(canvas, size, Color("3d3e34"), [
		Vector2(0.054, 0.246), Vector2(0.113, 0.216), Vector2(0.207, 0.193), Vector2(0.324, 0.188),
		Vector2(0.393, 0.165), Vector2(0.578, 0.176), Vector2(0.644, 0.190), Vector2(0.727, 0.186),
		Vector2(0.884, 0.216), Vector2(0.952, 0.250), Vector2(0.952, 0.280), Vector2(0.054, 0.280)])
	Ground.land(canvas, size, Color("484538"), [
		Vector2(0.113, 0.230), Vector2(0.218, 0.210), Vector2(0.361, 0.204), Vector2(0.409, 0.183),
		Vector2(0.558, 0.189), Vector2(0.622, 0.209), Vector2(0.725, 0.202), Vector2(0.871, 0.231),
		Vector2(0.893, 0.260), Vector2(0.098, 0.260)])
	Ground.land(canvas, size, Color("3b3c32"), [
		Vector2(0.114, 0.236), Vector2(0.278, 0.220), Vector2(0.497, 0.216), Vector2(0.682, 0.224),
		Vector2(0.881, 0.241), Vector2(0.892, 0.264), Vector2(0.103, 0.270)])
	for index in range(8):
		var x := 0.347 + index * 0.053
		var height := [0.053, 0.035, 0.063, 0.049][index % 4] as float
		var base := Vector2(x, 0.222 + 0.016 * absf(x - 0.50))
		var lean := (index % 3 - 1) * 0.007
		Ground.land(canvas, size, Color("332f29"), [base - Vector2(0.005, 0),
			base + Vector2(lean - 0.004, -height * 0.83), base + Vector2(lean + 0.007, -height),
			base + Vector2(0.008, 0)])
		canvas.draw_line((base + Vector2(lean + 0.007, -height)) * size,
			(base + Vector2(0.008, -0.012)) * size, Color("50463a"), 1.0, true)


static func paint_trench(canvas: CanvasItem, size: Vector2, first_cell: float, cell_size: float) -> void:
	var bank := size.y * 0.242
	var lip := first_cell - cell_size * 0.62
	var depth := lip - bank
	if depth < 12.0:
		return
	var far := bank + depth * 0.12
	var floor_y := bank + depth * 0.65
	canvas.draw_colored_polygon(PackedVector2Array([
		Vector2(size.x * 0.183, far), Vector2(size.x * 0.322, bank), Vector2(size.x * 0.638, bank + depth * 0.18),
		Vector2(size.x * 0.845, far), Vector2(size.x * 0.811, floor_y), Vector2(size.x * 0.668, lip),
		Vector2(size.x * 0.369, lip - depth * 0.14), Vector2(size.x * 0.217, floor_y)
	]), Color("4b4538"))
	canvas.draw_colored_polygon(PackedVector2Array([
		Vector2(size.x * 0.216, far + depth * 0.13), Vector2(size.x * 0.327, bank + depth * 0.17),
		Vector2(size.x * 0.647, bank + depth * 0.33), Vector2(size.x * 0.812, far + depth * 0.13),
		Vector2(size.x * 0.778, floor_y - depth * 0.04), Vector2(size.x * 0.661, lip - depth * 0.23),
		Vector2(size.x * 0.369, lip - depth * 0.35), Vector2(size.x * 0.248, floor_y)
	]), Color("2c2d27"))
	canvas.draw_polyline(PackedVector2Array([
		Vector2(size.x * 0.252, floor_y), Vector2(size.x * 0.368, lip - depth * 0.33),
		Vector2(size.x * 0.661, lip - depth * 0.21), Vector2(size.x * 0.777, floor_y - depth * 0.04)
	]), Color("605443"), 1.40, true)
	for index in range(8):
		var progress := (index + 0.55) / 8.0
		var x := lerpf(size.x * 0.31, size.x * 0.72, progress)
		var y := lerpf(lip - depth * 0.35, lip - depth * 0.26, progress) + (2.0 if index % 2 == 0 else -1.0)
		Ground.flagstone(canvas, Vector2(x, y), Vector2(cell_size * (0.32 + 0.07 * float(index % 3)), depth * 0.19),
			Color("514a3d") if index % 2 == 0 else Color("464236"))
