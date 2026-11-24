extends Node
var checks=[]
var app
var output=""
var root: Window
func key(echo_event=false):
	var e=InputEventKey.new();e.keycode=KEY_F11;e.pressed=true;e.echo=echo_event;root.push_input(e,true)
	if not echo_event:
		e=InputEventKey.new();e.keycode=KEY_F11;e.pressed=false;root.push_input(e,true)
	await get_tree().create_timer(.4).timeout
func click(button):
	await get_tree().process_frame;await RenderingServer.frame_post_draw
	var pos=button.get_global_rect().get_center()
	for down in [true,false]:
		var e=InputEventMouseButton.new();e.button_index=MOUSE_BUTTON_LEFT;e.pressed=down;e.position=pos;root.push_input(e,true)
	await get_tree().create_timer(.4).timeout
func save_image(name):
	await get_tree().process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png(output+"_"+name+".png")
func run(application):
	root=get_tree().root;app=application
	var args=OS.get_cmdline_user_args();output=args[args.find("--output")+1];var phase=args[args.find("--display-smoke")+1]
	await get_tree().create_timer(.45).timeout
	var display=root.get_node("DisplayPreferences")
	if app.store.state.is_empty():app.commands_ui.new.pressed.emit();app.dismiss_story()
	var before=JSON.stringify(app.store.state,"",true)
	if phase=="first":
		checks.append(not display.is_fullscreen());var initial=DisplayServer.window_get_size()
		await key();checks.append(DisplayServer.window_get_mode()==DisplayServer.WINDOW_MODE_FULLSCREEN and DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_BORDERLESS))
		var full_size=DisplayServer.window_get_size();var native=DisplayServer.screen_get_size(DisplayServer.window_get_current_screen())
		checks.append(absi(full_size.x-native.x)<=2 and absi(full_size.y-native.y)<=2)
		await key(true);checks.append(display.is_fullscreen())
		await save_image("fullscreen_town")
		app.open_town("barracks");await get_tree().create_timer(.3).timeout
		checks.append(app.context_ui.panel.get_global_rect().end.x<=root.size.x and app.context_ui.panel.get_global_rect().end.y<=root.size.y)
		await save_image("fullscreen_management");app.open_town("overview")
		await key();checks.append(not display.is_fullscreen() and not DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_BORDERLESS) and DisplayServer.window_get_size()==initial)
		var buttons=app.context_ui.header_panel.find_children("*","Button",true,false)
		var toggle=buttons.filter(func(b):return b.text.contains("F11"))[0];await click(toggle)
		checks.append(display.is_fullscreen() and display.save_error.is_empty())
		var config=ConfigFile.new();checks.append(config.load(display.config_path)==OK and config.get_value("display","mode")=="borderless")
	elif phase=="resume":
		checks.append(display.is_fullscreen());await key();checks.append(not display.is_fullscreen() and not DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_BORDERLESS));await save_image("restored_window")
		var config=ConfigFile.new();checks.append(config.load(display.config_path)==OK and config.get_value("display","mode")=="windowed")
	elif phase=="window":checks.append(not display.is_fullscreen())
	elif phase=="battle":
		app.open_town("deploy");app.recommend_first();app.commands_ui.depart.pressed.emit();app.commands_ui.map_enter.pressed.emit();app.paused=true;app.show_battle()
		before=JSON.stringify(app.store.state,"",true);await key();checks.append(display.is_fullscreen() and app.paused)
		checks.append(app.context_ui.footer_panel.get_global_rect().end.x<=root.size.x and app.context_ui.footer_panel.get_global_rect().end.y<=root.size.y)
		await save_image("fullscreen_battle");await key();checks.append(not display.is_fullscreen() and app.paused)
	elif phase=="write_fail":
		display.config_path=output+"/blocked/display.cfg";var file=FileAccess.open(output,FileAccess.WRITE);file.store_string("not a directory");file.close()
		await key();checks.append(display.is_fullscreen() and not display.save_error.is_empty() and app.context_ui.toast.visible)
	checks.append(before==JSON.stringify(app.store.state,"",true))
	var result={"passed":not false in checks,"checks":checks,"phase":phase,"window_mode":DisplayServer.window_get_mode(),"window_size":str(DisplayServer.window_get_size()),"scope":"actual native window modes, synthetic F11/header click, same campaign state; not a manual Alt+Tab or multi-monitor test"}
	var file=FileAccess.open(output+".json",FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close();print(JSON.stringify(result));get_tree().quit(0 if result.passed else 1)
