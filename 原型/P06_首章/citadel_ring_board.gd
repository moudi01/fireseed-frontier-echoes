class_name CitadelRingBoard
extends RefCounted

## Shared 2D/3D board presentation helper for CITADEL_RING (90 cells, DEMON + ADMIN finale battles).
## Live draws strictly obey authoritative terrain passed by the caller; PREVIEW_CELLS is used ONLY
## by the standalone preview script.

const BOARD_ID := "CITADEL_RING"
const FIELD_ART := "res://assets/citadel_ring/citadel_ring_ink.png"
const TERRAIN_PROPS := {
	"HIGH_OBSTACLE": "citadel-pillar",
	"LOW_OBSTACLE": "citadel-plinth",
	"HIGH_GROUND": "citadel-dais",
}

# Preview-only layout matching local-handoff.json (never hardcoded into live draw_terrain)
const PREVIEW_CELLS := {
	"LOW_OBSTACLE": [Vector2i(2, 3), Vector2i(5, 3)],
	"HIGH_GROUND": [Vector2i(0, 4), Vector2i(5, 4)],
	"HIGH_OBSTACLE": [Vector2i(2, 4), Vector2i(3, 4)],
}


static func field_art_path(board_id: String = BOARD_ID) -> String:
	if board_id != BOARD_ID:
		return ""
	return FIELD_ART if ResourceLoader.exists(FIELD_ART, "Texture2D") else ""


static func is_active(view_state: Variant) -> bool:
	if not (view_state is Dictionary):
		return false
	var st: Dictionary = view_state
	if str(st.get("phase", "")) != "BATTLE":
		return false
	var map_data: Variant = st.get("map", {})
	if not (map_data is Dictionary):
		return false
	return str((map_data as Dictionary).get("board_id", "")) == BOARD_ID and not field_art_path(BOARD_ID).is_empty()


static func draw_terrain(canvas: CanvasItem, coordinate_map: Dictionary, terrain: Dictionary,
		hex_scale: float, sideways: bool = false) -> void:
	if canvas == null or coordinate_map.is_empty():
		return
	var r := maxf(10.0, hex_scale * 0.88)
	for kind in ["HIGH_GROUND", "LOW_OBSTACLE", "HIGH_OBSTACLE"]:
		var cells: Variant = terrain.get(kind, [])
		if not (cells is Array):
			continue
		for raw in cells:
			var key := _cell_key(raw)
			if not coordinate_map.has(key):
				continue
			var pos: Vector2 = coordinate_map[key]
			var poly := _hex_poly(pos, r, sideways)
			match kind:
				"HIGH_GROUND":
					canvas.draw_colored_polygon(poly, Color(0.76, 0.72, 0.62, 0.42))
					canvas.draw_polyline(poly + PackedVector2Array([poly[0]]), Color(0.58, 0.46, 0.28, 0.85), 2.0)
				"LOW_OBSTACLE":
					canvas.draw_colored_polygon(poly, Color(0.42, 0.40, 0.38, 0.50))
					canvas.draw_polyline(poly + PackedVector2Array([poly[0]]), Color(0.28, 0.26, 0.24, 0.85), 2.0)
				"HIGH_OBSTACLE":
					canvas.draw_colored_polygon(poly, Color(0.28, 0.26, 0.25, 0.62))
					canvas.draw_polyline(poly + PackedVector2Array([poly[0]]), Color(0.64, 0.48, 0.28, 0.90), 2.2)


static func _cell_key(raw: Variant) -> Vector2i:
	if raw is Vector2i:
		return raw
	if raw is Array and raw.size() >= 2:
		return Vector2i(int(raw[0]), int(raw[1]))
	return Vector2i(999, 999)


static func _hex_poly(center: Vector2, radius: float, sideways: bool) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var offset := 0.0 if sideways else 30.0
	for i in range(6):
		var a := deg_to_rad(60.0 * i + offset)
		pts.append(center + Vector2(cos(a) * radius, sin(a) * radius * 0.62))
	return pts
