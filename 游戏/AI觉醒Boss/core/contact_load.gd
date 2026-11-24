extends Node3D
## Standalone synthetic presentation load. No CORE, campaign, save or RNG access.
const BOARD = preload("res://board.gd")
const CONTACT_EFFECT = preload("res://core/contact_effect.gd")
const WARMUP_SECONDS = 3.0
const TICK_SECONDS = 0.5
var board
var units: Array = []
var unit_count: int = 8
var benchmark_seconds: float = 30.0
var output: String = ""
var tick: int = 0
var clock: float = 0.0
var started_wall: int = 0
var previous_wall: int = 0
var sample_started_wall: int = 0
var sample_finished_wall: int = 0
var frame_times: Array = []
var status: Label
var observed_arrow_frames: int = 0
var observed_hit_frames: int = 0
var peak_contact_effects: int = 0
var peak_feedback_children: int = 0
var queued_at_sample: int = 0
var dispatched_at_sample: int = 0

func _argument(args: PackedStringArray, flag: String, fallback: String) -> String:
	var index = args.find(flag)
	return args[index + 1] if index >= 0 and index + 1 < args.size() else fallback

func _ready() -> void:
	var args = OS.get_cmdline_user_args()
	unit_count = 48 if _argument(args, "--contact-count", "8") == "48" else 8
	benchmark_seconds = maxf(1.0, float(_argument(args, "--benchmark-seconds", "30")))
	output = _argument(args, "--capture-contact-load", "")
	if not output.is_empty():
		DirAccess.make_dir_recursive_absolute(output)
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	board = BOARD.new()
	add_child(board)
	board.set_grid_mode("battle")
	board.sound.set_enabled(false)
	board.camera.position = Vector3(11, 14, 17)
	board.camera.look_at(Vector3(0, 0.3, 0))
	board.camera.size = 11.6
	board.set_paused(false, 1.0)
	var layer = CanvasLayer.new()
	add_child(layer)
	status = Label.new()
	status.position = Vector2(18, 14)
	status.add_theme_color_override("font_color", Color("fff1d3"))
	status.add_theme_color_override("font_shadow_color", Color("202923"))
	status.add_theme_constant_override("shadow_offset_x", 2)
	status.add_theme_constant_override("shadow_offset_y", 2)
	status.add_theme_font_size_override("font_size", 20)
	layer.add_child(status)
	var half = unit_count / 2
	for i in range(unit_count):
		var actor = i < half
		var pair_index = i if actor else i - half
		var x = 1 + pair_index * 2 if unit_count == 8 else 1 + pair_index % 8
		var y = 2 if unit_count == 8 else 1 + int(pair_index / 8)
		if not actor:
			y += 3
		var role = "shield"
		if actor:
			role = "archer" if pair_index % 2 == 0 else ("lorne" if pair_index % 4 == 1 else "cavalry")
		units.append({"instance_id": i + 1, "unit_type": role,
			"side": "player" if actor else "enemy", "position": [x, y],
			"hp": 99999, "max_hp": 99999, "alive": true, "shield_pool": 0})
	board.show_units(units, [], 0)
	started_wall = Time.get_ticks_usec()
	previous_wall = started_wall

func step() -> void:
	tick += 1
	var events: Array = []
	var half = int(unit_count / 2)
	for i in range(half):
		var actor: Dictionary = units[i]
		var victim: Dictionary = units[i + half]
		var before = int(victim.hp)
		victim.hp = before - 1
		events.append({"tick": tick, "phase": "attack", "action": "attack",
			"actor": actor.instance_id, "side": actor.side, "unit": actor.unit_type,
			"actor_pos": actor.position.duplicate(), "target": victim.instance_id,
			"target_side": victim.side, "target_unit": victim.unit_type,
			"target_pos": victim.position.duplicate(), "damage": 1, "absorbed": 0,
			"target_hp_before": before, "target_hp_after": victim.hp,
			"target_defending": false})
	board.show_units(units, events, tick)

func _process(delta: float) -> void:
	var now = Time.get_ticks_usec()
	var wall_ms = float(now - previous_wall) / 1000.0
	previous_wall = now
	var elapsed = float(now - started_wall) / 1000000.0
	if sample_started_wall == 0 and elapsed >= WARMUP_SECONDS:
		sample_started_wall = now
		queued_at_sample = _queued_count()
		dispatched_at_sample = board.contact_trace.size()
	elif sample_started_wall > 0:
		frame_times.append(wall_ms)
		_observe_effects()
	var sample_elapsed = float(now - sample_started_wall) / 1000000.0 if sample_started_wall > 0 else 0.0
	status.text = "接触表现合成负载 · %d单位 · %d步\n%s · 固定格反复放箭 / 近战命中 · 无战斗AI / 不读取存档" % [unit_count, tick, "预热" if sample_started_wall == 0 else "采样 %.1f / %.0f秒" % [sample_elapsed, benchmark_seconds]]
	clock += maxf(0.0, delta)
	if clock >= TICK_SECONDS:
		clock = fmod(clock, TICK_SECONDS)
		step()
	if sample_started_wall > 0 and sample_elapsed >= benchmark_seconds:
		sample_finished_wall = now
		set_process(false)
		finish_benchmark()

func _observe_effects() -> void:
	var active = 0
	var arrows = 0
	var hits = 0
	for child in board.feedback.get_children():
		if child is CONTACT_EFFECT and not child.finished:
			active += 1
			if child.kind == "arrow":
				arrows += 1
			elif child.kind == "hit":
				hits += 1
	observed_arrow_frames += 1 if arrows > 0 else 0
	observed_hit_frames += 1 if hits > 0 else 0
	peak_contact_effects = maxi(peak_contact_effects, active)
	peak_feedback_children = maxi(peak_feedback_children, board.feedback.get_child_count())

func _queued_count() -> int:
	var count = 0
	for entry in board.contact.trace:
		if entry.action == "queued":
			count += 1
	return count

func _counts(source: Array, action: String = "") -> Dictionary:
	var result = {"release": 0, "impact": 0, "ground": 0, "total": 0}
	for entry in source:
		if not action.is_empty() and entry.get("action", "") != action:
			continue
		var item_kind = str(entry.get("kind", ""))
		result[item_kind] = int(result.get(item_kind, 0)) + 1
		result.total += 1
	return result

func finish_benchmark() -> void:
	# Freeze measurement counters before an extra screenshot wave. Capturing is
	# deliberately outside the timed window and requires a visibly live arrow.
	var queued = _counts(board.contact.trace, "queued")
	var dispatched = _counts(board.contact_trace)
	var queued_sample = int(queued.total) - queued_at_sample
	var dispatched_sample = int(dispatched.total) - dispatched_at_sample
	var model_ok = board.figures.size() == unit_count and board.figures.values().all(func(f): return f.model.get_meta("action_issues", ["unchecked"]).is_empty())
	var sorted = frame_times.duplicate()
	sorted.sort()
	var sum = 0.0
	for value in frame_times:
		sum += float(value)
	var p95 = float(sorted[int((sorted.size() - 1) * 0.95)]) if not sorted.is_empty() else -1.0
	var ok = model_ok and frame_times.size() > 10 and observed_arrow_frames > 0 and observed_hit_frames > 0 and queued_sample > 0 and dispatched_sample > 0 and peak_feedback_children <= 48
	step()
	var screenshot_with_arrow = false
	var deadline = Time.get_ticks_usec() + 1000000
	while Time.get_ticks_usec() < deadline:
		await get_tree().process_frame
		if board.feedback.get_children().any(func(f): return f is CONTACT_EFFECT and f.kind == "arrow" and not f.finished):
			screenshot_with_arrow = true
			break
	await RenderingServer.frame_post_draw
	var image = get_viewport().get_texture().get_image()
	var result = {"passed": ok and screenshot_with_arrow, "unit_count": unit_count,
		"frames": frame_times.size(), "mean_wall_ms": sum / maxi(1, frame_times.size()),
		"p95_wall_ms": p95, "max_wall_ms": sorted[-1] if not sorted.is_empty() else -1,
		"frame_wall_ms": frame_times, "warmup_s": WARMUP_SECONDS,
		"sample_target_s": benchmark_seconds,
		"actual_sample_wall_s": float(sample_finished_wall - sample_started_wall) / 1000000.0,
		"frame_cap": Engine.max_fps, "vsync_mode": DisplayServer.window_get_vsync_mode(),
		"engine": Engine.get_version_info(), "renderer": ProjectSettings.get_setting("rendering/renderer/rendering_method"),
		"cpu": OS.get_processor_name(), "gpu": RenderingServer.get_video_adapter_name(),
		"actual_pixels": [image.get_width(), image.get_height()],
		"resolution": [get_viewport().get_visible_rect().size.x, get_viewport().get_visible_rect().size.y],
		"queued": queued, "dispatched": dispatched,
		"sample_queued": queued_sample, "sample_dispatched": dispatched_sample,
		"observed_arrow_frames": observed_arrow_frames, "observed_hit_frames": observed_hit_frames,
		"peak_contact_effects": peak_contact_effects, "peak_feedback_children": peak_feedback_children,
		"feedback_cap": 48, "screenshot_with_arrow": screenshot_with_arrow,
		"visible_nameplates": board.unit_label_nodes.values().filter(func(node):return node.is_visible_in_tree()).size(),"nameplate_budget":24,
		"scope": "synthetic stationary production-model contact load; half are repeated attack actors, half high-HP targets; fixed event positions, no CORE, battle AI, campaign, saves or RNG; wall-clock frame intervals include rendering, scripts and scheduling, not pure GPU time; screenshot wave excluded from measurement"}
	if not output.is_empty():
		var image_error = image.save_png(output.path_join("benchmark.png"))
		result.passed = result.passed and image_error == OK
		var file = FileAccess.open(output.path_join("load.json"), FileAccess.WRITE)
		if file == null:
			push_error("Cannot write contact-load report: " + output)
			get_tree().quit(1)
			return
		file.store_string(JSON.stringify(result, "  "))
		file.close()
	print(JSON.stringify({"passed": result.passed, "units": unit_count, "frames": frame_times.size(), "p95_wall_ms": p95, "queued": queued.total, "dispatched": dispatched.total}))
	get_tree().quit(0 if result.passed else 1)
