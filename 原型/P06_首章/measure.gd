extends Node

var frames: Dictionary = {}
var scene := ""
var prior := 0
var render_frames: Dictionary = {}
var profile_view: SubViewport
var transition_frames: Dictionary = {}
var _profile_app: Control
var _tree_started := 0
var _draw_started := 0
var _last_draw := []


func profile_render(view: SubViewport, app: Control) -> void:
	if view == null or DisplayServer.get_name() == "headless":
		return
	profile_view = view
	_profile_app = app
	RenderingServer.viewport_set_measure_render_time(view.get_viewport_rid(), true)
	get_tree().process_frame.connect(_start_tree_frame)
	RenderingServer.frame_pre_draw.connect(_start_draw)
	RenderingServer.frame_post_draw.connect(_end_draw)


func _start_tree_frame() -> void:
	_tree_started = Time.get_ticks_usec()


func _start_draw() -> void:
	if not scene.is_empty():
		_draw_started = Time.get_ticks_usec()


func _end_draw() -> void:
	if _draw_started == 0:
		return
	var elapsed := Time.get_ticks_usec() - _draw_started
	_last_draw = [int(_profile_app.client.frame.get("state_version", -1)),
		str(_profile_app.view.get("battle_memory", {}).get("id", "")),
		_draw_started - _tree_started, elapsed]
	_draw_started = 0


func _process(_delta: float) -> void:
	if scene.is_empty():
		return
	var now := Time.get_ticks_usec()
	if prior > 0:
		frames[scene].append(now - prior)
		if profile_view != null:
			var viewport := profile_view.get_viewport_rid()
			render_frames[scene].append([
				float(now - prior) / 1000.0, Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
				RenderingServer.viewport_get_measured_render_time_cpu(viewport),
				RenderingServer.viewport_get_measured_render_time_gpu(viewport),
				profile_view.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME),
				profile_view.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_PRIMITIVES_IN_FRAME)])
			transition_frames[scene].append([now - prior, _last_draw,
				int(_profile_app.client.frame.get("state_version", -1)), now - _tree_started, _tree_started])
	_last_draw = []
	prior = now


func begin(name: String) -> void:
	scene = name
	frames[scene] = []
	if profile_view != null:
		render_frames[scene] = []
		transition_frames[scene] = []
	_last_draw = []
	prior = 0


func finish() -> void:
	scene = ""
	_draw_started = 0
	prior = 0


func wait_samples(count: int) -> void:
	while frames[scene].size() < count:
		await get_tree().process_frame


func ready_probe(app: Control, control: Button) -> bool:
	if DisplayServer.get_name() == "headless" or control == null or control.disabled:
		return false
	await RenderingServer.frame_post_draw
	var report := FileAccess.open(app.data_dir.path_join("interactive.json"), FileAccess.WRITE)
	if report == null:
		return false
	report.store_string(JSON.stringify({
		"godot_pid": OS.get_process_id(),
		"python_pid": app.client._pid,
		"window": [get_window().size.x, get_window().size.y],
		"video_adapter": RenderingServer.get_video_adapter_name(),
		"graphics_api": RenderingServer.get_video_adapter_api_version(),
		"display_backend": DisplayServer.get_name(),
		"audio_backend": AudioServer.get_driver_name(),
		"focused": get_window().has_focus(),
		"control": control.text,
		"phase": app.view.get("phase"),
		"state_digest": app.client.frame.get("state_digest")
	}))
	report.close()
	return true
