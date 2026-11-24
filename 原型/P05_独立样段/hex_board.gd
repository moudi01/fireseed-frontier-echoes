extends Control

signal cell_selected(cell: Vector2i)

var map_data: Dictionary = {}
var slice: Dictionary = {}
var danger: Dictionary = {}
var font: Font
var coordinate_map: Dictionary = {}
var selected_id := ""
var _scale := 24.0
var _center := Vector2.ZERO

const TEXT := Color("e9dbc0")
const MUTED := Color("98ada5")
const ACCENT := Color("e7bd75")
const DANGER := Color("f6a073")


func update_board(presentation: Dictionary, member_id: String) -> void:
	map_data = presentation.get("map") if presentation.get("map") is Dictionary else {}
	slice = presentation.get("slice", {})
	danger = presentation.get("danger") if presentation.get("danger") is Dictionary else {}
	selected_id = member_id
	queue_redraw()


func _ready() -> void:
	resized.connect(queue_redraw)


func _grid(q: float, r: float) -> Vector2:
	return Vector2(1.73205 * (q + r / 2.0), 1.5 * r)


func _point(value: Array) -> Vector2:
	return _grid(float(value[0]), float(value[1])) * _scale + _center


func _label(at: Vector2, message: String, color: Color, size_px := 15) -> void:
	if font != null:
		draw_string(font, at, message, HORIZONTAL_ALIGNMENT_LEFT, -1, size_px, color)


func _hex(pos: Vector2, radius: float) -> PackedVector2Array:
	var shape := PackedVector2Array()
	for i in range(6):
		var angle := TAU * (float(i) / 6.0 + 0.25)
		shape.append(pos + Vector2(cos(angle), sin(angle)) * radius)
	return shape


func _draw() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	draw_rect(rect, Color("101d20"))
	for y in range(32, int(size.y), 36):
		for x in range(24, int(size.x), 40):
			draw_circle(Vector2(x, y), 1.0, Color("233335"))
	draw_rect(rect.grow(-14), Color("314343"), false, 1)
	draw_line(Vector2(28, size.y - 43), Vector2(size.x - 28, size.y - 43), Color("314343"), 1)
	_label(Vector2(30, size.y - 22), "◆ 当前位置     ┅ 部署格     ╳ 危险锁定", MUTED)
	coordinate_map.clear()
	var battle_mode: bool = slice.get("phase") == "BATTLE" or slice.get("route", {}).get("contact_pending", false)
	var town := map_data.is_empty()
	var cells: Array = slice.get("town_board_cells", []) if town else map_data.get("battle_cells" if battle_mode else "cells", [])
	if cells.is_empty():
		_draw_waiting()
		return
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	for row in cells:
		var item := _grid(float(row["q"]), float(row["r"]))
		low = low.min(item)
		high = high.max(item)
	var span := high - low
	_scale = minf(37.0, minf((size.x - 130) / (span.x + 3), (size.y - 126) / (span.y + 3)))
	_center = Vector2(size.x / 2.0, (size.y - 38) / 2.0) - (low + high) / 2.0 * _scale
	var deployment: Array = slice.get("town_deploy_cells", []) if town else map_data.get("deploy_cells", [])
	var lit: Array = slice.get("route", {}).get("lit_cells", []) if not battle_mode and not town else []
	for row in cells:
		var cell := Vector2i(int(row["q"]), int(row["r"]))
		var xy := _point([cell.x, cell.y])
		coordinate_map[cell] = xy
		var shape := _hex(xy, _scale * 0.94)
		var filled := Color("2b423c") if row.get("visible", true) else Color("1b2b2c")
		if not row.get("walkable", true):
			filled = Color("35484a")
		if [cell.x, cell.y] in deployment:
			filled = Color("244f4e")
		elif [cell.x, cell.y] in lit:
			filled = Color("594b32")
		draw_colored_polygon(shape, filled)
		shape.append(shape[0])
		draw_polyline(shape, Color("496159") if row.get("visible", true) else Color("2c4241"), 1.1, true)
	if not town and not battle_mode:
		_draw_route()
	else:
		_draw_units()
	if not danger.is_empty():
		_draw_danger()


func _draw_waiting() -> void:
	var origin := size / 2.0 - Vector2(0, 20)
	for radius in [100.0, 73.0, 49.0]:
		draw_arc(origin, radius, 0, TAU, 72, Color("465540"), 1)
	draw_circle(origin, 12, ACCENT)
	draw_line(origin - Vector2(0, 112), origin + Vector2(0, 112), Color("746449"), 1)
	draw_line(origin - Vector2(112, 0), origin + Vector2(112, 0), Color("746449"), 1)
	_label(origin + Vector2(-47, 132), "暮汀 · 入夜", MUTED)


func _draw_route() -> void:
	var anchors := {}
	for entry in map_data.get("objects", []):
		anchors[entry["id"]] = entry["position"]
	for link in slice.get("route", {}).get("links", []):
		if anchors.has(link[0]) and anchors.has(link[1]):
			draw_dashed_line(_point(anchors[link[0]]), _point(anchors[link[1]]), Color("988359"), 2.0, 6.0)
	for entry in map_data.get("objects", []):
		var position := _point(entry["position"])
		var edge := Color("92cbb5") if entry.get("cleared", false) else ACCENT
		draw_circle(position, 8, Color("111d1e"))
		draw_circle(position, 8, edge, false, 2, true)
		_label(position + Vector2(10, -9), str(entry["id"]).replace("B_SUPPORT", "支援").replace("B_MATERIAL", "材料"), TEXT)
	var player := _point(map_data["position"])
	draw_circle(player, 14, Color("645738"))
	draw_colored_polygon(PackedVector2Array([player+Vector2(0,-9),player+Vector2(7,0),player+Vector2(0,9),player+Vector2(-7,0)]), ACCENT)


func _draw_units() -> void:
	var actors: Array = slice.get("actors", [])
	if actors.is_empty():
		actors = slice.get("party", [])
	for actor in actors:
		if float(actor.get("hp", 0)) <= 0 or not actor.get("deployed", true):
			continue
		var grid: Variant = actor.get("pos", actor.get("position"))
		if not grid is Array or grid.size() != 2 or not coordinate_map.has(Vector2i(int(grid[0]), int(grid[1]))):
			continue
		var xy := _point(grid)
		var enemy: bool = actor.get("side") == "enemy"
		var ink := DANGER if enemy else Color("95dbca")
		var radius := minf(17, _scale * 0.53)
		if enemy:
			draw_colored_polygon(PackedVector2Array([xy-Vector2(0,radius),xy+Vector2(radius,radius),xy+Vector2(-radius,radius)]), ink)
		else:
			draw_circle(xy, radius, ink)
		if actor.get("instance_id", actor.get("id")) == selected_id:
			draw_circle(xy, radius + 4, ACCENT, false, 2, true)
		if font != null:
			var token := "敌" if enemy else str(actors.find(actor) + 1)
			var width := font.get_string_size(token, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
			_label(xy + Vector2(-width / 2, 5), token, Color("132221"), 14)


func _draw_danger() -> void:
	for action in danger.get("actions", []):
		if action["side"] != "enemy":
			continue
		for cell in action.get("locked_cells", []):
			var point := _point(cell)
			var shape := _hex(point, _scale * 0.9)
			draw_colored_polygon(shape, Color(0.85, 0.35, 0.23, 0.32))
			shape.append(shape[0])
			draw_polyline(shape, DANGER, 2.5, true)
			var cross := _scale * 0.25
			draw_line(point-Vector2(cross,cross),point+Vector2(cross,cross),DANGER,2,true)
			draw_line(point-Vector2(cross,-cross),point+Vector2(cross,-cross),DANGER,2,true)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		for cell in coordinate_map:
			if event.position.distance_to(coordinate_map[cell]) <= _scale * 0.84:
				cell_selected.emit(cell)
				accept_event()
				return
