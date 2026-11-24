extends RefCounted

const FRAME := Vector2(480, 438)
const BRUSHES_ART := "res://assets/gray_oak/overlook_brushes.png"
const CLEARED_ART := "res://assets/gray_oak/overlook_cleared.png"


static func art_path(cleared: bool) -> String:
	return CLEARED_ART if cleared else BRUSHES_ART


static func paint(canvas: Control, bounds: Rect2, cleared: bool, font: Font, art: Texture2D, large_text: bool) -> void:
	var scale_factor := bounds.size.x / FRAME.x
	canvas.draw_set_transform_matrix(Transform2D(0.0, Vector2.ONE * scale_factor, 0.0, bounds.position))
	var frame := Rect2(Vector2.ZERO, FRAME)
	if art == null:
		canvas.draw_rect(frame, Color("344343"))
	else:
		canvas.draw_texture_rect(art, frame, false)
	canvas.draw_rect(frame, Color("788477"), false, 1.5)
	if font != null:
		canvas.draw_rect(Rect2(13, 13, 150 if large_text else 122, 39 if large_text else 34), Color("2e2b23"))
		canvas.draw_string(font, Vector2(23, 41 if large_text else 37), "望向根口",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 27 if large_text else 23, Color("e9dbc0"))
		var hint := "放大"
		var hint_size := 25 if large_text else 20
		var width := font.get_string_size(hint, HORIZONTAL_ALIGNMENT_LEFT, -1, hint_size).x + 20.0
		canvas.draw_rect(Rect2(FRAME.x - width - 13, 13, width, 37), Color("2e2b23"))
		canvas.draw_string(font, Vector2(FRAME.x - width - 3, 40), hint,
			HORIZONTAL_ALIGNMENT_LEFT, -1, hint_size, Color("efd39c"))
		var caption := "根口已清理" if cleared else "旧路上有两团枝影"
		canvas.draw_rect(Rect2(0, 402, FRAME.x, 36), Color("302a22"))
		canvas.draw_string(font, Vector2(14, 428 if large_text else 427), caption,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 25 if large_text else 20, Color("e0d5bf"))
	canvas.draw_set_transform_matrix(Transform2D.IDENTITY)
