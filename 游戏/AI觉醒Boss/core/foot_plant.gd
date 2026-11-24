extends SkeletonModifier3D
## Cosmetic, bounded stance correction after animation. Flat board only, no rule authority.
const CONTACTS=preload("res://data/foot_contacts.json")
const MAX_SHIFT=.10
const RELEASE_DISTANCE=.18
var figure={}
var chains={}
var anchors={}
var profile={}
var enabled=true
var last_clip=""
var latest=[]
var callbacks=0
func configure(f:Dictionary):
	figure=f;var skeleton=get_skeleton();var id=str(f.model.get_meta("action_profile",""))
	profile=CONTACTS.data.models.get(id,{})
	if profile.get("scene_path","")!=f.model.scene_file_path or not f.model.get_meta("action_issues",["unchecked"]).is_empty():profile={}
	for side in ["Left","Right"]:
		var names=[side+"UpLeg",side+"Leg",side+"Foot",side+"ToeBase"];var bones=[]
		for name in names:bones.append(skeleton.find_bone(name))
		if bones.all(func(i):return i>=0) and skeleton.get_bone_parent(bones[1])==bones[0] and skeleton.get_bone_parent(bones[2])==bones[1] and skeleton.get_bone_parent(bones[3])==bones[2]:chains[side]=bones
	if chains.size()!=2:profile={}
func _process_modification_with_delta(_delta:float):
	callbacks+=1;latest=[]
	if figure.is_empty():return
	var clip=str(figure.clip)
	if clip!=last_clip:anchors.clear();last_clip=clip
	if not enabled or not profile.get("clips",{}).has(clip) or float(figure.motion)>=1:
		anchors.clear();return
	var skeleton=get_skeleton();var scale_y=figure.node.global_basis.get_scale().y
	for side in ["Left","Right"]:
		var bones=chains[side];var toe=skeleton.global_transform*skeleton.get_bone_global_pose(bones[3]).origin
		var height=(toe.y-figure.node.global_position.y)/scale_y;var floor_y=float(profile.clips[clip][side.to_lower()+"_floor"])
		var state=anchors.get(side,{"held":false,"point":toe})
		if height>floor_y+.04:state.held=false
		elif height<=floor_y+.018 and not state.held:state.held=true;state.point=toe
		anchors[side]=state
		if not state.held:continue
		var offset=Vector3(state.point.x-toe.x,0,state.point.z-toe.z);var distance=offset.length()/scale_y
		if distance>=RELEASE_DISTANCE:state.held=false;continue
		var strength=(1.0-smoothstep(floor_y+.018,floor_y+.04,height))*(1.0-smoothstep(MAX_SHIFT,RELEASE_DISTANCE,distance))
		var correction=offset.limit_length(MAX_SHIFT*scale_y)*strength
		var ankle_world=skeleton.global_transform*skeleton.get_bone_global_pose(bones[2]).origin
		var target=skeleton.global_transform.affine_inverse()*(ankle_world+correction)
		solve(skeleton,bones,target)
		var corrected=skeleton.global_transform*skeleton.get_bone_global_pose(bones[3]).origin
		latest.append({"side":side,"before":toe,"after":corrected,"anchor":state.point,"correction":correction.length(),"height":height,"strength":strength})
static func solve(skeleton:Skeleton3D,bones:Array,target:Vector3):
	var upper=skeleton.get_bone_global_pose(bones[0]);var knee=skeleton.get_bone_global_pose(bones[1]);var foot=skeleton.get_bone_global_pose(bones[2])
	var a=upper.origin;var b=knee.origin;var c=foot.origin;var l1=a.distance_to(b);var l2=b.distance_to(c);var axis=(target-a).normalized()
	if not target.is_finite() or l1<.0001 or l2<.0001 or a.distance_to(target)<.0001:return
	var distance=clampf(a.distance_to(target),absf(l1-l2)+.0001,l1+l2-.0001)
	var along=(l1*l1-l2*l2+distance*distance)/(2.0*distance);var height=sqrt(maxf(0,l1*l1-along*along))
	var bend=(b-a)-axis*(b-a).dot(axis)
	if bend.length_squared()<.000001:bend=upper.basis.z-axis*upper.basis.z.dot(axis)
	var desired_knee=a+axis*along+bend.normalized()*height
	upper.basis=Basis(Quaternion((b-a).normalized(),(desired_knee-a).normalized()))*upper.basis;skeleton.set_bone_global_pose(bones[0],upper)
	knee=skeleton.get_bone_global_pose(bones[1]);var current_foot=skeleton.get_bone_global_pose(bones[2]);var desired_foot=a+axis*distance
	knee.basis=Basis(Quaternion((current_foot.origin-knee.origin).normalized(),(desired_foot-knee.origin).normalized()))*knee.basis;skeleton.set_bone_global_pose(bones[1],knee)
	current_foot=skeleton.get_bone_global_pose(bones[2]);current_foot.basis=foot.basis;skeleton.set_bone_global_pose(bones[2],current_foot)
