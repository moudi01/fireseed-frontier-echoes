extends Control

const NORTH_GATE := "res://assets/town/north_gate_dusk.webp"
const REGISTRY := "res://assets/town/north_gate_registry.webp"
const PLATE_SIZE := Vector2(1536, 1024)
const FULL_SHOT := Rect2(Vector2.ZERO, PLATE_SIZE)
# Framing in the coordinates of the painted north-gate plate.
const ARRIVAL_SHOT := Rect2(250, 225, 1050, 700)
const MAYOR_SHOT := Rect2(686, 190, 795, 530)

var _cue := ""
var _plate: Texture2D
var _gate: Texture2D
var _registry: Texture2D
var _loading_registry := false


func _ready() -> void:
	resized.connect(queue_redraw)
	set_process(false)


func present(cue: String) -> void:
	visible = not cue.is_empty()
	if cue == _cue:
		return
	_cue = cue
	if cue.is_empty():
		_plate = null
		_gate = null
		_registry = null
	elif cue == "TD032":
		if _loading_registry:
			_finish_registry()
		if _registry == null:
			_registry = load(REGISTRY) as Texture2D
		_plate = _registry
	else:
		if _gate == null:
			_gate = load(NORTH_GATE) as Texture2D
		_plate = _gate
		if _registry == null and not _loading_registry:
			_loading_registry = ResourceLoader.load_threaded_request(REGISTRY, "Texture2D") == OK
			set_process(_loading_registry)
	queue_redraw()


func _process(_delta: float) -> void:
	if ResourceLoader.load_threaded_get_status(REGISTRY) != ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		_finish_registry()


func _finish_registry() -> void:
	var completed := ResourceLoader.load_threaded_get(REGISTRY) as Texture2D
	_loading_registry = false
	set_process(false)
	if not _cue.is_empty():
		_registry = completed


func _exit_tree() -> void:
	if _loading_registry:
		_finish_registry()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("152023"))
	if _plate == null:
		return
	var scale_factor := minf((size.x - 28.0) / PLATE_SIZE.x, (size.y - 28.0) / PLATE_SIZE.y)
	if scale_factor <= 0.0:
		return
	var extent := PLATE_SIZE * scale_factor
	var frame := Rect2((size - extent) * 0.5, extent)
	var shot := FULL_SHOT
	match _cue:
		"TD002": shot = ARRIVAL_SHOT
		"TD003": shot = MAYOR_SHOT
	draw_texture_rect_region(_plate, frame, shot)
	draw_rect(frame, Color("53615b"), false, 1.0)
