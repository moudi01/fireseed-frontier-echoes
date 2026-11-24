extends RefCounted
## Carried equipment is hidden on downed poses. No death/accounting state is set.

static func apply_clip(model: Node, clip: String) -> int:
	var hidden := 0
	for node in model.find_children("Equipment_*", "Node3D", true, false):
		if not node.has_meta("carried_visibility"):
			node.set_meta("carried_visibility", node.visible)
		node.visible = bool(node.get_meta("carried_visibility")) and clip != "dying_backwards"
		if not node.visible: hidden += 1
	return hidden
