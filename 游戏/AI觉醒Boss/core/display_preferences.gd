extends Node
## Local display preference only. Never opens a campaign store.
signal changed
var config_path=""
var save_error=""
var window_size=Vector2i(1600,900)
var window_position=Vector2i.ZERO
var busy=false
func _ready():
	process_mode=Node.PROCESS_MODE_ALWAYS
	if DisplayServer.get_name()=="headless":return
	window_size=DisplayServer.window_get_size();window_position=DisplayServer.window_get_position()
	var args=OS.get_cmdline_user_args()
	config_path=ProjectSettings.globalize_path("res://local/display.cfg") if OS.has_feature("editor") else OS.get_executable_path().get_base_dir().path_join("display.cfg")
	if args.has("--display-config") and args.find("--display-config")+1<args.size():config_path=args[args.find("--display-config")+1]
	var engine_args=OS.get_cmdline_args()
	# Explicit run/test geometry wins over remembered display mode.
	for flag in ["--resolution","--fullscreen","-f","--windowed","-w","--maximized","-m"]:
		if engine_args.has(flag):return
	if args.has("--no-display-restore"):return
	var cfg=ConfigFile.new()
	if cfg.load(config_path)==OK and cfg.get_value("display","mode","")=="borderless":call_deferred("set_fullscreen",true,false)
func is_fullscreen() -> bool:
	return DisplayServer.window_get_mode() in [DisplayServer.WINDOW_MODE_FULLSCREEN,DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN]
func _input(event):
	if event is InputEventKey and event.keycode==KEY_F11 and event.pressed and not event.echo:
		get_viewport().set_input_as_handled();toggle()
func toggle():set_fullscreen(not is_fullscreen())
func set_fullscreen(value: bool,persist=true):
	if busy or DisplayServer.get_name()=="headless":return
	busy=true
	if value:
		if not is_fullscreen():window_size=DisplayServer.window_get_size();window_position=DisplayServer.window_get_position()
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS,true)
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		# Godot fullscreen forces the borderless flag; explicitly undo it on return.
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS,false)
		var usable=DisplayServer.screen_get_usable_rect(DisplayServer.window_get_current_screen())
		var available=Vector2i(maxi(640,usable.size.x-32),maxi(360,usable.size.y-64))
		var restored=Vector2i(mini(window_size.x,available.x),mini(window_size.y,available.y))
		DisplayServer.window_set_size(restored)
		DisplayServer.window_set_position(Vector2i(clampi(window_position.x,usable.position.x,usable.end.x-restored.x),clampi(window_position.y,usable.position.y+30,usable.end.y-restored.y)))
	if persist:
		var cfg=ConfigFile.new();cfg.set_value("display","mode","borderless" if value else "windowed")
		var base=config_path.get_base_dir();var error=DirAccess.make_dir_recursive_absolute(base)
		if error==OK:error=cfg.save(config_path+".tmp")
		if error==OK:error=DirAccess.rename_absolute(config_path+".tmp",config_path)
		save_error="显示模式已切换，但本地设置未保存（%d）"%error if error!=OK else ""
	busy=false;changed.emit()
func caption() -> String:return "窗口 F11" if is_fullscreen() else "全屏 F11"
