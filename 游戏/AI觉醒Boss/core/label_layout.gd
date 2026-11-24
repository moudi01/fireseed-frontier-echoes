extends RefCounted
## Deterministic label placement. This module only reads values: it never
## touches nodes, cameras, time, randomness, files or game state, and it never
## mutates the supplied items or obstacles.

const MAX_LAYERS := 16
const MAX_CANDIDATES_PER_LAYER := 4
const PLACED_GAP := 3.0
const ROW_GAP := 4.0
const COLUMN_GAP := 4.0
const EPSILON := 0.001

## items: [{id:int, anchor:Vector2, size:Vector2, priority:int,
##          preferred_offset:Vector2 (optional)}]
## Returns one entry per input item, sorted by priority descending, id ascending
## and original order. Duplicate ids are rejected after their first occurrence.
static func solve(items: Array, safe: Rect2, obstacles: Array = [], max_shift: float = 96.0) -> Array:
	var safe_ok := _rect_is_finite(safe) and safe.size.x > 0.0 and safe.size.y > 0.0
	var shift_limit := max_shift
	if not is_finite(shift_limit) or shift_limit < 0.0:
		shift_limit = 0.0

	var clean_obstacles: Array = []
	for obstacle in obstacles:
		if typeof(obstacle) != TYPE_RECT2:
			continue
		var obstacle_rect: Rect2 = obstacle
		if not _rect_is_finite(obstacle_rect) or obstacle_rect.size.x < 0.0 or obstacle_rect.size.y < 0.0:
			continue
		clean_obstacles.append(obstacle_rect)

	var records: Array = []
	var seen_ids: Dictionary = {}
	for index in range(items.size()):
		var source = items[index]
		var record := {
			"id": 0,
			"anchor": Vector2.ZERO,
			"size": Vector2.ZERO,
			"priority": 0,
			"preferred": Vector2.ZERO,
			"has_preferred": false,
			"index": index,
			"valid": false,
		}
		if typeof(source) == TYPE_DICTIONARY:
			var id_state := _read_id(source.get("id", null))
			record["id"] = int(id_state["value"])
			record["priority"] = _read_int(source.get("priority", 0))
			# The first occurrence owns the id even when that occurrence is
			# itself invalid; a later duplicate can never displace it.
			var is_duplicate := seen_ids.has(record["id"])
			if is_duplicate:continue
			if bool(id_state["ok"]) and not is_duplicate:
				seen_ids[record["id"]] = true
				var anchor = source.get("anchor", null)
				var size = source.get("size", null)
				var anchor_ok: bool = typeof(anchor) == TYPE_VECTOR2 and anchor.is_finite()
				var size_ok: bool = (
					typeof(size) == TYPE_VECTOR2 and size.is_finite()
					and size.x > 0.0 and size.y > 0.0
				)
				if (anchor_ok and size_ok and safe_ok
						and size.x <= safe.size.x and size.y <= safe.size.y):
					record["anchor"] = anchor
					record["size"] = size
					record["valid"] = true
					var preferred = source.get("preferred_offset", null)
					if (typeof(preferred) == TYPE_VECTOR2 and preferred.is_finite()
							and preferred.length() <= shift_limit + EPSILON):
						record["preferred"] = preferred
						record["has_preferred"] = true
		records.append(record)

	# Insertion sort keeps equal priority/id entries in their original order.
	for i in range(1, records.size()):
		var current: Dictionary = records[i]
		var j := i - 1
		while j >= 0 and _before(current, records[j]):
			records[j + 1] = records[j]
			j -= 1
		records[j + 1] = current

	var output: Array = []
	var placed_rects: Array = []
	for record in records:
		var id := int(record["id"])
		if not bool(record["valid"]):
			output.append(_hidden(id, "invalid"))
			continue
		var placement := _best_placement(record, safe, clean_obstacles, placed_rects, shift_limit)
		if placement.is_empty():
			output.append(_hidden(id, "no_space"))
			continue
		placed_rects.append(placement["rect"])
		output.append({
			"id": id,
			"visible": true,
			"rect": placement["rect"],
			"offset": placement["offset"],
			"reason": "",
		})
	return output

static func _best_placement(record: Dictionary, safe: Rect2, obstacles: Array, placed: Array, max_shift: float) -> Dictionary:
	var anchor: Vector2 = record["anchor"]
	var size: Vector2 = record["size"]
	var candidates: Array = []
	var seen_offsets: Dictionary = {}
	if bool(record["has_preferred"]):
		_add_candidate(candidates, seen_offsets, record["preferred"])
	_add_candidate(candidates, seen_offsets, Vector2.ZERO)

	# Row shifts are the primary escape route; a few horizontal candidates per
	# layer handle anchors that sit directly under a wide obstacle.
	var row_step := size.y + ROW_GAP
	var column_step := size.x + COLUMN_GAP
	for layer in range(1, MAX_LAYERS + 1):
		var rows := row_step * float(layer)
		var columns := column_step * float(layer)
		var layer_candidates: Array = [
			Vector2(0.0, -rows),
			Vector2(0.0, rows),
			Vector2(-columns, 0.0),
			Vector2(columns, 0.0),
		]
		var added := 0
		for offset in layer_candidates:
			if added >= MAX_CANDIDATES_PER_LAYER:
				break
			if _add_candidate(candidates, seen_offsets, offset):
				added += 1

	for offset in candidates:
		var fitted := _fit(anchor, size, offset, safe, max_shift)
		if fitted.is_empty():
			continue
		var rect: Rect2 = fitted["rect"]
		if _intersects_any(rect, obstacles):
			continue
		if not _keeps_gap(rect, placed):
			continue
		return fitted
	return {}

static func _fit(anchor: Vector2, size: Vector2, offset: Vector2, safe: Rect2, max_shift: float) -> Dictionary:
	var desired := anchor + offset
	if not desired.is_finite():
		return {}
	var half := size * 0.5
	var min_center := safe.position + half
	var max_center := safe.position + safe.size - half
	var center := Vector2(
		clampf(desired.x, min_center.x, max_center.x),
		clampf(desired.y, min_center.y, max_center.y)
	)
	if not center.is_finite():
		return {}
	var actual := center - anchor
	if not actual.is_finite() or actual.length() > max_shift + EPSILON:
		return {}
	return {"rect": Rect2(center - half, size), "offset": actual}

static func _add_candidate(candidates: Array, seen_offsets: Dictionary, offset: Vector2) -> bool:
	if not offset.is_finite() or seen_offsets.has(offset):
		return false
	seen_offsets[offset] = true
	candidates.append(offset)
	return true

static func _intersects_any(rect: Rect2, obstacles: Array) -> bool:
	for obstacle in obstacles:
		var obstacle_rect: Rect2 = obstacle
		if rect.intersects(obstacle_rect):
			return true
	return false

static func _keeps_gap(rect: Rect2, placed: Array) -> bool:
	for other in placed:
		var other_rect: Rect2 = other
		var horizontal := maxf(other_rect.position.x - rect.end.x, rect.position.x - other_rect.end.x)
		var vertical := maxf(other_rect.position.y - rect.end.y, rect.position.y - other_rect.end.y)
		if horizontal < PLACED_GAP and vertical < PLACED_GAP:
			return false
	return true

static func _before(a: Dictionary, b: Dictionary) -> bool:
	var a_priority := int(a["priority"])
	var b_priority := int(b["priority"])
	if a_priority != b_priority:
		return a_priority > b_priority
	var a_id := int(a["id"])
	var b_id := int(b["id"])
	if a_id != b_id:
		return a_id < b_id
	return int(a["index"]) < int(b["index"])

static func _hidden(id: int, reason: String) -> Dictionary:
	return {
		"id": id,
		"visible": false,
		"rect": Rect2(),
		"offset": Vector2.ZERO,
		"reason": reason,
	}

static func _read_id(value) -> Dictionary:
	var value_type := typeof(value)
	if value_type == TYPE_INT:
		return {"ok": true, "value": int(value)}
	if value_type == TYPE_FLOAT:
		var number := float(value)
		if is_finite(number):
			return {"ok": true, "value": int(number)}
	return {"ok": false, "value": 0}

static func _read_int(value) -> int:
	var value_type := typeof(value)
	if value_type == TYPE_INT:
		return int(value)
	if value_type == TYPE_FLOAT:
		var number := float(value)
		if is_finite(number):
			return int(number)
	return 0

static func _rect_is_finite(rect: Rect2) -> bool:
	return rect.position.is_finite() and rect.size.is_finite() and (rect.position + rect.size).is_finite()
