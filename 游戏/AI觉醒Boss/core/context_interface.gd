extends Control
## Context windows are presentation only. The host owns all commands and pause state.
signal dismissed
signal quit_requested
signal exit_confirmed
signal exit_cancelled
const UI_THEME=preload("res://core/interface_theme.gd")
var header_panel: PanelContainer
var fade: Tween
var panel: PanelContainer
var stack: VBoxContainer
var headline: Label
var notice: Label
var inspection: Label
var caption: Label
var close_button: Button
var shade: ColorRect
var footer: HFlowContainer
var footer_stack: VBoxContainer
var footer_panel: PanelContainer
var status: Label
var toast: PanelContainer
var mode=""
var can_close=false
var note_seen=""
var note_time=0.0
var footer_buttons={}
var quit_button: Button
var exit_overlay: ColorRect
var exit_panel: PanelContainer
var exit_message: Label
var exit_cancel: Button
var exit_confirm: Button
var exit_focus: Control
func _ready():
	theme=preload("res://core/interface_theme.gd").create();mouse_filter=Control.MOUSE_FILTER_IGNORE
	var top=PanelContainer.new();top.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT);top.offset_left=14;top.offset_right=-14;top.offset_top=10;top.offset_bottom=56;add_child(top)
	top.add_theme_stylebox_override("panel",preload("res://core/interface_theme.gd").box("eddfbf","9e8058",10))
	header_panel=top
	var top_row=HBoxContainer.new();top.add_child(top_row);headline=Label.new();headline.text="AI觉醒Boss";headline.clip_text=true;headline.add_theme_font_size_override("font_size",17);headline.size_flags_horizontal=Control.SIZE_EXPAND_FILL;top_row.add_child(headline)
	var display=get_node_or_null("/root/DisplayPreferences")
	if display:
		var mode_button=Button.new();mode_button.text=display.caption();mode_button.tooltip_text="无边框全屏 / 窗口 · F11";top_row.add_child(mode_button)
		mode_button.pressed.connect(display.toggle)
		display.changed.connect(func():
			mode_button.text=display.caption()
			if not display.save_error.is_empty():notify(display.save_error))
	quit_button=Button.new();quit_button.text="退出游戏";UI_THEME.action_style(quit_button,"danger");top_row.add_child(quit_button);quit_button.pressed.connect(request_quit)
	var bottom=PanelContainer.new();bottom.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE);bottom.offset_left=14;bottom.offset_right=-14;bottom.offset_top=-70;bottom.offset_bottom=-12;add_child(bottom)
	footer_panel=bottom;bottom.add_theme_stylebox_override("panel",preload("res://core/interface_theme.gd").box("eddfbf","9e8058",10))
	footer_stack=VBoxContainer.new();footer_stack.add_theme_constant_override("separation",UI_THEME.ACTION_GAP);bottom.add_child(footer_stack)
	status=Label.new();status.add_theme_font_size_override("font_size",16);status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;status.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;footer_stack.add_child(status)
	footer=HFlowContainer.new();footer.alignment=FlowContainer.ALIGNMENT_CENTER;footer.add_theme_constant_override("h_separation",UI_THEME.ACTION_GAP);footer.add_theme_constant_override("v_separation",UI_THEME.ACTION_GAP);footer_stack.add_child(footer)
	footer_stack.minimum_size_changed.connect(func():call_deferred("layout"))
	shade=ColorRect.new();shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);shade.color=Color(0.07,0.06,0.04,.32);add_child(shade)
	panel=PanelContainer.new();add_child(panel);panel.add_theme_stylebox_override("panel",preload("res://core/interface_theme.gd").box("eddfbf","9e8058",20))
	var body=VBoxContainer.new();panel.add_child(body)
	var heading=HBoxContainer.new();body.add_child(heading);caption=Label.new();caption.size_flags_horizontal=Control.SIZE_EXPAND_FILL;caption.add_theme_font_size_override("font_size",16);heading.add_child(caption)
	close_button=Button.new();close_button.text="收起 ×";close_button.flat=true;heading.add_child(close_button);close_button.pressed.connect(func():if can_close:dismissed.emit())
	stack=VBoxContainer.new();stack.size_flags_vertical=Control.SIZE_EXPAND_FILL;body.add_child(stack)
	toast=PanelContainer.new();add_child(toast);notice=Label.new();notice.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;notice.add_theme_font_size_override("font_size",17);toast.add_child(notice);toast.mouse_filter=Control.MOUSE_FILTER_IGNORE;notice.mouse_filter=Control.MOUSE_FILTER_IGNORE
	toast.add_theme_stylebox_override("panel",preload("res://core/interface_theme.gd").box("fff0ca","ae793e",14))
	inspection=Label.new();inspection.hide();add_child(inspection)
	build_exit_warning()
	resized.connect(layout);present("new",false)
func build_exit_warning():
	exit_overlay=ColorRect.new();exit_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);exit_overlay.color=Color(0.07,0.06,0.04,.65);add_child(exit_overlay);exit_overlay.hide()
	exit_panel=PanelContainer.new();exit_overlay.add_child(exit_panel);exit_panel.add_theme_stylebox_override("panel",UI_THEME.box("eddfbf","9e8058",20))
	exit_panel.minimum_size_changed.connect(func():call_deferred("layout"))
	var body=VBoxContainer.new();exit_panel.add_child(body)
	var title=Label.new();title.text="退出游戏前";title.add_theme_font_size_override("font_size",22);body.add_child(title)
	exit_message=Label.new();exit_message.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;body.add_child(exit_message)
	var buttons=HBoxContainer.new();buttons.add_theme_constant_override("separation",UI_THEME.ACTION_GAP);body.add_child(buttons)
	exit_cancel=Button.new();exit_cancel.text="继续游戏";UI_THEME.action_style(exit_cancel,"primary");exit_cancel.size_flags_horizontal=Control.SIZE_EXPAND_FILL;buttons.add_child(exit_cancel);exit_cancel.pressed.connect(cancel_exit)
	exit_confirm=Button.new();exit_confirm.text="仍然退出";UI_THEME.action_style(exit_confirm,"danger");exit_confirm.size_flags_horizontal=Control.SIZE_EXPAND_FILL;buttons.add_child(exit_confirm);exit_confirm.pressed.connect(func():exit_confirmed.emit())
	exit_cancel.focus_neighbor_left=exit_confirm.get_path();exit_cancel.focus_neighbor_right=exit_confirm.get_path();exit_confirm.focus_neighbor_left=exit_cancel.get_path();exit_confirm.focus_neighbor_right=exit_cancel.get_path()
	for b in [exit_cancel,exit_confirm]:
		b.focus_neighbor_top=b.get_path();b.focus_neighbor_bottom=b.get_path();b.focus_next=(exit_confirm if b==exit_cancel else exit_cancel).get_path();b.focus_previous=b.focus_next
func request_quit():
	# Standalone anomaly uses this shared shell without a campaign host/report.
	if quit_requested.get_connections().is_empty():get_tree().quit()
	else:quit_requested.emit()
func show_exit_warning(text: String):
	if exit_overlay.visible:return
	exit_focus=get_viewport().gui_get_focus_owner();exit_message.text=text;exit_overlay.show();layout();exit_cancel.grab_focus()
func cancel_exit():
	if not exit_overlay.visible:return
	exit_overlay.hide()
	if is_instance_valid(exit_focus) and exit_focus.is_visible_in_tree():exit_focus.grab_focus()
	exit_cancelled.emit()
func set_exit_hint(text: String):quit_button.tooltip_text=text
func present(value: String,closable: bool=true):
	var animate=not panel.visible or mode!=value
	mode=value;can_close=closable;panel.visible=value not in ["world","map","battle","town"]
	shade.visible=panel.visible and value!="formation";close_button.visible=closable;caption.text={"story":"同行 · 剧情","event":"途中事件","management":"据点管理","formation":"出征整备","transport":"返回运输","report":"归城战报 · 已确认入账","history":"同行记事","details":"战况详情","new":"开始旅程","demo":"独立异常片段","error":"进度提示"}.get(value,"")
	footer_panel.visible=not panel.visible and (footer.get_child_count()>0 or not status.text.is_empty())
	layout()
	if panel.visible and animate:
		if fade:fade.kill()
		panel.modulate.a=0;fade=create_tween();fade.tween_property(panel,"modulate:a",1.0,.16)
func layout():
	if panel==null:return
	header_panel.position=Vector2(20,16);header_panel.size=Vector2(minf(660,size.x-40),46)
	# A wrapped status line must not compete horizontally with the action row.
	var footer_width=minf(size.x-40,1000);status.visible=not status.text.is_empty()
	footer_panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT);footer_panel.size=Vector2(footer_width,0)
	var footer_height=maxf(60,footer_panel.get_combined_minimum_size().y)
	footer_panel.size.y=footer_height;footer_panel.position=Vector2((size.x-footer_width)*.5,size.y-footer_height-16)
	var width=minf(860,size.x-44);var height=minf(560,size.y-130)
	if mode=="story":height=minf(390,size.y-150)
	if mode=="formation":width=minf(560,size.x-44);height=minf(680,size.y-32)
	caption.add_theme_font_override("font",preload("res://core/interface_theme.gd").title_font());caption.add_theme_color_override("font_color",Color("b5bda5"))
	panel.size=Vector2(width,height)
	panel.position=Vector2((size.x-width)*.5,size.y-height-86 if mode=="story" else (size.y-height)*.5)
	if mode=="formation":panel.position.x=size.x-width-20
	toast.size=Vector2(minf(680,size.x-60),0);toast.position=Vector2((size.x-toast.size.x)*.5,70)
	if is_instance_valid(exit_panel):
		exit_panel.size=Vector2(minf(600,size.x-40),0);exit_panel.position=Vector2((size.x-exit_panel.size.x)*.5,(size.y-exit_panel.size.y)*.5)
func clear_footer(text=""):
	for child in footer.get_children():
		footer.remove_child(child);child.queue_free()
	footer_buttons={};status.text=text
	footer_panel.visible=not panel.visible and not text.is_empty()
func action(text: String,callback: Callable,key: String):
	var button=Button.new();button.text=text;UI_THEME.action_style(button,"primary" if key in ["map_enter","reopen","town_deploy"] else "secondary");footer.add_child(button);button.pressed.connect(callback);footer_buttons[key]=button
	footer_panel.visible=not panel.visible;call_deferred("layout");return button
func notify(text: String):
	notice.text=text;note_seen=text;note_time=7.0 if not text.is_empty() else 0.0;toast.visible=note_time>0;layout()
func _process(delta):
	if notice.text!=note_seen:notify(notice.text)
	if note_time>0:note_time=maxf(0,note_time-delta);toast.visible=note_time>0
	else:toast.hide()
func _unhandled_key_input(event):
	if exit_overlay.visible and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled();cancel_exit();return
	if event.is_action_pressed("ui_cancel") and panel.visible:
		get_viewport().set_input_as_handled()
		if can_close:dismissed.emit()
