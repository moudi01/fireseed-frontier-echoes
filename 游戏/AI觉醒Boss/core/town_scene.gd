extends Node3D
const ART=preload("res://core/forest_art.gd")
const KIT=preload("res://core/scenery_kit.gd")
const BOUNDS=preload("res://core/asset_bounds.gd")
## Local set dressing only. Facility actions remain in main/campaign commands.
signal selected(place)
var camera: Camera3D
var labels={}
var rng=RandomNumberGenerator.new()
func material(color: String) -> Material:return KIT.mat(color,"wall")
func block(parent: Node3D,p: Vector3,s: Vector3,color: String,rot=Vector3.ZERO) -> MeshInstance3D:return KIT.block(parent,p,s,color,"wood",rot)
func cylinder(parent: Node3D,p: Vector3,r: float,h: float,color: String,top=-1.0) -> MeshInstance3D:return KIT.cylinder(parent,p,r,h,color,"wood",top)
func sign_label(parent: Node3D,title: String,p: Vector3) -> Label3D:
	var n=Label3D.new();n.text=title;n.position=p;n.font_size=48;n.pixel_size=.010;n.billboard=BaseMaterial3D.BILLBOARD_ENABLED;n.modulate=Color("f4ebd6");n.outline_size=6;n.outline_modulate=Color("35483f");n.no_depth_test=true
	var font=SystemFont.new();font.font_names=PackedStringArray(["Microsoft YaHei UI","Microsoft YaHei"]);n.font=font;parent.add_child(n);return n
func _ready():
	rng.seed=29029
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=17.8;camera.position=Vector3(15,17,19);add_child(camera);camera.look_at(Vector3.ZERO)
	var sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-48,-35,0);sun.light_color=Color("fff1db");sun.light_energy=.80;sun.shadow_enabled=true;sun.directional_shadow_max_distance=60;add_child(sun)
	var terrain=block(self,Vector3(0,-.24,0),Vector3(100,.4,100),"778569")
	var ground=ShaderMaterial.new();ground.shader=Shader.new();ground.shader.code="""shader_type spatial;
 varying vec3 world;
 void vertex(){world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
 void fragment(){
 float yard=1.0-smoothstep(6.2,8.1,length(world.xz*vec2(1.0,.88)));
 float mainpath=1.0-smoothstep(.75,1.6,abs(world.x+.22*sin(world.z*.7)));
 float sidepath=(1.0-smoothstep(.65,1.15,abs(world.z+.9)))*(1.0-smoothstep(4.5,6.2,abs(world.x)));
 float grain=sin(world.x*1.9+sin(world.z*2.3))*sin(world.z*3.1)*.017;
 vec3 soil=mix(vec3(.34,.41,.31),vec3(.57,.54,.42),yard);
 ALBEDO=mix(soil,vec3(.67,.61,.47),max(mainpath,sidepath)*yard*.62)+grain;ROUGHNESS=.97;}
 """;terrain.material_override=ground
	# Three purposeful buildings; the expedition station is an open canopy.
	house("barracks","兵营 · 招募",Vector3(-4.3,0,-3),Vector3(4.1,1.8,2.8),"8f7759",true)
	house("rest","营舍 · 休整",Vector3(.1,0,-4.6),Vector3(3.6,1.35,2.0),"778569",false)
	porch();warehouse();expedition_station();training_yard();gate();furnish()
	# Authored perimeter framing. No foreground crowns obscure entrances.
	var trees=[Vector3(-8.2,0,-5),Vector3(-6.6,0,-7.4),Vector3(-2.8,0,-8.6),Vector3(2.8,0,-8.7),Vector3(7.5,0,-6.2),Vector3(9,0,-2.8),Vector3(-9,0,0),Vector3(-8.5,0,4)]
	for i in range(trees.size()):ART.tree(self,trees[i],.95+float(i%3)*.12,i%2)
	for p in [Vector3(-6.5,0,-.1),Vector3(6.6,0,-5),Vector3(-6,0,5),Vector3(6.7,0,4.5)]:ART.shrub(self,p,0)
	for p in [Vector3(-7,0,-6),Vector3(7.4,0,-4),Vector3(-7.2,0,3.2)]:ART.rock(self,p,0)
	for i in range(3):resident(i)
func porch():
	KIT.canopy(self,Vector3(.1,0,-2.85),Vector2(3.55,1.15),"9b9f7e",1.65)
	KIT.bench(self,Vector3(-.75,.06,-2.6),1.35);KIT.bench(self,Vector3(1,.06,-2.65),1.15)
	KIT.barrel(self,Vector3(1.85,0,-3.05),.8)
	KIT.block(self,Vector3(-.6,.52,-2.59),Vector3(.62,.08,.32),"697e73","cloth")
func warehouse():
	var root=Node3D.new();root.position=Vector3(4.45,0,-2.8);add_child(root)
	block(root,Vector3(0,.16,0),Vector3(3.25,.32,3.0),"919080")
	block(root,Vector3(0,1.35,-.28),Vector3(2.9,2.45,2.35),"b9b092")
	# Tall loading bay reads as a recess beneath a projecting shed roof.
	block(root,Vector3(0,1.16,1.0),Vector3(1.9,1.85,.07),"465148")
	for x in [-1.22,1.22]:block(root,Vector3(x,1.28,1.04),Vector3(.21,2.4,.22),"705b41")
	block(root,Vector3(0,2.52,1.05),Vector3(2.8,.18,.22),"705b41")
	block(root,Vector3(0,2.78,-.1),Vector3(3.4,.18,3.25),"747b68",Vector3(-.10,0,0))
	KIT.canopy(root,Vector3(0,.1,1.25),Vector2(3.0,1.3),"a49470",1.9)
	for x in [-.61,0,.61]:KIT.crate(root,Vector3(x,.32,.86),.53)
	KIT.crate(root,Vector3(-.59,.85,.87),.48)
	KIT.barrel(root,Vector3(1.85,0,1.2),.9);KIT.sack(root,Vector3(1.75,0,2),1.1)
	labels.warehouse=sign_label(root,"仓库 · 运输",Vector3(0,3.2,0));clickable(root,"warehouse",Vector3(0,1.2,.35),Vector3(3.25,2.7,3.9))
func expedition_station():
	var root=KIT.canopy(self,Vector3(4.5,0,2.0),Vector2(3.0,1.3),"b79b62",1.95)
	KIT.map_table(root,Vector3(0,0,1.25));KIT.sack(root,Vector3(-1.05,0,.8),1.05,"899781");KIT.sack(root,Vector3(-1.15,0,.25),.8)
	KIT.crate(root,Vector3(1.12,0,-.65),.6);KIT.barrel(root,Vector3(1.15,0,.2),.7)
	KIT.rod(root,Vector3(-1.6,0,-1),Vector3(-1.6,3,-1),.045)
	KIT.block(root,Vector3(-1.28,2.68,-1),Vector3(.6,.45,.025),"596b72","cloth")
	labels.deploy=sign_label(root,"远征桌 · 整备",Vector3(0,2.85,.6));clickable(root,"deploy",Vector3(0,1,.6),Vector3(3.2,2.6,3.2))
func training_yard():
	var root=Node3D.new();root.position=Vector3(-4.1,0,1.35);add_child(root)
	for x in [-1.05,1.05]:
		KIT.rod(root,Vector3(x,0,-.75),Vector3(x,1.45,-.75),.055)
		var target=cylinder(root,Vector3(x,1.25,-.7),.37,.10,"c0b18c");target.rotation.x=PI/2
		var center=cylinder(root,Vector3(x,1.25,-.64),.15,.012,"916d4f");center.rotation.x=PI/2
		KIT.rod(root,Vector3(x-.22,0,-.6),Vector3(x,.8,-.75),.045)
	KIT.bench(root,Vector3(0,0,1.2),2.1)
	labels.training=sign_label(root,"训练场 · 培养",Vector3(0,2.0,0));clickable(root,"training",Vector3(0,.8,0),Vector3(3.5,1.7,3.3))
func gate():
	for side in [-1,1]:
		for z in [-5,-3,-1,1,3,5]:
			block(self,Vector3(side*7,.43,z),Vector3(.14,.86,.16),"7a7053")
		for z in [-4,-2,0,2,4]:block(self,Vector3(side*7,.55,z),Vector3(.08,.08,2.1),"8a7a59")
	for x in [-1.45,1.45]:
		KIT.rod(self,Vector3(x,0,6.4),Vector3(x,1.8,6.4),.09)
		KIT.block(self,Vector3(x,1.47,6.4),Vector3(.36,.46,.04),"596b72","cloth")
func furnish():
	# Weapon rack beside barracks; props cluster at their own destination.
	for x in [-5.6,-3.4]:KIT.rod(self,Vector3(x,0,-1.25),Vector3(x,1.45,-1.25),.055)
	KIT.rod(self,Vector3(-5.6,1.12,-1.25),Vector3(-3.4,1.12,-1.25),.06)
	for i in range(4):
		var x=-5.4+i*.48;KIT.rod(self,Vector3(x,.12,-1.07),Vector3(x,1.78,-1.23),.027)
		KIT.block(self,Vector3(x,1.72,-1.22),Vector3(.13,.36,.035),"7d8c8f","iron",Vector3(0,0,-.18))
	for p in [Vector3(-2.2,0,4.5),Vector3(2.2,0,4.5),Vector3(-1.9,0,-.7)]:
		KIT.rod(self,p,p+Vector3(0,1.7,0),.045)
		var lamp=KIT.block(self,p+Vector3(0,1.57,0),Vector3(.16,.22,.16),"d9b875","iron")
		var glow=StandardMaterial3D.new();glow.albedo_color=Color("dfbb77");glow.emission_enabled=true;glow.emission=Color("b68c48");lamp.material_override=glow
	for i in range(26):
		var z=-1.8+float(i)*.30;var x=sin(float(i)*2.7)*.56
		block(self,Vector3(x,-.012,z),Vector3(.24,.025,.22),"a8a38a",Vector3(0,float(i)*.7,0))
func resident(index: int):
	var scene=load("res://assets/"+(["shield","infantry","infantry"][index])+".glb");var model=scene.instantiate();ART.prepare_character(model)
	var bounds=BOUNDS.measure(model).bounds;var factor=1.18/bounds.size.y;model.scale*=factor
	model.position=[Vector3(-2.4,0,-.6),Vector3(.1,0,1.7),Vector3(2.8,0,3.8)][index];model.position-=Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)*factor;model.rotation.y=[.3,-.4,1.0][index];add_child(model)
	var players=model.find_children("*","AnimationPlayer",true,false)
	if not players.is_empty():players[0].play("Idle")
func clickable(parent: Node3D,id: String,p: Vector3,size: Vector3):
	var area=Area3D.new();var shape=CollisionShape3D.new();var box=BoxShape3D.new();box.size=size;shape.shape=box;area.add_child(shape);area.position=p;parent.add_child(area)
	area.input_event.connect(func(_camera,event,_pos,_normal,_shape):
		if event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT:selected.emit(id))
	area.mouse_entered.connect(func():labels[id].modulate=Color("ffe0a0"))
	area.mouse_exited.connect(func():labels[id].modulate=Color("f4ebd6"))
func activate(value: bool):
	visible=value;process_mode=Node.PROCESS_MODE_INHERIT if value else Node.PROCESS_MODE_DISABLED
	if value and camera:camera.make_current()

func house(id: String,title: String,p: Vector3,size: Vector3,roof_color: String,banner: bool):
	var root=Node3D.new();root.position=p;add_child(root)
	block(root,Vector3(0,.12,0),Vector3(size.x+.35,.3,size.z+.35),"77715e")
	block(root,Vector3(0,size.y*.5+.25,0),size,"d6c8a8")
	for x in [-size.x*.46,size.x*.46]:
		for z in [-size.z*.46,size.z*.46]:block(root,Vector3(x,size.y*.5+.25,z),Vector3(.13,size.y+.1,.13),"624b38")
	for y in [.42,size.y+.2]:block(root,Vector3(0,y,size.z*.5+.03),Vector3(size.x,.12,.13),"70543a")
	var height=size.y+.35;var rise=.95;var half=size.x*.58;var slope=atan2(rise,half)
	for side in [-1,1]:
		block(root,Vector3(side*half*.5,height+rise*.5,0),Vector3(sqrt(half*half+rise*rise),.16,size.z+.7),roof_color,Vector3(0,0,-side*slope))
		for row in range(4):
			var f=float(row+1)/5
			block(root,Vector3(side*half*f,height+rise*(1-f)+.10,0),Vector3(.025,.018,size.z+.72),"87775a",Vector3(0,0,-side*slope))
	block(root,Vector3(0,height+rise+.04,0),Vector3(.16,.15,size.z+.8),"70543b")
	for side in [-1,1]:
		var surface=SurfaceTool.new();surface.begin(Mesh.PRIMITIVE_TRIANGLES);surface.set_normal(Vector3(0,0,side))
		for point in [Vector3(-half*side,height,side*size.z*.5),Vector3(half*side,height,side*size.z*.5),Vector3(0,height+rise,side*size.z*.5)]:surface.add_vertex(point)
		var gable=MeshInstance3D.new();gable.mesh=surface.commit();gable.material_override=material("bdb391");root.add_child(gable)
	block(root,Vector3(size.x*.28,height+.8,-size.z*.2),Vector3(.4,1.3,.45),"8e826d")
	block(root,Vector3(size.x*.28,height+1.48,-size.z*.2),Vector3(.52,.14,.56),"b3a489")
	block(root,Vector3(0,.84,size.z*.5+.07),Vector3(.8,1.25,.08),"685039")
	for x in [-.26,0,.26]:block(root,Vector3(x,.84,size.z*.5+.12),Vector3(.018,1.2,.025),"af8d5c")
	cylinder(root,Vector3(.25,.82,size.z*.5+.17),.045,.07,"c3a35c").rotation.x=PI/2
	for x in [-size.x*.32,size.x*.32]:
		block(root,Vector3(x,1.25,size.z*.5+.1),Vector3(.52,.63,.09),"514e3d")
		block(root,Vector3(x,1.25,size.z*.5+.16),Vector3(.39,.48,.02),"ddb36b")
		block(root,Vector3(x,1.25,size.z*.5+.19),Vector3(.045,.55,.04),"6d5238")
		block(root,Vector3(x,1.25,size.z*.5+.19),Vector3(.45,.045,.04),"6d5238")
	block(root,Vector3(0,1.88,size.z*.5+.3),Vector3(1.5,.38,.12),"5c4430")
	if banner:
		block(root,Vector3(-size.x*.52,1.55,.2),Vector3(.07,2.7,.07),"604c37")
		block(root,Vector3(-size.x*.52+.28,2.1,.2),Vector3(.55,.85,.055),"577c78")
		block(root,Vector3(-size.x*.52+.28,2.1,.235),Vector3(.08,.56,.025),"e8c58b")
	labels[id]=sign_label(root,title,Vector3(0,height+rise+.6,0))
	clickable(root,id,Vector3(0,1,0),Vector3(size.x,3,size.z))
