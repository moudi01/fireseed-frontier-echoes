extends Node3D
## Material-only comparison, driven by the production skill workbench. No campaign/store.
const DEMO=preload("res://core/skill_demo.gd")
const SURFACE=preload("res://core/character_surface.gd")
const BOUNDS=preload("res://core/asset_bounds.gd")
const THEME=preload("res://core/interface_theme.gd")
const ROLES=["lorne","cavalry","archer"]
const ROLE_NAMES=["洛恩 · 剑盾","突击兵 · 单手剑","弓兵 · 弓"]
const PHASES=[0,1,3,4,5]
const PHASE_NAMES=["待机","技能起手","技能出招","行走","收势"]
const DURATIONS=[.65,.50,.42,.55,.60]
const SAMPLE_AT=[.40,.35,.14,.27,.40]
const LIGHT_NAMES=["中性棚光","林道暖光","暗部检视","关闭后处理"]
const ENVIRONMENT_PROPERTIES=["background_mode","background_color","background_energy_multiplier","ambient_light_source","ambient_light_color","ambient_light_energy","ambient_light_sky_contribution","reflected_light_source","tonemap_mode","tonemap_exposure","tonemap_white","glow_enabled","glow_intensity","glow_strength","glow_bloom","fog_enabled","fog_density","fog_light_color","fog_light_energy","fog_sky_affect","volumetric_fog_enabled","volumetric_fog_density","adjustment_enabled","adjustment_brightness","adjustment_contrast","adjustment_saturation","ssr_enabled","ssao_enabled","ssil_enabled","sdfgi_enabled"]
const POSTPROCESS_SWITCHES=["glow_enabled","fog_enabled","volumetric_fog_enabled","adjustment_enabled","ssr_enabled","ssao_enabled","ssil_enabled","sdfgi_enabled"]
var workbench
var board
var world:WorldEnvironment
var key_light:DirectionalLight3D
var role_index=0
var phase=0
var elapsed=0.0
var paused=false
var enabled=true
var side_view=false
var rotating=false
var orbit=0.0
var light_mode=0
var output=""
var samples=[]
var pending=false
var status:Label
var role_button:Button
var material_button:Button
var light_button:Button
var pause_button:Button
var rotation_button:Button
var action_mode=0
var original_environment={}
var original_key={}
var board_lighting_baseline={}

func _ready():
	var args=OS.get_cmdline_user_args()
	var role_arg=argument(args,"--surface-role","lorne")
	role_index=maxi(0,ROLES.find(role_arg))
	enabled=not args.has("--surface-baseline")
	side_view=args.has("--side")
	light_mode=clampi(int(argument(args,"--surface-light","0")),0,LIGHT_NAMES.size()-1)
	output=argument(args,"--capture-surfaces","")
	if not output.is_empty():DirAccess.make_dir_recursive_absolute(output)
	workbench=DEMO.new();add_child(workbench)
	workbench.set_process(false);workbench.set_process_input(false)
	for child in workbench.get_children():
		if child is CanvasLayer:child.hide()
	board=workbench.board
	board.set_shield_visuals(false)
	board.camera.size=3.15
	# Viewer-only floor: the production board's finite edge must not cut a close-up.
	var viewer_floor=PlaneMesh.new();viewer_floor.size=Vector2(120,120);board.surface.mesh=viewer_floor
	for child in board.get_children():
		if child is WorldEnvironment:world=child
		if child is DirectionalLight3D:key_light=child
	remember_board_lighting()
	make_interface()
	apply_light();show_phase()

func argument(args:PackedStringArray,flag:String,fallback:String) -> String:
	var index=args.find(flag)
	return args[index+1] if index>=0 and index+1<args.size() else fallback

func button(row:HBoxContainer,text:String,callback:Callable) -> Button:
	var control=Button.new();control.text=text;row.add_child(control);control.pressed.connect(callback);return control

func make_interface():
	var layer=CanvasLayer.new();add_child(layer)
	var panel=PanelContainer.new();panel.theme=THEME.create();panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	panel.offset_left=20;panel.offset_right=-20;panel.offset_top=14;layer.add_child(panel)
	var stack=VBoxContainer.new();panel.add_child(stack)
	var title=Label.new();title.text="AD-03 · 角色身体材质对照";title.add_theme_font_size_override("font_size",20);stack.add_child(title)
	var row=HBoxContainer.new();stack.add_child(row)
	role_button=button(row,"角色",func():role_index=(role_index+1)%ROLES.size();restart())
	material_button=button(row,"材质",func():enabled=not enabled;apply_materials();refresh_status())
	button(row,"正面 / 侧面",func():side_view=not side_view;orbit=0;update_camera())
	rotation_button=button(row,"旋转：关",func():rotating=not rotating;refresh_status())
	light_button=button(row,"光照",func():light_mode=(light_mode+1)%LIGHT_NAMES.size();apply_light();refresh_status())
	var action_picker=OptionButton.new();row.add_child(action_picker)
	for name_value in ["动作：循环","动作：待机","动作：技能","动作：行走"]:action_picker.add_item(name_value)
	action_picker.item_selected.connect(func(index):action_mode=index;phase=[0,0,1,3][index];elapsed=0;show_phase())
	pause_button=button(row,"暂停",func():paused=not paused;board.set_paused(paused,1);refresh_status())
	button(row,"重播",func():restart())
	button(row,"退出",func():get_tree().quit())
	status=Label.new();stack.add_child(status)
	var info=Label.new();info.text="原生模型与技能动作 · 护壁特效暂隐以比较身体表面 · F11全屏 / 滚轮缩放";stack.add_child(info)

func restart():
	phase=[0,0,1,3][action_mode];elapsed=0;paused=false;samples=[];board.camera.size=3.15;show_phase()

func show_phase():
	workbench.focus_id=role_index+1
	workbench.side_view=side_view
	workbench.phase=PHASES[phase]
	workbench.paused=false
	workbench.elapsed=0
	workbench.show_phase()
	board.set_paused(paused,1)
	# Reset may replace instances; switch only their materials, never template resources.
	apply_materials()
	for figure in board.figures.values():figure.ring.visible=false
	update_camera();refresh_status()

func apply_materials():
	for figure in board.figures.values():SURFACE.set_enabled(figure.model,enabled)

func apply_light():
	if world==null or key_light==null:return
	var environment=world.environment
	# Always restore real production settings before applying an inspection override.
	for property in original_environment:environment.set(property,original_environment[property])
	for property in original_key:key_light.set(property,original_key[property])
	board.ground.visible=light_mode in [1,3]
	board.surface.visible=true
	if light_mode in [1,3]:
		board.surface.material_override=preload("res://core/forest_art.gd").earth()
		if light_mode==3:
			for property in POSTPROCESS_SWITCHES:
				if original_environment.has(property):environment.set(property,false)
			if original_environment.has("tonemap_mode"):environment.set("tonemap_mode",Environment.TONE_MAPPER_LINEAR)
			if original_environment.has("tonemap_exposure"):environment.set("tonemap_exposure",1.0)
	else:
		var ground_material=StandardMaterial3D.new();ground_material.albedo_color=Color("777d79") if light_mode==0 else Color("363d3d");ground_material.roughness=.95
		board.surface.material_override=ground_material
		environment.background_color=Color("777d79") if light_mode==0 else Color("363d3d")
		environment.ambient_light_color=Color("d8dedb") if light_mode==0 else Color("a8bdc7")
		environment.ambient_light_energy=.65 if light_mode==0 else .30
		key_light.light_color=Color("fff9ee") if light_mode==0 else Color("b7cada")
		key_light.light_energy=.85 if light_mode==0 else .40
		key_light.rotation_degrees=Vector3(-42,-28,0) if light_mode==0 else Vector3(-35,48,0)

func supported_properties(object:Object) -> Dictionary:
	var names={}
	for property in object.get_property_list():names[str(property.name)]=true
	return names

func remember_board_lighting():
	if world==null or key_light==null:return
	var properties=supported_properties(world.environment)
	for property in ENVIRONMENT_PROPERTIES:
		if properties.has(property):original_environment[property]=world.environment.get(property)
	for property in ["light_color","light_energy","rotation_degrees","shadow_enabled"]:original_key[property]=key_light.get(property)
	board_lighting_baseline=lighting_report()

func json_value(value):
	if value is Color:return [value.r,value.g,value.b,value.a]
	if value is Vector3:return [value.x,value.y,value.z]
	return value

func lighting_report() -> Dictionary:
	if world==null or key_light==null:return {"valid":false}
	var properties=supported_properties(world.environment)
	var values={};var unavailable=[]
	for property in ENVIRONMENT_PROPERTIES:
		if properties.has(property):values[property]=json_value(world.environment.get(property))
		else:unavailable.append(property)
	var key={}
	for property in ["light_color","light_energy","rotation_degrees","shadow_enabled"]:key[property]=json_value(key_light.get(property))
	var sky_values={}
	if world.environment.sky!=null:
		sky_values["class"]=world.environment.sky.get_class()
		var material=world.environment.sky.sky_material
		if material!=null:
			sky_values["material_class"]=material.get_class()
			var material_properties=supported_properties(material)
			for property in ["sky_top_color","sky_horizon_color","ground_bottom_color","ground_horizon_color"]:
				if material_properties.has(property):sky_values[property]=json_value(material.get(property))
	return {"valid":true,"environment":values,"key_light":key,"sky":sky_values,"unavailable_properties":unavailable,"rendering_method":ProjectSettings.get_setting("rendering/renderer/rendering_method",""),"note":"Actual queried configuration; backend support and visual effect require rendered verification. Disabled defaults are recorded without implying that a post effect was previously active."}

func update_camera(reset_zoom=false):
	if not board.figures.has(role_index+1):return
	var figure=board.figures[role_index+1]
	var center=figure.node.position+Vector3(0,.94,0)
	var angle=(PI*.5 if side_view else .12)+orbit
	board.camera.position=center+Vector3(sin(angle)*3.2,.24,cos(angle)*3.2)
	board.camera.look_at(center)
	if reset_zoom:board.camera.size=3.15

func refresh_status():
	role_button.text=ROLE_NAMES[role_index]
	material_button.text="材质：040 新版" if enabled else "材质：039 基线"
	light_button.text=LIGHT_NAMES[light_mode]
	pause_button.text="继续" if paused else "暂停"
	rotation_button.text="旋转：开" if rotating else "旋转：关"
	status.text="%s · %s · %s · 可切换材质比较；所有动作来自同一制作模型"%[ROLE_NAMES[role_index],PHASE_NAMES[phase],LIGHT_NAMES[light_mode]]

func capture():
	pending=true
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var figure=board.figures[role_index+1]
	var measured=BOUNDS.measure(figure.model,Transform3D.IDENTITY,true)
	var world_bounds: AABB=BOUNDS.measure(figure.node,board.global_transform,true).bounds
	var top=INF;var bottom=-INF;var left=INF;var right=-INF
	for index in range(8):
		var point=board.camera.unproject_position(world_bounds.get_endpoint(index))
		top=minf(top,point.y);bottom=maxf(bottom,point.y);left=minf(left,point.x);right=maxf(right,point.x)
	var size_value=get_viewport().get_visible_rect().size
	var image_path=output.path_join("phase_%d.png"%phase)
	var image_error=get_viewport().get_texture().get_image().save_png(image_path)
	var surface_report=figure.model.get_meta("character_surface_report",{})
	samples.append({"phase":phase,"name":PHASE_NAMES[phase],"role":ROLES[role_index],"clip":figure.clip,"animation_time":figure.player.current_animation_position,"floor":measured.bounds.position.y,"height":measured.bounds.size.y,"enabled":enabled,"light":light_mode,"screen_bounds":{"top":top,"bottom":bottom,"left":left,"right":right,"logical_size":[size_value.x,size_value.y]},"issues":figure.model.get_meta("action_issues",["unchecked"]),"surface_report":surface_report,"png":image_path,"image_saved":image_error==OK})
	pending=false

func finish_capture():
	var ok=samples.size()==PHASES.size() and samples.all(func(sample):return sample.image_saved and sample.issues.is_empty() and sample.surface_report.get("valid",false) and sample.surface_report.get("enabled",not enabled)==enabled and absf(sample.floor)<.06 and sample.height<2.8 and sample.screen_bounds.top>=160 and sample.screen_bounds.bottom<=sample.screen_bounds.logical_size[1]-8 and sample.screen_bounds.left>=8 and sample.screen_bounds.right<=sample.screen_bounds.logical_size[0]-8)
	var result={"passed":ok,"role":ROLES[role_index],"enabled":enabled,"side_view":side_view,"light":light_mode,"light_name":LIGHT_NAMES[light_mode],"lighting":lighting_report(),"board_lighting_baseline":board_lighting_baseline,"postprocess_switches_forced_off":POSTPROCESS_SWITCHES.filter(func(property):return original_environment.has(property)) if light_mode==3 else [],"samples":samples,"scope":"material comparison using the production skill workbench, models and contact/pose modifiers; shield VFX hidden; no campaign access or combat authority"}
	var file=FileAccess.open(output.path_join("surfaces.json"),FileAccess.WRITE)
	if file==null:push_error("Cannot write surfaces.json");get_tree().quit(1);return
	file.store_string(JSON.stringify(result,"  "));file.close()
	print(JSON.stringify({"passed":ok,"role":ROLES[role_index],"samples":samples.size()}));get_tree().quit(0 if ok else 1)

func _process(delta):
	if board==null or pending:return
	if rotating and not paused:orbit+=delta*.40
	update_camera()
	if paused:return
	elapsed+=delta
	if not output.is_empty() and elapsed>=SAMPLE_AT[phase] and not samples.any(func(sample):return sample.phase==phase):
		await capture();return
	if elapsed<(DURATIONS[phase] if not output.is_empty() else 1.8):return
	if phase==PHASES.size()-1 and not output.is_empty():finish_capture();return
	if output.is_empty():
		if action_mode==1:return
		if action_mode==2:
			phase=2 if phase==1 else (4 if phase==2 else 1);elapsed=0;show_phase();return
		if action_mode==3:elapsed=0;show_phase();return
	phase=(phase+1)%PHASES.size();elapsed=0;show_phase()

func _input(event):
	if board==null:return
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
		board.camera.size=clampf(board.camera.size+(-.20 if event.button_index==MOUSE_BUTTON_WHEEL_UP else .20),2.25,5.0);get_viewport().set_input_as_handled()
