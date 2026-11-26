extends RefCounted

# Region-and-board identity for the two ordinary DUAL_FLANK field backdrops (issue #13).
# RG06 雾痕林缘 and RG08 炉灰荒径 share the same real 79-cell DUAL_FLANK board, so the picture is chosen
# by region AND board_id (never by board alone, never changing cells or gameplay).
# Painted for hex_board's sideways projection inside the 1041x669 board node; the texture is stretched into
# Rect2(4, 4, size - 8) like every other field art. Recipe: _tools/美术/build_dual_flank_regional_backdrops.py
# Minimal runtime hook (owned by the hex_board.gd / main.gd integrator, not wired here):
#   var art := DualFlankRegional.field_art_path(region, map_data.get("board_id", ""))
#   -> pass it through the same load / prefetch path as ForgeCrossing.field_art_path(); "" keeps the generic floor.
# Terrain props, anchors and warnings stay on the runtime layer; the picture carries no gameplay marks.

const BOARD_ID := "DUAL_FLANK"
const FIELD_ART := {
	"RG06": "res://assets/dual_flank/rg06_mist_edge_ink.png",
	"RG08": "res://assets/dual_flank/rg08_ash_road_ink.png",
}


static func field_art_path(region: String, board_id: String) -> String:
	return FIELD_ART.get(region, "") if board_id == BOARD_ID else ""
