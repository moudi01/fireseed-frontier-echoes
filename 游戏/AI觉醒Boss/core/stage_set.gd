extends Node3D
## Local primitive set pieces, visual only. No collision shapes or gameplay state.
const KIT=preload("res://core/scenery_kit.gd")
const ANOMALY_ART=preload("res://core/anomaly_art.gd")
const ART=preload("res://core/forest_art.gd")
var current=""
func mat(color: Color):
	var m=StandardMaterial3D.new();m.albedo_color=color;m.roughness=.9;return m
func box(parent: Node3D,pos: Vector3,size: Vector3,color: Color):
	var n=MeshInstance3D.new();var m=BoxMesh.new();m.size=size;n.mesh=m;n.material_override=mat(color);n.position=pos;parent.add_child(n);return n
func cylinder(parent: Node3D,pos: Vector3,radius: float,length: float,color: Color):
	var n=MeshInstance3D.new();var m=CylinderMesh.new();m.top_radius=radius;m.bottom_radius=radius;m.height=length;m.radial_segments=8;n.mesh=m;n.material_override=mat(color);n.position=pos;parent.add_child(n);return n
func show_scene(value: String):
	if current==value:return
	current=value
	for child in get_children():remove_child(child);child.queue_free()
	if value=="caravan":
		var cart=Node3D.new();cart.position=Vector3(-3.1,.2,-1.3);cart.rotation=Vector3(.05,-.25,.20);add_child(cart)
		KIT.block(cart,Vector3(0,.56,0),Vector3(1.8,.13,1.05),"9a7955")
		for z in [-.54,.54]:
			for y in [.78,1.04]:KIT.block(cart,Vector3(0,y,z),Vector3(1.85,.18,.07),"a48960")
		for x in [-.72,.72]:
			for z in [-.54,.54]:KIT.block(cart,Vector3(x,.84,z),Vector3(.08,.72,.09),"6f573e")
		# One missing wheel makes the damage readable; no simulated obstruction.
		for coords in [Vector2(-.65,-.68),Vector2(.65,-.68),Vector2(.65,.68)]:KIT.wheel(cart,Vector3(coords.x,.37,coords.y),.42)
		for z in [-.3,.3]:KIT.rod(cart,Vector3(.75,.5,z),Vector3(2,.30,z),.045)
		KIT.crate(cart,Vector3(-.25,.64,.07),.58);KIT.sack(cart,Vector3(.45,.64,0),.8)
		var detached=KIT.wheel(self,Vector3(-3.9,.12,-.12),.42);detached.rotation=Vector3(-1.25,.2,.12)
		KIT.sack(self,Vector3(-2,.02,-.65),1.1);KIT.sack(self,Vector3(-1.5,.02,-.9),.85,"899781")
		KIT.crate(self,Vector3(-1.8,.02,-1.7),.52)
	elif value=="camp":
		var base=Vector3(-3,.04,-1.0)
		for i in range(9):
			var a=float(i)*TAU/9;ART.rock(self,base+Vector3(cos(a)*.48,0,sin(a)*.48),i%2).scale=Vector3.ONE*.32
		for z in [-.16,.16]:KIT.rod(self,base+Vector3(-.35,.09,z),base+Vector3(.35,.09,-z),.07,"68513d")
		var coal=KIT.block(self,base+Vector3(0,.13,0),Vector3(.37,.07,.29),"b27642")
		var ember=StandardMaterial3D.new();ember.albedo_color=Color("bd8548");ember.emission_enabled=true;ember.emission=Color("a55729");coal.material_override=ember
		for x in [-.67,.67]:KIT.rod(self,base+Vector3(x,0,0),base+Vector3(x,1.05,0),.035)
		KIT.rod(self,base+Vector3(-.7,1.05,0),base+Vector3(.7,1.05,0),.035)
		KIT.rod(self,base+Vector3(0,.98,0),base+Vector3(0,.64,0),.015,"596b72","iron")
		KIT.cylinder(self,base+Vector3(0,.51,0),.21,.26,"596b72","iron",.25)
		KIT.cylinder(self,base+Vector3(0,.65,0),.25,.03,"909087","iron")
		KIT.block(self,base+Vector3(-1.05,.025,.82),Vector3(1.1,.045,.7),"899781","cloth",Vector3(0,.2,0))
		KIT.block(self,base+Vector3(-1.4,.13,.75),Vector3(.22,.19,.66),"a0aa8e","cloth",Vector3(0,.2,0))
		KIT.sack(self,base+Vector3(.9,0,-.5),.8);KIT.bench(self,base+Vector3(.2,0,1.1),1.35)
		var light=OmniLight3D.new();light.position=base+Vector3(0,.5,0);light.light_color=Color("ffbd79");light.light_energy=.35;light.omni_range=2;add_child(light)
	elif value.begins_with("boundary_"):
		ANOMALY_ART.boundary(self,value=="boundary_observed")
	elif value=="memory":
		ANOMALY_ART.room(self)
