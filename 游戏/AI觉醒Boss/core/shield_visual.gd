extends Node3D
## Cosmetic fantasy ward bound to the equipment's original skin. No rule writes.
const PULSE_SECONDS=.65
const CENTER_ALPHA=.045
const EDGE_ALPHA=.68
var figure={}
var equipment:MeshInstance3D
var shell:MeshInstance3D
var barrier:MeshInstance3D
var barrier_mat:ShaderMaterial
var barrier_span=Vector2.ZERO
var barrier_center=Vector3.ZERO
var barrier_normal=Vector3.FORWARD
var barrier_bind_vertices=PackedVector3Array()
var barrier_vertices=PackedVector3Array()
var uploaded_expansion=1.0
var magic_expansion=1.0
var impact_strength=0.0
var formation_strength=0.0
var valid=false
var enabled=true
var active_shield=false
var age=PULSE_SECONDS
var pulse=""
var triggers=0
var mat:StandardMaterial3D
var phase=0.0
const WARD_SHADER="""
shader_type spatial;
render_mode unshaded, cull_disabled, blend_mix, depth_draw_never, fog_disabled;
uniform vec3 barrier_center;
uniform float expansion=1.0;
uniform float impact=0.0;
uniform float formed=0.0;
uniform float phase=0.0;
uniform float center_alpha=.045;
uniform float edge_alpha=.68;
uniform vec4 jade: source_color=vec4(.23,.68,.68,1.0);
uniform vec4 gold: source_color=vec4(.94,.75,.38,1.0);
void fragment(){
 vec2 p=UV*2.0-1.0;
 float r=length(p);
 float aa=max(fwidth(r),.004);
 float inside=1.0-smoothstep(.985-aa,1.0+aa,r);
 float rim=1.0-smoothstep(.012,.029,abs(r-.955));
 float inner=(1.0-smoothstep(.003,.012,abs(r-.835)))*.48;
 float angle=atan(p.y,p.x);
 float sector=abs(fract((angle+3.141593)/6.283186*12.0+.5)-.5);
 float glyph=(1.0-smoothstep(.055,.09,sector))*smoothstep(.86,.89,r)*(1.0-smoothstep(.92,.935,r));
 float facet=(1.0-smoothstep(.004,.012,abs(abs(p.x)*.54+abs(p.y)*.84-.64)))*.11;
 float sweep_radius=mix(.15,1.16,1.0-impact);
 float wave=(1.0-smoothstep(.025,.075,abs(r-sweep_radius)))*impact;
 float casting=(1.0-smoothstep(.02,.075,abs(r-(.30+.64*(1.0-formed)))))*formed;
 float shimmer=.88+.12*sin(phase*1.6+angle*3.0);
 float strength=max(rim,max(inner,glyph));
 float alpha=(center_alpha*(.45+.55*r)+strength*edge_alpha*shimmer+wave*.28+casting*.16+facet)*inside;
 // Transparent center and dark depth-tested silhouette keep bodies/ground readable.
 ALBEDO=mix(jade.rgb,gold.rgb,clamp(glyph*.9+inner*.5+wave*.7+casting*.65,0.0,1.0));
 EMISSION=ALBEDO*(.20+strength*.28+wave*.30);
 ALPHA=min(alpha,.76);
}
"""
func configure(f:Dictionary):
 figure=f;visible=false
 if f.unit_type!="lorne" or not f.model.get_meta("action_issues",["unchecked"]).is_empty():return
 var shields=f.model.find_children("Equipment_Shield*","MeshInstance3D",true,false)
 if shields.size()!=1:return
 equipment=shields[0]
 if equipment.skin==null or equipment.mesh==null:return
 var skeleton=equipment.get_node_or_null(equipment.skeleton)
 if not skeleton is Skeleton3D:return
 var arrays=equipment.mesh.surface_get_arrays(0)
 if arrays[Mesh.ARRAY_VERTEX].is_empty() or arrays[Mesh.ARRAY_NORMAL]==null or arrays[Mesh.ARRAY_BONES]==null or arrays[Mesh.ARRAY_WEIGHTS]==null:return
 var vertices=arrays[Mesh.ARRAY_VERTEX];var normals=arrays[Mesh.ARRAY_NORMAL];var sums={};var smooth=PackedVector3Array()
 for i in range(vertices.size()):sums[vertices[i]]=sums.get(vertices[i],Vector3.ZERO)+normals[i]
 for i in range(vertices.size()):smooth.append(sums[vertices[i]].normalized() if sums[vertices[i]].length_squared()>.00001 else normals[i])
 arrays[Mesh.ARRAY_NORMAL]=smooth
 # Expanding a rigid shield must never guess weights for a deformable replacement.
 var source_bones:PackedInt32Array=arrays[Mesh.ARRAY_BONES];var source_weights:PackedFloat32Array=arrays[Mesh.ARRAY_WEIGHTS]
 var influence_count=int(float(source_bones.size())/float(vertices.size()))
 if influence_count!=4:return
 var reference={}
 for k in range(influence_count):
  if source_weights[k]>.0001:reference[source_bones[k]]=source_weights[k]
 if reference.is_empty():return
 for i in range(vertices.size()):
  var influences={}
  for k in range(influence_count):
   var index=i*influence_count+k
   if source_weights[index]>.0001:influences[source_bones[index]]=source_weights[index]
  if influences!=reference:return
 reparent(equipment,false);transform=Transform3D.IDENTITY
 var wood=ArrayMesh.new();wood.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
 shell=MeshInstance3D.new();shell.name="ShieldRim";shell.mesh=wood;shell.skin=equipment.skin;add_child(shell);shell.skeleton=shell.get_path_to(skeleton)
 mat=StandardMaterial3D.new();mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;mat.cull_mode=BaseMaterial3D.CULL_FRONT;mat.depth_draw_mode=BaseMaterial3D.DEPTH_DRAW_DISABLED;mat.grow=true
 shell.material_override=mat;shell.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
 make_barrier(arrays,skeleton)
 valid=true;update_color()
func make_barrier(source:Array,skeleton:Skeleton3D):
 var points:PackedVector3Array=source[Mesh.ARRAY_VERTEX]
 for p in points:barrier_center+=p
 barrier_center/=float(points.size())
 # Least-variance axis fits the actual slanted shield plane instead of its AABB.
 var xx=0.0;var yy=0.0;var zz=0.0;var xy=0.0;var xz=0.0;var yz=0.0
 for p in points:
  var q=p-barrier_center;xx+=q.x*q.x;yy+=q.y*q.y;zz+=q.z*q.z;xy+=q.x*q.y;xz+=q.x*q.z;yz+=q.y*q.z
 var covariance=Basis(Vector3(xx,xy,xz),Vector3(xy,yy,yz),Vector3(xz,yz,zz))
 if absf(covariance.determinant())>.00000001:
  var inverse=covariance.inverse();barrier_normal=Vector3(.31,.77,.56)
  for _i in range(16):barrier_normal=(inverse*barrier_normal).normalized()
 else:barrier_normal=Vector3.RIGHT
 if barrier_normal.dot(Vector3(barrier_center.x,0,barrier_center.z))<0:barrier_normal=-barrier_normal
 var up=(Vector3.UP-barrier_normal*barrier_normal.dot(Vector3.UP)).normalized()
 var right=up.cross(barrier_normal).normalized()
 var half_x=0.0;var half_y=0.0
 for p in points:
  half_x=maxf(half_x,absf((p-barrier_center).dot(right)));half_y=maxf(half_y,absf((p-barrier_center).dot(up)))
 barrier_span=Vector2(maxf(half_x*4.9,half_y*4.4),half_y*4.4)
 # A shallow curved, open-center ward: broad enough to read as fantasy protection,
 # while original rigid shield weights keep it attached through every animation.
 var vertices=PackedVector3Array();var uv=PackedVector2Array();var bones=PackedInt32Array();var weights=PackedFloat32Array();var indices=PackedInt32Array()
 var source_bones:PackedInt32Array=source[Mesh.ARRAY_BONES];var source_weights:PackedFloat32Array=source[Mesh.ARRAY_WEIGHTS]
 var count=int(float(source_bones.size())/float(points.size()))
 const COLS=24
 const ROWS=24
 for y in range(ROWS+1):
  for x in range(COLS+1):
   var coord=Vector2(float(x)/COLS,float(y)/ROWS);var p=coord*2.0-Vector2.ONE
   vertices.append(barrier_center+right*p.x*barrier_span.x*.5+up*p.y*barrier_span.y*.5+barrier_normal*(.035+.10*(1.0-p.x*p.x)))
   uv.append(coord)
   for k in range(count):bones.append(source_bones[k]);weights.append(source_weights[k])
 for y in range(ROWS):
  for x in range(COLS):
   var i=y*(COLS+1)+x;indices.append_array(PackedInt32Array([i,i+1,i+COLS+1,i+1,i+COLS+2,i+COLS+1]))
 var arrays=[];arrays.resize(Mesh.ARRAY_MAX);arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_TEX_UV]=uv;arrays[Mesh.ARRAY_BONES]=bones;arrays[Mesh.ARRAY_WEIGHTS]=weights;arrays[Mesh.ARRAY_INDEX]=indices
 barrier_bind_vertices=vertices.duplicate();barrier_vertices=vertices.duplicate()
 var mesh=ArrayMesh.new();mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays,[],{},Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE)
 barrier=MeshInstance3D.new();barrier.name="FantasyWard";barrier.mesh=mesh;barrier.skin=equipment.skin;add_child(barrier);barrier.skeleton=barrier.get_path_to(skeleton);barrier.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
 var shader=Shader.new();shader.code=WARD_SHADER;barrier_mat=ShaderMaterial.new();barrier_mat.shader=shader;barrier_mat.set_shader_parameter("barrier_center",barrier_center);barrier_mat.set_shader_parameter("center_alpha",CENTER_ALPHA);barrier_mat.set_shader_parameter("edge_alpha",EDGE_ALPHA);barrier.material_override=barrier_mat
func sync(unit:Dictionary,events:Array,current:Dictionary,fresh:bool,snap:bool):
 active_shield=valid and enabled and unit.get("alive",true) and int(unit.get("shield_pool",0))>0 and equipment.visible
 visible=active_shield
 if snap or not active_shield:age=PULSE_SECONDS;pulse=""
 elif fresh:
  var formed=events.any(func(e):return e.get("action")=="shield_formed" and e.get("actor")==unit.instance_id)
  var absorbed=events.any(func(e):return e.get("action")=="attack" and int(e.get("absorbed",0))>0 and current.get(int(e.get("target",-1)),{}).get("side","")==unit.side)
  if formed or absorbed:age=0;pulse="formed" if formed else "absorbed";triggers+=1
 update_color()
func advance(seconds:float):
 var delta=maxf(0,seconds);age=minf(PULSE_SECONDS,age+delta);phase=fmod(phase+delta,TAU*16.0);update_color()
func update_color():
 if mat==null:return
 var strength=1.0-smoothstep(0,PULSE_SECONDS,age)
 mat.albedo_color=Color("79b4a8").lerp(Color("e3d9aa") if pulse=="formed" else Color("bad4c9"),strength*.75);mat.albedo_color.a=.46+strength*.40
 mat.grow_amount=(.014+strength*.010)*figure.node.global_basis.get_scale().x/maxf(.0001,global_basis.get_scale().x)
 formation_strength=strength if pulse=="formed" else 0.0
 impact_strength=strength if pulse=="absorbed" else 0.0
 magic_expansion=lerpf(.35,1.0,smoothstep(0,.46,age)) if pulse=="formed" else 1.0
 update_expansion_vertices()
 barrier_mat.set_shader_parameter("expansion",magic_expansion);barrier_mat.set_shader_parameter("impact",impact_strength);barrier_mat.set_shader_parameter("formed",formation_strength);barrier_mat.set_shader_parameter("phase",phase)
func update_expansion_vertices():
 if barrier==null or is_equal_approx(uploaded_expansion,magic_expansion):return
 # Spatial shader VERTEX has already received skinning in this renderer. Scaling
 # there around a bind-space center moves the ward toward the knees. Upload the
 # small position-only buffer BEFORE skinning; keep mesh/skin/material resources.
 for i in range(barrier_bind_vertices.size()):
  barrier_vertices[i]=barrier_center+(barrier_bind_vertices[i]-barrier_center)*magic_expansion
 barrier.mesh.surface_update_vertex_region(0,0,barrier_vertices.to_byte_array())
 uploaded_expansion=magic_expansion
func get_visual_state()->Dictionary:
 return {"expansion":magic_expansion,"impact":impact_strength,"formed":formation_strength,"phase":phase,"center_alpha":CENTER_ALPHA,"edge_alpha":EDGE_ALPHA,"span":barrier_span,"center":barrier_center,"normal":barrier_normal,"pulse_seconds":PULSE_SECONDS}
