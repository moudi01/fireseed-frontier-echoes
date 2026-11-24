extends RefCounted
const CHARACTER_SURFACE=preload("res://core/character_surface.gd")
## AD-01: authored low-frequency forms. All randomness is local and visual only.
static var mesh_cache={}
static var material_cache={}

static func mat(hex: String) -> StandardMaterial3D:
	if not material_cache.has(hex):
		var m=StandardMaterial3D.new();m.albedo_color=Color(hex);m.roughness=.92
		material_cache[hex]=m
	return material_cache[hex]

static func family(kind: String) -> Material:
	var key="family_"+kind
	if material_cache.has(key):return material_cache[key]
	var m: Material
	if kind=="wood":
		var shader=Shader.new()
		shader.code="shader_type spatial; varying vec3 p; void vertex(){p=VERTEX;} void fragment(){float grain=sin(p.y*9.0+sin(p.x*7.0)*0.5+sin(p.z*5.0)); ALBEDO=vec3(0.35,0.22,0.115)*(0.97+grain*0.045); ROUGHNESS=0.79;}"
		m=ShaderMaterial.new();m.shader=shader
	else:
		m=StandardMaterial3D.new()
		match kind:
			"iron":m.albedo_color=Color("7b8a8e");m.metallic=1.0;m.roughness=.52
			"cloth":m.albedo_color=Color("899d85");m.roughness=.96
			"leather":m.albedo_color=Color("6a4d34");m.roughness=.78
			_:m.albedo_color=Color("919080");m.roughness=.94
	m.resource_name="AD01_"+kind;m.set_meta("art_family",kind);material_cache[key]=m
	return m

static func earth(_tint="",_repeat=1.0) -> ShaderMaterial:
	if material_cache.has("ground"):return material_cache.ground
	var shader=Shader.new()
	shader.code="""shader_type spatial;
render_mode diffuse_lambert, specular_disabled;
uniform sampler2D ground_tex: source_color, filter_linear_mipmap_anisotropic, repeat_enable;
varying vec2 p;
void vertex(){p=(MODEL_MATRIX*vec4(VERTEX,1.0)).xz;}
void fragment(){
 float bend=0.28*p.y+sin(p.y*0.48)*0.7;
 float distance_to_road=abs(p.x-bend);
 float edge=sin(p.y*2.1)*0.07+sin(p.y*4.3)*0.025;
 float road=1.0-smoothstep(0.85+edge,1.65+edge,distance_to_road);
 float clearing=1.0-smoothstep(4.0,8.0,length(p*vec2(0.8,1.0)));
 vec3 grass=mix(vec3(0.17,0.205,0.15),vec3(0.245,0.28,0.205),clearing);
 vec3 soil=vec3(0.36,0.285,0.195);
 float rut_a=1.0-smoothstep(0.025,0.085,abs(distance_to_road-0.5));
 float rut_break=smoothstep(-0.2,0.5,sin(p.y*0.9)+0.35*sin(p.y*2.4));
 vec3 color=mix(grass,soil,road*0.80);
 color*=1.0-rut_a*rut_break*road*0.055;
 vec3 texture_color=texture(ground_tex,p*0.10).rgb;
 float paint=dot(texture_color,vec3(0.299,0.587,0.114));
 color*=0.96+paint*0.09;
 ALBEDO=color; ROUGHNESS=0.97;
}"""
	var m=ShaderMaterial.new();m.shader=shader;m.set_shader_parameter("ground_tex",load("res://assets/art026/forest_ground_v1.png"));material_cache.ground=m
	return m

static func chunk(kind: String,variant: int) -> ArrayMesh:
	var key=kind+str(variant)
	if mesh_cache.has(key):return mesh_cache[key]
	var rng=RandomNumberGenerator.new();rng.seed=27019+variant*83+(100 if kind=="stone" else 0)
	var sides=12 if kind=="leaf" else 7
	var profile=[.0,.54,.88,1.0,.92,.64,.0] if kind=="leaf" else [.0,.72,1.0,.78,.0]
	var offsets=[]
	for i in range(sides):offsets.append(rng.randf_range(.88,1.10))
	var s=SurfaceTool.new();s.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j in range(profile.size()-1):
		for i in range(sides):
			var points=[]
			for pair in [[j,i],[j,(i+1)%sides],[j+1,i],[j+1,(i+1)%sides]]:
				var row=int(pair[0]);var col=int(pair[1]);var a=TAU*float(col)/sides
				var y=float(row)/(profile.size()-1)*2.0-1.0
				var r=float(profile[row])*float(offsets[col]);var offset=.10*sin(float(row)*.8+variant)
				points.append(Vector3(cos(a)*r+offset,y,sin(a)*r))
			for tri in [[points[0],points[1],points[2]],[points[1],points[3],points[2]]]:
				var face=(tri[2]-tri[0]).cross(tri[1]-tri[0]).normalized()
				for v in tri:
					var normal=Vector3(v.x,v.y*.65,v.z).normalized() if kind=="leaf" else face
					s.set_normal(normal)
					var tone=1.0+v.y*.07+sin(atan2(v.z,v.x)*3.0+variant)*.035
					s.set_color(Color(tone,tone,tone));s.add_vertex(v)
	var mesh=s.commit();mesh_cache[key]=mesh;return mesh

static func mass(parent: Node3D,p: Vector3,size_value: Vector3,color: String,variant: int,kind="leaf") -> MeshInstance3D:
	var n=MeshInstance3D.new();n.mesh=chunk(kind,posmod(variant,5));n.position=p;n.scale=size_value
	var key=color+"_vertex"
	if not material_cache.has(key):
		var m=mat(color).duplicate();m.vertex_color_use_as_albedo=true;material_cache[key]=m
	n.material_override=material_cache[key];parent.add_child(n);return n

static func rod(parent: Node3D,a: Vector3,b: Vector3,radius: float,color="61533e") -> MeshInstance3D:
	var n=MeshInstance3D.new();var m=CylinderMesh.new();m.top_radius=radius*.65;m.bottom_radius=radius;m.height=a.distance_to(b);m.radial_segments=9
	n.mesh=m;n.material_override=mat(color);n.position=(a+b)*.5;n.basis=Basis(Quaternion(Vector3.UP,(b-a).normalized()));parent.add_child(n);return n

static func tree(parent: Node3D,p: Vector3,scale_value: float,variant: int) -> Node3D:
	var n=Node3D.new();n.position=p;n.rotation.y=variant*1.71;n.scale=Vector3.ONE*scale_value;parent.add_child(n)
	rod(n,Vector3.ZERO,Vector3(.1,2.8,0),.23)
	for angle in [.2,2.3,4.4]:
		rod(n,Vector3(.04,.16,0),Vector3(cos(angle)*.48,-.04,sin(angle)*.48),.10)
	rod(n,Vector3(.02,1.4,0),Vector3(-.75,2.6,.18),.12)
	rod(n,Vector3(.08,1.8,0),Vector3(.95,2.9,-.18),.11)
	if variant%2==0:
		mass(n,Vector3(-.70,2.6,.14),Vector3(1.18,.75,.9),"657b59",variant)
		mass(n,Vector3(.75,2.95,-.2),Vector3(1.35,.85,1.0),"71855d",variant+1)
		mass(n,Vector3(.0,3.45,.16),Vector3(1.16,.9,.88),"7e8e64",variant+2)
	else:
		mass(n,Vector3(-.48,2.7,.15),Vector3(.95,.97,.82),"5b7456",variant)
		mass(n,Vector3(.67,3.1,-.24),Vector3(1.05,1.16,.84),"6e825d",variant+1)
		mass(n,Vector3(-.14,3.85,.02),Vector3(.88,.8,.8),"7d8c64",variant+2)
	return n

static func shrub(parent: Node3D,p: Vector3,variant: int):
	mass(parent,p+Vector3(0,.20,0),Vector3(.65,.28,.42),"71815b",variant)
	mass(parent,p+Vector3(.34,.14,.15),Vector3(.36,.20,.32),"849068",variant+2)

static func rock(parent: Node3D,p: Vector3,variant: int) -> MeshInstance3D:
	return mass(parent,p+Vector3(0,.16,0),Vector3(.64,.3,.38),["909083","7c8275","a09a84"][posmod(variant,3)],variant,"stone")

static func prepare_character(model: Node) -> int:
	var changed=0
	for mesh in model.find_children("*","MeshInstance3D",true,false):
		if mesh.mesh==null:continue
		for i in range(mesh.mesh.get_surface_count()):
			var original=mesh.mesh.surface_get_material(i)
			if original==null:continue
			var name_value=str(original.resource_name)
			var kind=""
			if "Shield_Wood" in name_value:kind="wood"
			elif "Worn_Iron" in name_value:kind="iron"
			elif "Shield_Cloth" in name_value:kind="cloth"
			elif "Leather" in name_value:kind="leather"
			if not kind.is_empty():mesh.set_surface_override_material(i,family(kind));changed+=1
	# Imported clip names do not carry a loop suffix; explicitly prepare true cycles.
	for player in model.find_children("*","AnimationPlayer",true,false):
		for clip in ["Idle","Armature|walking_man|baselayer","BowReady"]:
			if player.has_animation(clip):player.get_animation(clip).loop_mode=Animation.LOOP_LINEAR
	CHARACTER_SURFACE.prepare(model)
	return changed
