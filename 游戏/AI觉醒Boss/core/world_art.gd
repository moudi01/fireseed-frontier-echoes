extends RefCounted
## Local visual assets only. Never uses the campaign/global random stream.
static var meshes={}
static var materials={}
static func mat(hex: String) -> StandardMaterial3D:
	if materials.has(hex):return materials[hex]
	var m=StandardMaterial3D.new();m.albedo_color=Color(hex);m.roughness=.94;materials[hex]=m;return m
static func earth(tint="bab29e",_repeat=4.0) -> ShaderMaterial:
	var shader=Shader.new();shader.code="shader_type spatial; render_mode diffuse_lambert, specular_disabled; uniform sampler2D ground_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable; uniform vec4 base_color : source_color; varying vec2 world_uv; void vertex(){ world_uv=(MODEL_MATRIX*vec4(VERTEX,1.0)).xz; } void fragment(){ float clearing=1.0-smoothstep(3.0,7.0,length(world_uv*vec2(0.8,1.0))); vec3 soil=mix(base_color.rgb,vec3(0.24,0.22,0.17),clearing*0.28); ALBEDO=mix(soil,texture(ground_tex,world_uv*0.12).rgb,0.20); ROUGHNESS=1.0; }"
	var m=ShaderMaterial.new();m.shader=shader;m.set_shader_parameter("ground_tex",load("res://assets/art026/forest_ground_v1.png"));m.set_shader_parameter("base_color",Color({"a9b49f":"7c8872","b9b1a1":"7c8872","c3bba7":"7c8872"}.get(tint,tint)).srgb_to_linear());return m
static func blob(variant: int) -> ArrayMesh:
	if meshes.has(variant):return meshes[variant]
	var rng=RandomNumberGenerator.new();rng.seed=26001+variant
	var rings=[];var sides=9;var count=5
	for j in range(count+1):
		var points=[];var theta=PI*float(j)/count
		for i in range(sides):
			var angle=TAU*float(i)/sides;var r=sin(theta)*rng.randf_range(.84,1.12)
			points.append(Vector3(cos(angle)*r,cos(theta)*rng.randf_range(.88,1.07),sin(angle)*r))
		rings.append(points)
	var s=SurfaceTool.new();s.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j in range(count):
		for i in range(sides):
			var a=rings[j][i];var b=rings[j][(i+1)%sides];var c=rings[j+1][i];var d=rings[j+1][(i+1)%sides]
			for tri in [[a,b,c],[b,d,c]]:
				var normal=(tri[1]-tri[0]).cross(tri[2]-tri[0]).normalized();var tone=rng.randf_range(.93,1.04)
				for v in tri:s.set_normal(normal);s.set_color(Color(tone,tone,tone));s.add_vertex(v)
	var mesh=s.commit();meshes[variant]=mesh;return mesh
static func lump(parent: Node3D,p: Vector3,scale_value: Vector3,hex: String,variant: int):
	var n=MeshInstance3D.new();n.mesh=blob(posmod(variant,8));n.position=p;n.scale=scale_value
	var key=hex+"leaf"
	if not materials.has(key):
		var m=mat(hex).duplicate();m.vertex_color_use_as_albedo=true;m.cull_mode=BaseMaterial3D.CULL_DISABLED;materials[key]=m
	n.material_override=materials[key];parent.add_child(n);return n
static func rod(parent: Node3D,a: Vector3,b: Vector3,radius: float,hex: String):
	var n=MeshInstance3D.new();var mesh=CylinderMesh.new();mesh.top_radius=radius*.65;mesh.bottom_radius=radius;mesh.height=a.distance_to(b);mesh.radial_segments=7;n.mesh=mesh;n.material_override=mat(hex);n.position=(a+b)*.5;n.basis=Basis(Quaternion(Vector3.UP,(b-a).normalized()));parent.add_child(n)
static func tree(parent: Node3D,p: Vector3,size_value: float,index: int):
	var n=Node3D.new();n.position=p;n.scale=Vector3.ONE*size_value;n.rotation.y=index*2.39;parent.add_child(n)
	rod(n,Vector3(0,0,0),Vector3(.12,2.45,0),.14,"514a3b")
	rod(n,Vector3(0,1.2,0),Vector3(.72,2.3,.12),.075,"625542")
	rod(n,Vector3(0,1.3,0),Vector3(-.5,2.6,-.34),.065,"625542")
	var colors=["55674d","64734f","6d7b54","77845b"]
	lump(n,Vector3(.65,2.35,.06),Vector3(.8,.75,.72),colors[index%4],index)
	lump(n,Vector3(-.48,2.6,-.25),Vector3(.8,.85,.75),colors[(index+1)%4],index+1)
	lump(n,Vector3(.05,3.1,0),Vector3(.92,.9,.82),colors[(index+2)%4],index+2)
	return n
static func shrub(parent: Node3D,p: Vector3,index: int):
	lump(parent,p+Vector3(0,.25,0),Vector3(.5,.35,.42),["637457","738261","8b885e"][index%3],index)
static func rock(parent: Node3D,p: Vector3,index: int):
	return lump(parent,p,Vector3(.5,.32,.4),["777d73","8c8d7b","626d64"][index%3],index)
