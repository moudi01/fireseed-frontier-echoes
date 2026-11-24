extends RefCounted

const Ground = preload("res://town_ground.gd")
const BREACH := 0.667


static func paint_wall(canvas: CanvasItem, size: Vector2) -> void:
	Ground.land(canvas, size, Color("444439"), [
		Vector2(0.064, 0.221), Vector2(0.078, 0.188), Vector2(0.191, 0.178), Vector2(0.191, 0.162),
		Vector2(0.285, 0.158), Vector2(0.285, 0.174), Vector2(0.447, 0.177), Vector2(0.512, 0.164),
		Vector2(0.596, 0.165), Vector2(0.610, 0.190), Vector2(0.598, 0.204), Vector2(0.614, 0.222),
		Vector2(0.624, 0.249), Vector2(0.064, 0.254)])
	Ground.land(canvas, size, Color("4b493d"), [
		Vector2(0.708, 0.252), Vector2(0.712, 0.227), Vector2(0.727, 0.208), Vector2(0.716, 0.191),
		Vector2(0.729, 0.163), Vector2(0.801, 0.166), Vector2(0.835, 0.186), Vector2(0.909, 0.189),
		Vector2(0.945, 0.207), Vector2(0.949, 0.253)])
	Ground.land(canvas, size, Color("383b33"), [
		Vector2(0.603, 0.248), Vector2(0.625, 0.212), Vector2(0.619, 0.195), Vector2(0.655, 0.168),
		Vector2(0.683, 0.168), Vector2(0.704, 0.199), Vector2(0.697, 0.219), Vector2(0.726, 0.248)])
	for course in range(3):
		var y := 0.195 + course * 0.019
		var ink := Color("353831")
		canvas.draw_line(Vector2(0.081, y + 0.007) * size, Vector2(0.587, y - 0.004) * size, ink, 1.25, true)
		canvas.draw_line(Vector2(0.735, y - 0.003) * size, Vector2(0.939, y + 0.005) * size, ink, 1.25, true)
		for joint in [0.23, 0.35, 0.47, 0.55, 0.76, 0.88]:
			var x: float = joint + (0.014 if course % 2 == 0 else -0.010)
			canvas.draw_line(Vector2(x, y + 0.002) * size, Vector2(x - 0.004, y + 0.013) * size, ink, 1.0, true)
	_pier(canvas, size, 0.162, 0.140)
	_pier(canvas, size, 0.516, 0.151)
	_pier(canvas, size, 0.814, 0.153)
	Ground.land(canvas, size, Color("5b5443"), [
		Vector2(0.596, 0.165), Vector2(0.611, 0.179), Vector2(0.610, 0.194), Vector2(0.601, 0.205),
		Vector2(0.615, 0.219), Vector2(0.622, 0.248), Vector2(0.606, 0.249), Vector2(0.595, 0.221)])
	Ground.land(canvas, size, Color("5a5141"), [
		Vector2(0.729, 0.163), Vector2(0.739, 0.174), Vector2(0.729, 0.193), Vector2(0.736, 0.206),
		Vector2(0.723, 0.222), Vector2(0.718, 0.251), Vector2(0.705, 0.251), Vector2(0.712, 0.222),
		Vector2(0.722, 0.208), Vector2(0.714, 0.194)])


static func _pier(canvas: CanvasItem, size: Vector2, x: float, crest: float) -> void:
	Ground.land(canvas, size, Color("383a31"), [
		Vector2(x - 0.022, crest + 0.013), Vector2(x + 0.015, crest), Vector2(x + 0.033, crest + 0.014),
		Vector2(x + 0.038, 0.247), Vector2(x - 0.030, 0.247)])
	Ground.land(canvas, size, Color("504b3e"), [
		Vector2(x - 0.022, crest + 0.013), Vector2(x + 0.015, crest),
		Vector2(x + 0.017, 0.245), Vector2(x - 0.030, 0.247)])
	canvas.draw_line(Vector2(x - 0.025, 0.217) * size, Vector2(x + 0.034, 0.215) * size, Color("393b32"), 1.2, true)


static func paint_service_lane(canvas: CanvasItem, size: Vector2, first_cell: float, cell_size: float) -> void:
	var start := Vector2(size.x * BREACH, size.y * 0.239)
	var end := Vector2(size.x * 0.61, first_cell - cell_size * 0.65)
	if end.y - start.y < 12.0:
		return
	var near_width := cell_size * 1.30
	var far_width := cell_size * 0.90
	canvas.draw_colored_polygon(PackedVector2Array([
		start - Vector2(far_width, 0), start + Vector2(far_width, 0),
		end + Vector2(near_width, 0), end - Vector2(near_width, 0)
	]), Color("444438"))
	for course in range(4):
		var depth := (course + 0.5) / 4.0
		var middle := start.lerp(end, depth)
		var half := lerpf(far_width, near_width, depth)
		var height := (end.y - start.y) * 0.17
		for lane in [-1.0, 0.0, 1.0]:
			var stone := middle + Vector2(lane * half * 0.61 + (2.0 if course % 2 == 0 else -2.0), lane * 1.2)
			var tone := Color("565244") if lane == 0.0 and course != 2 else Color("4e4b3e")
			Ground.flagstone(canvas, stone, Vector2(half * 0.53, height), tone)
	for side in [-1.0, 1.0]:
		var ledge := start.lerp(end, 0.36) + Vector2(side * cell_size * 1.13, cell_size * 0.08)
		Ground.flagstone(canvas, ledge, Vector2(cell_size * 0.42, cell_size * 0.14), Color("514c3e"))
