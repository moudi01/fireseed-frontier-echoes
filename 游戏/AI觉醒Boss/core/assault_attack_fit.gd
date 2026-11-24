extends RefCounted
## Initialization-only experimental fit for the accepted infantry contract.
## Rotation tracks only. Unit offsets refer to the contracted skeleton units.
const SKILL=preload("res://core/skill_presentation.gd")
const STAMP=preload("res://core/shield_attack_fit.gd")
const MELEE=preload("res://core/melee_contact.gd")
const RIGHT=["RightShoulder","RightArm","RightForeArm","RightHand"]
const CLIPS=["Right_Hand_Sword_Slash","ChargeRelease"]
static func fit(model:Node)->Dictionary:
 if not is_instance_valid(model):return {"valid":false,"diagnostic":"missing model"}
 if model.has_meta("assault_attack_fit_043"):
  var old=model.get_meta("assault_attack_fit_043").duplicate(true);old["idempotent"]=true;return old
 if model.get_meta("action_profile","")!="infantry" or not model.get_meta("action_issues",["unchecked"]).is_empty():return {"valid":false,"diagnostic":"accepted infantry contract required"}
 var p=SKILL.player(model);var found=model.find_children("*","Skeleton3D",true,false)
 if p==null or found.size()!=1:return {"valid":false,"diagnostic":"player/skeleton missing"}
 var sk:Skeleton3D=found[0];var ids=[]
 for name in RIGHT:ids.append(sk.find_bone(name))
 if ids.has(-1):return {"valid":false,"diagnostic":"right chain missing"}
 var probe=MELEE.new();var prep=probe.prepare(model)
 if not prep.valid:return prep
 var initial_poses=[]
 for bone in sk.get_bone_count():initial_poses.append(sk.get_bone_pose(bone))
 var original_library=p.get_animation_library("");var source_hash=STAMP.library_fingerprint(original_library);var library=original_library.duplicate();var clips={};var baked_samples={}
 for clip in CLIPS:
  if not p.has_animation(clip):return {"valid":false,"diagnostic":"missing "+clip}
  var original=p.get_animation(clip);var original_hash=STAMP.animation_fingerprint(original);var track_paths={};var samples=[];var max_residual=0.0;var clamps=0;var max_delta=0.0;var previous_pole=Vector3.ZERO
  for i in original.get_track_count():
   if original.track_get_type(i)!=Animation.TYPE_ROTATION_3D:continue
   var path=original.track_get_path(i)
   for name in RIGHT:
    if str(path).ends_with(":"+name):track_paths[name]=path
  if track_paths.size()!=4:return {"valid":false,"diagnostic":"four right tracks required"}
  for i in range(121):
   var phase=float(i)/120
   var weight=smoothstep(.34,.48,phase)*(1.0-smoothstep(.58,.86,phase)) if clip==CLIPS[0] else smoothstep(.035,.23,phase)*(1.0-smoothstep(.72,.98,phase))
   # set_bone_global_pose can decompose a nonuniform parent into scale/shear.
   # Reset all source local poses before every sample; never accumulate it.
   for bone in sk.get_bone_count():sk.set_bone_pose(bone,initial_poses[bone])
   p.play(clip);p.seek(phase*original.length,true);p.advance(0);p.pause()
   var original_rotations=[]
   for id in ids:original_rotations.append(sk.get_bone_pose_rotation(id))
   if weight<.00000001:
    samples.append({"time":phase*original.length,"rotations":original_rotations,"original_rotations":original_rotations});continue
   var upper=sk.get_bone_global_pose(ids[1]);var elbow=sk.get_bone_global_pose(ids[2]);var wrist=sk.get_bone_global_pose(ids[3])
   var source_wrist=wrist
   var forward=18.0 if clip==CLIPS[0] else 22.0
   var shift=Vector3((13.0-wrist.origin.x)*.42,0,forward)*weight
   var target=wrist.origin+shift;var a=upper.origin;var b=elbow.origin;var c=wrist.origin
   var l1=a.distance_to(b);var l2=b.distance_to(c);var delta=target-a;var axis=delta.normalized()
   var soft_span=5.0*weight;var soft_start=l1+l2-soft_span
   var distance=clampf(delta.length(),absf(l1-l2)+.0001,l1+l2-.0001)
   if soft_span>.0001 and delta.length()>soft_start:distance=soft_start+soft_span*tanh((delta.length()-soft_start)/soft_span)
   if absf(distance-delta.length())>.001:clamps+=1
   var along=(l1*l1-l2*l2+distance*distance)/(2*distance);var height=sqrt(maxf(0,l1*l1-along*along))
   var pole=b-a;pole-=axis*pole.dot(axis)
   if pole.length_squared()<.000001:return {"valid":false,"diagnostic":"degenerate elbow pole"}
   pole=pole.normalized()
   if previous_pole.length_squared()>.01:
    var carried=previous_pole-axis*previous_pole.dot(axis)
    if carried.length_squared()>.000001:pole=carried.normalized().slerp(pole,.08).normalized()
   previous_pole=pole
   var desired_elbow=a+axis*along+pole.normalized()*height;var desired_hand=a+axis*distance
   upper.basis=Basis(Quaternion((b-a).normalized(),(desired_elbow-a).normalized()))*upper.basis;sk.set_bone_global_pose(ids[1],upper)
   elbow=sk.get_bone_global_pose(ids[2]);wrist=sk.get_bone_global_pose(ids[3])
   elbow.basis=Basis(Quaternion((wrist.origin-elbow.origin).normalized(),(desired_hand-elbow.origin).normalized()))*elbow.basis;sk.set_bone_global_pose(ids[2],elbow)
   wrist=sk.get_bone_global_pose(ids[3]);wrist.basis=source_wrist.basis
   var tip=wrist*probe.inverse_bind*probe.local_tip
   var sword_axis=(tip-wrist.origin).normalized();var desired_axis=(Vector3(13.0,wrist.origin.y,120.0)-wrist.origin).normalized()
   var correction=Quaternion(sword_axis,desired_axis);var angle=Quaternion.IDENTITY.angle_to(correction)
   var cap=.25 if clip==CLIPS[0] else .40
   var amount=minf((.35 if clip==CLIPS[0] else .55)*weight,cap*weight/maxf(angle,.0001))
   wrist.basis=Basis(Quaternion.IDENTITY.slerp(correction,amount))*wrist.basis;sk.set_bone_global_pose(ids[3],wrist)
   max_residual=maxf(max_residual,wrist.origin.distance_to(target))
   var rotations=[]
   for j in ids.size():
    var rotation=sk.get_bone_pose_rotation(ids[j]).normalized();rotations.append(rotation);max_delta=maxf(max_delta,original_rotations[j].angle_to(rotation))
   samples.append({"time":phase*original.length,"rotations":rotations,"original_rotations":original_rotations,"target":target})
  # Smooth the baked active right-chain keys, including the fast imported wrist
  # swivel. Endpoint keys remain exactly the imported pose, no runtime solver.
  for _pass_index in range(2):
   var filtered=samples.duplicate(true)
   for i in range(1,samples.size()-1):
    var phase=float(i)/120
    var weight=smoothstep(.34,.48,phase)*(1.0-smoothstep(.58,.86,phase)) if clip==CLIPS[0] else smoothstep(.035,.23,phase)*(1.0-smoothstep(.72,.98,phase))
    for j in RIGHT.size():
     var neighbors=samples[i-1].rotations[j].slerp(samples[i+1].rotations[j],.5)
     filtered[i].rotations[j]=samples[i].rotations[j].slerp(neighbors,.45*weight).normalized()
   samples=filtered
  var fitted=original.duplicate(true)
  for i in range(fitted.get_track_count()-1,-1,-1):
   if fitted.track_get_type(i)==Animation.TYPE_ROTATION_3D and track_paths.values().has(fitted.track_get_path(i)):fitted.remove_track(i)
  for j in RIGHT.size():
   var track=fitted.add_track(Animation.TYPE_ROTATION_3D);fitted.track_set_path(track,track_paths[RIGHT[j]]);fitted.track_set_interpolation_type(track,Animation.INTERPOLATION_LINEAR)
   for row in samples:fitted.rotation_track_insert_key(track,row.time,row.rotations[j])
  library.remove_animation(clip);library.add_animation(clip,fitted)
  baked_samples[clip]=samples
  clips[clip]={"samples":samples.size(),"source_sha256_before":original_hash,"source_sha256_after":STAMP.animation_fingerprint(original),"fitted_sha256":STAMP.animation_fingerprint(fitted),"pre_smoothing_target_residual_skeleton_units":max_residual,"reach_clamped_samples":clamps,"pre_smoothing_right_rotation_delta_rad":max_delta}
 p.stop();p.remove_animation_library("");p.add_animation_library("",library)
 for clip in CLIPS:
  var max_residual=0.0;var max_delta=0.0
  for row in baked_samples[clip]:
   for bone in sk.get_bone_count():sk.set_bone_pose(bone,initial_poses[bone])
   p.play(clip);p.seek(row.time,true);p.advance(0);p.pause()
   if row.has("target"):max_residual=maxf(max_residual,sk.get_bone_global_pose(ids[3]).origin.distance_to(row.target))
   for j in ids.size():max_delta=maxf(max_delta,row.original_rotations[j].angle_to(sk.get_bone_pose_rotation(ids[j])))
  clips[clip]["max_target_residual_skeleton_units"]=max_residual;clips[clip]["max_right_rotation_delta_rad"]=max_delta
 p.stop()
 for bone in sk.get_bone_count():sk.set_bone_pose(bone,initial_poses[bone])
 var result={"valid":true,"clips":clips,"source_library_sha256_before":source_hash,"source_library_sha256_after":STAMP.library_fingerprint(original_library),"library_owned":library!=original_library,"forward_target_skeleton_units":{"Right_Hand_Sword_Slash":18.0,"ChargeRelease":22.0},"soft_reach_skeleton_units":5.0,"max_wrist_correction_rad":{"Right_Hand_Sword_Slash":.25,"ChargeRelease":.40},"active_key_smoothing_passes":2,"diagnostic":"121 samples/clip; initialization-only right rotation bake; finite forward reach, midline and bounded wrist correction; unreachable targets projected and final-baked residual reported; source local scale/pose restored each sample and on return"}
 model.set_meta("assault_attack_fit_043",result);return result
