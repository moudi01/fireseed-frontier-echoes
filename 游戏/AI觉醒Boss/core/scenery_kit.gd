extends RefCounted
## Locally authored scenery. Shared material families; no state or gameplay collision.
const ART=preload("res://core/forest_art.gd")
static var materials={}
static func mat(color: String,kind="wall") -> Material:
	var key=color+":"+kind
	if materials.has(key):return materials[key]
	var m=StandardMaterial3D.new();m.albedo_color=Color(color)
	m.roughness={"iron":.53,"cloth":.98,"wood":.87,"wall":.94,"stone":.96}.get(kind,.9)
	if kind=="iron":m.metallic=.85
	if kind in ["wall","cloth","wood"]:
		var noise=FastNoiseLite.new();noise.seed=29029;noise.frequency=.045
		var tex=NoiseTexture2D.new();tex.width=128;tex.height=128;tex.noise=noise
		var ramp=Gradient.new();ramp.colors=PackedColorArray([Color(.88,.88,.88),Color.WHITE]);tex.color_ramp=ramp;m.albedo_texture=tex
	materials[key]=m;return m
static func block(parent: Node3D,p: Vector3,size: Vector3,color: String,kind="wood",rot=Vector3.ZERO) -> MeshInstance3D:
	var n=MeshInstance3D.new();var mesh=BoxMesh.new();mesh.size=size;n.mesh=mesh;n.material_override=mat(color,kind);n.position=p;n.rotation=rot;parent.add_child(n);return n
static func cylinder(parent: Node3D,p: Vector3,r: float,h: float,color: String,kind="wood",top=-1.0) -> MeshInstance3D:
	var n=MeshInstance3D.new();var mesh=CylinderMesh.new();mesh.bottom_radius=r;mesh.top_radius=r if top<0 else top;mesh.height=h;mesh.radial_segments=12;n.mesh=mesh;n.material_override=mat(color,kind);n.position=p;parent.add_child(n);return n
static func rod(parent: Node3D,a: Vector3,b: Vector3,r: float,color="6f573e",kind="wood"):
	var n=cylinder(parent,(a+b)*.5,r,a.distance_to(b),color,kind)
	var dir=(b-a).normalized();n.quaternion=Quaternion(Vector3.UP,dir);return n
static func crate(parent: Node3D,p: Vector3,s=.65):
	var root=Node3D.new();root.position=p;parent.add_child(root)
	block(root,Vector3(0,s*.5,0),Vector3(s,s,s),"9a7955")
	for x in [-.43,.43]:
		block(root,Vector3(x*s,s*.5,s*.51),Vector3(s*.10,s,s*.06),"66533e")
		block(root,Vector3(x*s,s*1.01,0),Vector3(s*.10,s*.05,s),"b19468")
	rod(root,Vector3(-s*.42,s*.1,s*.54),Vector3(s*.42,s*.9,s*.54),.025,"c1a477")
	return root
static func barrel(parent: Node3D,p: Vector3,s=1.0):
	var root=Node3D.new();root.position=p;root.scale=Vector3.ONE*s;parent.add_child(root)
	cylinder(root,Vector3(0,.36,0),.29,.72,"90704e", "wood",.26)
	for y in [.13,.59]:cylinder(root,Vector3(0,y,0),.298,.055,"59666a","iron")
	cylinder(root,Vector3(0,.73,0),.257,.035,"b09163")
	return root
static func sack(parent: Node3D,p: Vector3,s=1.0,color="b3a17d"):
	var root=Node3D.new();root.position=p;root.scale=Vector3.ONE*s;parent.add_child(root)
	var body=MeshInstance3D.new();var mesh=SphereMesh.new();mesh.radius=.25;mesh.height=.58;mesh.radial_segments=12;mesh.rings=6
	body.mesh=mesh;body.material_override=mat(color,"cloth");body.position.y=.29;body.scale=Vector3(1.3,1,.85);root.add_child(body)
	cylinder(root,Vector3(0,.59,0),.09,.12,color,"cloth",.12);cylinder(root,Vector3(0,.56,0),.09,.025,"6e5842")
	return root
static func bench(parent: Node3D,p: Vector3,length=1.4):
	var root=Node3D.new();root.position=p;parent.add_child(root)
	block(root,Vector3(0,.47,0),Vector3(length,.11,.37),"9a7955")
	for x in [-length*.36,length*.36]:block(root,Vector3(x,.22,0),Vector3(.12,.44,.32),"64543f")
	return root
static func canopy(parent: Node3D,p: Vector3,size: Vector2,color: String,height=2.05):
	var root=Node3D.new();root.position=p;parent.add_child(root)
	for x in [-size.x*.5,size.x*.5]:
		for z in [-size.y*.5,size.y*.5]:
			rod(root,Vector3(x,0,z),Vector3(x,height,z),.065)
			rod(root,Vector3(x,height-.5,z),Vector3(x-signf(x)*.35,height,z),.04)
	var half=size.x*.56;var rise=.45
	for side in [-1,1]:
		block(root,Vector3(side*half*.5,height+rise*.5,0),Vector3(sqrt(half*half+rise*rise),.055,size.y+.35),color,"cloth",Vector3(0,0,-side*atan2(rise,half)))
		block(root,Vector3(side*half,height-.10,0),Vector3(.045,.24,size.y+.35),color,"cloth")
	rod(root,Vector3(0,height+rise,-size.y*.6),Vector3(0,height+rise,size.y*.6),.05)
	return root
static func wheel(parent: Node3D,p: Vector3,r=.46):
	var root=Node3D.new();root.position=p;parent.add_child(root)
	var rim=MeshInstance3D.new();var torus=TorusMesh.new();torus.inner_radius=r*.79;torus.outer_radius=r;torus.rings=16;torus.ring_segments=6
	rim.mesh=torus;rim.material_override=mat("66523d","wood");rim.rotation.x=PI/2;root.add_child(rim)
	for a in range(6):
		var v=Vector3(cos(a*PI/3),sin(a*PI/3),0)*r*.86;rod(root,-v,v,.028,"ac8d61")
	cylinder(root,Vector3.ZERO,.09,.18,"566163","iron").rotation.x=PI/2
	return root
static func map_table(parent: Node3D,p: Vector3):
	var root=Node3D.new();root.position=p;parent.add_child(root)
	block(root,Vector3(0,.86,0),Vector3(1.6,.12,1.05),"a4845a")
	for x in [-.62,.62]:
		for z in [-.35,.35]:block(root,Vector3(x,.42,z),Vector3(.10,.84,.10),"66513b")
	block(root,Vector3(0,.929,0),Vector3(1.2,.018,.76),"e2d2b4","cloth")
	var pts=[Vector3(-.46,.944,.25),Vector3(-.2,.944,-.10),Vector3(.15,.944,.06),Vector3(.45,.944,-.25)]
	for i in range(3):rod(root,pts[i],pts[i+1],.012,"9a7955")
	for v in pts:cylinder(root,v,.034,.025,"596b72","iron")
	cylinder(root,Vector3(.52,.95,.27),.055,.035,"b79b62","iron")
	return root
