extends Node3D
## Standalone presentation scene. Does not instantiate campaign rules/store or open saves.
const BOARD=preload("res://board.gd")
const ART=preload("res://core/forest_art.gd")
const THEME=preload("res://core/interface_theme.gd")
var board
var bench=Node3D.new()
var model
var player: AnimationPlayer
var sun: DirectionalLight3D
var environment: Environment
var status: Label
var scene_mode="forest"
var light_mode=0
var animation="Idle"
var paused=false
var mesh_material_changes=0
var units=[]

func _ready():
	board=BOARD.new();add_child(board);board.camera.look_at(Vector3(0,.3,0))
	for child in board.get_children():
		if child is DirectionalLight3D:sun=child
		if child is WorldEnvironment:environment=child.environment
	for i in range(8):
		units.append({"instance_id":i+1,"unit_type":["shield","cavalry","archer","lorne"][i%4],"side":"player" if i<4 else "enemy","position":[2+(i%4)*2,1 if i<4 else 6],"hp":32,"alive":true})
	board.show_units(units,[],0);board.set_grid_mode("battle");board.set_paused(false,1)
	add_child(bench);build_bench();bench.hide()
	var layer=CanvasLayer.new();add_child(layer)
	var panel=PanelContainer.new();panel.theme=THEME.create();panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE);panel.offset_left=20;panel.offset_right=-20;panel.offset_top=16;layer.add_child(panel)
	var stack=VBoxContainer.new();panel.add_child(stack)
	var title=Label.new();title.text="AD-01 · 林道 / 材质基准　（独立查看，不读取游戏进度）";title.add_theme_font_size_override("font_size",22);stack.add_child(title)
	var row=HBoxContainer.new();stack.add_child(row)
	button(row,"林道场景",func():set_mode("forest"));button(row,"盾兵 / 四材质",func():set_mode("materials"))
	button(row,"光照：中性 / 林道 / 暗部",func():set_lighting((light_mode+1)%3))
	var picker=OptionButton.new()
	for label_value in ["待机","行走","近战","举盾","倒地"]:picker.add_item(label_value)
	picker.tooltip_text="材质台盾兵动作；选择后切到近景检查"
	picker.item_selected.connect(func(index):set_mode("materials");set_animation(["Idle","Armature|walking_man|baselayer","Right_Hand_Sword_Slash","ShieldWall","dying_backwards"][index]));row.add_child(picker)
	button(row,"暂停 / 播放",func():paused=not paused;player.speed_scale=0 if paused else 1;board.set_paused(paused,1))
	button(row,"退出",func():get_tree().quit())
	status=Label.new();stack.add_child(status)
	set_lighting(1);set_mode("forest");set_animation("Idle")
	var args=OS.get_cmdline_user_args()
	if args.has("--capture-art") and args.find("--capture-art")+1<args.size():call_deferred("capture_requested",args[args.find("--capture-art")+1])

func button(parent: Node,text: String,callback: Callable):
	var b=Button.new();b.text=text;b.pressed.connect(callback);parent.add_child(b)

func shape(mesh: Mesh,p: Vector3,material: Material) -> MeshInstance3D:
	var n=MeshInstance3D.new();n.mesh=mesh;n.position=p;n.material_override=material;bench.add_child(n);return n

func build_bench():
	var floor_mesh=PlaneMesh.new();floor_mesh.size=Vector2(35,35);shape(floor_mesh,Vector3(0,-.05,0),ART.mat("8b8b7c"))
	var names=["木 · 顺纹 / 旧边","石 · 宽切面","布 · 低光 / 宽褶","铁 · 受控反光"]
	for i in range(4):
		var x=-2.7+i*1.8
		var base=BoxMesh.new();base.size=Vector3(1.45,.18,1.25);shape(base,Vector3(x,.04,.95),ART.mat("5a655d"))
		var label=board.label(bench,names[i],Color("eee7d6"),.4);label.position=Vector3(x,.27,1.72);label.font_size=30;label.pixel_size=.0045
		if i==0:
			var box=BoxMesh.new();box.size=Vector3(.75,.65,.62);var n=shape(box,Vector3(x,.46,.95),ART.family("wood"));n.rotation.y=.2
		elif i==1:
			var n=ART.rock(bench,Vector3(x,.16,.95),2);n.scale*=1.1;n.material_override=ART.family("stone")
		elif i==2:
			var tool=SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES)
			for column in range(12):
				var a=-.48+float(column)*.08;var b=a+.08
				var za=.95+sin(a*15)*.06;var zb=.95+sin(b*15)*.06
				for tri in [[Vector3(a,.92,za),Vector3(a,.22,za+.08),Vector3(b,.92,zb)],[Vector3(b,.92,zb),Vector3(a,.22,za+.08),Vector3(b,.22,zb+.08)]]:
					var normal=(tri[1]-tri[0]).cross(tri[2]-tri[0]).normalized()
					for point in tri:tool.set_normal(normal);tool.add_vertex(point+Vector3(x,0,0))
			var cloth=ART.family("cloth").duplicate();cloth.cull_mode=BaseMaterial3D.CULL_DISABLED;shape(tool.commit(),Vector3.ZERO,cloth)
			ART.rod(bench,Vector3(x-.55,.97,.95),Vector3(x+.55,.97,.95),.035)
		else:
			var sphere=SphereMesh.new();sphere.radius=.34;sphere.height=.68;sphere.radial_segments=24;sphere.rings=12;shape(sphere,Vector3(x,.48,.95),ART.family("iron"))
	model=load("res://assets/shield.glb").instantiate();bench.add_child(model)
	mesh_material_changes=ART.prepare_character(model)
	var bounds=load("res://core/asset_bounds.gd").measure(model).bounds
	var factor=2.5/bounds.size.y;model.scale*=factor;model.position=Vector3(-bounds.get_center().x,-bounds.position.y,-bounds.get_center().z)*factor+Vector3(0,0,-1.1);model.rotation.y=-.25
	player=model.find_children("*","AnimationPlayer",true,false)[0]

func set_mode(value: String):
	scene_mode=value;bench.visible=value=="materials";board.ground.visible=value=="forest";board.surface.visible=value=="forest"
	board.set_process_unhandled_input(value=="forest")
	board.set_grid_mode("battle" if value=="forest" else "off")
	for f in board.figures.values():f.node.visible=value=="forest"
	board.camera.size=11.6 if value=="forest" else 7.1
	board.camera.position=Vector3(11,14,17) if value=="forest" else Vector3(4.4,5.0,8.5)
	board.camera.look_at(Vector3(0,.3,0) if value=="forest" else Vector3(0,.8,0))
	update_status()

func _unhandled_input(event):
	if scene_mode!="materials" or not event is InputEventMouseButton or not event.pressed:return
	if event.button_index==MOUSE_BUTTON_WHEEL_UP:board.camera.size=maxf(4.0,board.camera.size-.4)
	elif event.button_index==MOUSE_BUTTON_WHEEL_DOWN:board.camera.size=minf(10.0,board.camera.size+.4)

func set_lighting(index: int):
	light_mode=index
	sun.light_color=Color("ffffff") if index==0 else Color("fff5e7")
	sun.light_energy=[.95,.9,.48][index]
	environment.ambient_light_color=Color("d0d2d0") if index==0 else Color("c5d2d6")
	environment.ambient_light_energy=[.50,.55,.32][index]
	update_status()

func set_animation(clip: String):
	animation=clip
	if player.has_animation(clip):player.play(clip,.12);player.speed_scale=0 if paused else 1
	update_status()

func update_status():
	if status==null:return
	status.text="%s · %s光 · 滚轮缩放 · 盾兵身体/骨架保留；本批仅检查材质、尺度与构图"%["林道8单位" if scene_mode=="forest" else "盾兵与四材质",["中性","林道","暗部"][light_mode]]

func capture_requested(output: String):
	DirAccess.make_dir_recursive_absolute(output)
	var captures=[]
	for mode in ["forest","materials"]:
		set_mode(mode)
		for light in ([1] if mode=="forest" else [0,1,2]):
			set_lighting(light)
			for i in range(12):await get_tree().process_frame
			await RenderingServer.frame_post_draw
			var name_value=mode+"_"+str(light)
			get_viewport().get_texture().get_image().save_png(output.path_join(name_value+".png"));captures.append(name_value)
	set_lighting(1)
	for clip in ["Idle","Armature|walking_man|baselayer","Right_Hand_Sword_Slash","ShieldWall","dying_backwards"]:
		set_animation(clip)
		player.seek(player.get_animation(clip).length*.55,true);player.pause()
		for i in range(4):await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var name_value="pose_"+str(captures.size())
		get_viewport().get_texture().get_image().save_png(output.path_join(name_value+".png"));captures.append(name_value)
	var report={"passed":mesh_material_changes>0,"material_overrides":mesh_material_changes,"captures":captures,"resolution":[get_viewport().size.x,get_viewport().size.y],"scope":"standalone renderer fixture, three lights and five existing poses; no campaign stores opened and no art-quality approval"}
	var f=FileAccess.open(output.path_join("capture.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "));f.close();print(JSON.stringify(report));get_tree().quit(0 if report.passed else 1)
