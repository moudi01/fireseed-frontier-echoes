extends RefCounted
## Read-only geometry for the currently contracted, rigidly RightHand-skinned
## Equipment_Sword meshes. Endpoints approximate the blade centreline; this is
## not a collision hull, hit authority, IK solver or proof of visible contact.
## Usage: var probe=MELEE.new(); probe.prepare(model); probe.sample(board)
## Re-run prepare after replacing a mesh/skin or changing its bind layout.
var prepared=false
var diagnostic="not prepared"
var mesh_ref: WeakRef
var skeleton_ref: WeakRef
var model_ref: WeakRef
var mesh_resource: Mesh
var skin_resource: Skin
var bone=-1
var bind_index=-1
var inverse_bind=Transform3D.IDENTITY
var local_hilt=Vector3.ZERO
var local_tip=Vector3.ZERO
var blade_vertices=PackedVector3Array()
var surface_index=-1
var vertex_count=0

func fail(reason: String) -> Dictionary:
	prepared=false;diagnostic=reason
	return {"valid":false,"diagnostic":reason}

func prepare(model: Node) -> Dictionary:
	prepared=false;mesh_ref=null;skeleton_ref=null;model_ref=null
	mesh_resource=null;skin_resource=null;bone=-1;bind_index=-1
	blade_vertices=PackedVector3Array();surface_index=-1;vertex_count=0
	if not is_instance_valid(model):return fail("model missing")
	model_ref=weakref(model)
	if not model.has_meta("action_profile") or not model.get_meta("action_issues",["unchecked"]).is_empty():return fail("action contract not accepted")
	var found=model.find_children("Equipment_Sword*","MeshInstance3D",true,false)
	if found.size()!=1:return fail("exactly one sword required")
	var mesh: MeshInstance3D=found[0]
	if mesh.mesh==null or mesh.skin==null:return fail("skinned sword mesh missing")
	var skeleton=mesh.get_node_or_null(mesh.skeleton) as Skeleton3D
	if skeleton==null:return fail("skeleton missing")
	var hand=skeleton.find_bone("RightHand")
	if hand<0:return fail("RightHand missing")
	var candidates=[]
	for surface in range(mesh.mesh.get_surface_count()):
		var arrays=mesh.mesh.surface_get_arrays(surface)
		if arrays.size()!=Mesh.ARRAY_MAX:return fail("surface arrays missing")
		var vertices=arrays[Mesh.ARRAY_VERTEX]
		var bones=arrays[Mesh.ARRAY_BONES]
		var weights=arrays[Mesh.ARRAY_WEIGHTS]
		if vertices==null or vertices.size()<2 or bones==null or weights==null:return fail("skin vertex data missing")
		if bones.size()%vertices.size()!=0:return fail("invalid influence count")
		var influences=int(bones.size()/vertices.size())
		if influences not in [4,8] or bones.size()!=weights.size():return fail("unsupported skin layout")
		var unique=PackedVector3Array()
		for i in range(vertices.size()):
			var positive=0;var total=0.0
			for j in range(influences):
				var index=i*influences+j;var weight=float(weights[index])
				if weight<=0.000001:continue
				var bind=int(bones[index]);positive+=1;total+=weight
				if bind<0 or bind>=mesh.skin.get_bind_count():return fail("invalid skin bind")
				var name=mesh.skin.get_bind_name(bind)
				var mapped=skeleton.find_bone(name) if not name.is_empty() else mesh.skin.get_bind_bone(bind)
				if mapped!=hand:return fail("sword is not rigid RightHand equipment")
				if bind_index<0:bind_index=bind
				elif bind_index!=bind:return fail("multiple inverse binds unsupported")
			if positive!=1 or absf(total-1.0)>.0001:return fail("nonrigid or unnormalised sword weights")
			if not unique.has(vertices[i]):unique.append(vertices[i])
		vertex_count+=vertices.size()
		var axis=_principal_axis(unique)
		if axis.length_squared()<.99:continue
		var low=INF;var high=-INF
		for point in unique:
			var projection=point.dot(axis);low=minf(low,projection);high=maxf(high,projection)
		candidates.append({"surface":surface,"vertices":unique,"axis":axis,"low":low,"high":high,"span":high-low})
	if candidates.is_empty():return fail("blade axis unavailable")
	candidates.sort_custom(func(a,b):return a.span>b.span)
	var chosen=candidates[0]
	if chosen.span<=.00001:return fail("blade span degenerate")
	var low_center=Vector3.ZERO;var high_center=Vector3.ZERO;var low_count=0;var high_count=0
	# Small end caps suppress thickness while retaining actual mesh-tip position.
	var cap=chosen.span*.025
	for point in chosen.vertices:
		var projection=point.dot(chosen.axis)
		if projection<=chosen.low+cap:low_center+=point;low_count+=1
		if projection>=chosen.high-cap:high_center+=point;high_count+=1
	if low_count==0 or high_count==0:return fail("blade end caps unavailable")
	low_center/=low_count;high_center/=high_count
	inverse_bind=mesh.skin.get_bind_pose(bind_index)
	if absf(inverse_bind.basis.determinant())<.0000001:return fail("singular inverse bind")
	var hand_in_mesh=inverse_bind.affine_inverse()*Vector3.ZERO
	if low_center.distance_squared_to(hand_in_mesh)>high_center.distance_squared_to(hand_in_mesh):
		local_hilt=high_center;local_tip=low_center
	else:
		local_hilt=low_center;local_tip=high_center
	bone=hand;mesh_ref=weakref(mesh);skeleton_ref=weakref(skeleton)
	mesh_resource=mesh.mesh;skin_resource=mesh.skin
	blade_vertices=chosen.vertices;surface_index=chosen.surface
	prepared=true;diagnostic="rigid RightHand blade centreline; longest mesh surface, PCA end caps"
	return {"valid":true,"diagnostic":diagnostic,"surface":surface_index,"vertex_count":vertex_count,"blade_vertex_count":blade_vertices.size(),"local_hilt":local_hilt,"local_tip":local_tip,"bone":bone,"bind":bind_index}

func sample(space: Node3D=null,include_blade_vertices: bool=false) -> Dictionary:
	var invalid={"valid":false,"diagnostic":diagnostic,"hilt":Vector3.ZERO,"tip":Vector3.ZERO,"blade_points":PackedVector3Array()}
	if not prepared:return invalid
	var model=model_ref.get_ref();var mesh=mesh_ref.get_ref();var skeleton=skeleton_ref.get_ref()
	if not is_instance_valid(model) or not is_instance_valid(mesh) or not is_instance_valid(skeleton):invalid.diagnostic="prepared nodes freed";return invalid
	if not model.get_meta("action_issues",["unchecked"]).is_empty():invalid.diagnostic="action contract invalidated";return invalid
	if not mesh.is_inside_tree() or not mesh.is_visible_in_tree():invalid.diagnostic="sword hidden or outside tree";return invalid
	if mesh.mesh!=mesh_resource or mesh.skin!=skin_resource:invalid.diagnostic="mesh or skin replaced; prepare again";return invalid
	if mesh.get_node_or_null(mesh.skeleton)!=skeleton or bone>=skeleton.get_bone_count() or str(skeleton.get_bone_name(bone))!="RightHand":invalid.diagnostic="skeleton binding changed";return invalid
	if bind_index>=skin_resource.get_bind_count() or skin_resource.get_bind_pose(bind_index)!=inverse_bind:invalid.diagnostic="skin binding changed; prepare again";return invalid
	# Exactly the same skin space as asset_bounds.gd: skeleton-world * posed
	# bone * inverse-bind. The mesh node transform must not be applied twice.
	var transform: Transform3D=skeleton.global_transform*skeleton.get_bone_global_pose(bone)*inverse_bind
	if space!=null:
		if not is_instance_valid(space) or not space.is_inside_tree() or absf(space.global_basis.determinant())<.0000001:invalid.diagnostic="invalid output space";return invalid
		transform=space.global_transform.affine_inverse()*transform
	var points=PackedVector3Array()
	if include_blade_vertices:
		for point in blade_vertices:points.append(transform*point)
	return {"valid":true,"diagnostic":diagnostic,"hilt":transform*local_hilt,"tip":transform*local_tip,"blade_points":points,"surface":surface_index,"bone":bone,"bind":bind_index}

static func _principal_axis(points: PackedVector3Array) -> Vector3:
	if points.size()<2:return Vector3.ZERO
	var center=Vector3.ZERO
	for point in points:center+=point
	center/=points.size()
	# Covariance power iteration is independent of coordinate axis and model yaw.
	var xx=0.0;var xy=0.0;var xz=0.0;var yy=0.0;var yz=0.0;var zz=0.0
	for point in points:
		var p=point-center;xx+=p.x*p.x;xy+=p.x*p.y;xz+=p.x*p.z;yy+=p.y*p.y;yz+=p.y*p.z;zz+=p.z*p.z
	var axis=Vector3.RIGHT if xx>=yy and xx>=zz else (Vector3.UP if yy>=zz else Vector3.BACK)
	for iteration in range(20):
		var next=Vector3(xx*axis.x+xy*axis.y+xz*axis.z,xy*axis.x+yy*axis.y+yz*axis.z,xz*axis.x+yz*axis.y+zz*axis.z)
		if next.length_squared()<.000000000001:return Vector3.ZERO
		axis=next.normalized()
	return axis
