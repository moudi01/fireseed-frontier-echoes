extends RefCounted
## 042 experimental initialization-only pose bake; only contracted shield model.
## No asset writes or per-frame IK. Each Animation and AnimationLibrary owned by model.
const SKILL=preload("res://core/skill_presentation.gd")
const RIGHT=["RightShoulder","RightArm","RightForeArm","RightHand"]
static func animation_fingerprint(animation:Animation)->String:
 var bits=[str(animation.length),str(animation.loop_mode)]
 for i in animation.get_track_count():
  bits.append(str(animation.track_get_type(i))+":"+str(animation.track_get_path(i))+":"+str(animation.track_get_interpolation_type(i)))
  for k in animation.track_get_key_count(i):bits.append(str(animation.track_get_key_time(i,k))+":"+str(animation.track_get_key_value(i,k))+":"+str(animation.track_get_key_transition(i,k)))
 return "|".join(bits).sha256_text()
static func library_fingerprint(library:AnimationLibrary)->String:
 var names=library.get_animation_list();names.sort();var bits=[]
 for name in names:bits.append(str(name)+":"+animation_fingerprint(library.get_animation(name)))
 return "|".join(bits).sha256_text()
static func fit(model:Node)->Dictionary:
 if not is_instance_valid(model):return {"valid":false,"diagnostic":"model missing"}
 if model.has_meta("shield_attack_fit_042"):
  var old=model.get_meta("shield_attack_fit_042").duplicate(true);old["idempotent"]=true;return old
 if model.get_meta("action_profile","")!="shield" or not model.get_meta("action_issues",["unchecked"]).is_empty():return {"valid":false,"diagnostic":"requires accepted shield contract"}
 var p=SKILL.player(model);var found=model.find_children("*","Skeleton3D",true,false)
 if p==null or found.size()!=1 or not p.has_animation("ShieldAttack") or not p.has_animation("Right_Hand_Sword_Slash"):return {"valid":false,"diagnostic":"required animations missing"}
 var sk:Skeleton3D=found[0];var ids=[];var track_paths={}
 for name in RIGHT:ids.append(sk.find_bone(name))
 if ids.has(-1):return {"valid":false,"diagnostic":"required chain missing"}
 var original_library=p.get_animation_library("");var library_hash_before=library_fingerprint(original_library)
 var original=p.get_animation("ShieldAttack");var original_hash_before=animation_fingerprint(original);var slash=p.get_animation("Right_Hand_Sword_Slash");var length=original.length
 for i in original.get_track_count():
  if original.track_get_type(i)==Animation.TYPE_ROTATION_3D:
   var path=original.track_get_path(i)
   for name in RIGHT:
    if str(path).ends_with(":"+name):track_paths[name]=path
 if track_paths.size()!=4:return {"valid":false,"diagnostic":"four right rotation tracks required"}
 var samples=[];var max_residual=0.0;var max_nonright_error=0.0;var max_local_jump=0.0;var previous=[];var reach_clamps=0;var max_step_phase=0.0;var max_step_bone="";var max_basis_error=0.0
 for i in range(121):
  var phase=float(i)/120;var weight=smoothstep(.12,.30,phase)*(1.0-smoothstep(.62,.88,phase))
  p.play("Right_Hand_Sword_Slash");p.seek(phase*slash.length,true);p.advance(0);p.pause()
  var source=[]
  for id in ids:source.append(sk.get_bone_global_pose(id))
  p.play("ShieldAttack");p.seek(phase*length,true);p.advance(0);p.pause()
  var untouched=[]
  for bone in sk.get_bone_count():untouched.append(sk.get_bone_pose(bone))
  var guard_hand=sk.get_bone_global_pose(ids[3]);var target=guard_hand.origin.lerp(source[3].origin,weight)
  var target_basis=Basis(guard_hand.basis.get_rotation_quaternion().slerp(source[3].basis.get_rotation_quaternion(),weight))
  var shoulder=sk.get_bone_global_pose(ids[0]);shoulder.basis=Basis(shoulder.basis.get_rotation_quaternion().slerp(source[0].basis.get_rotation_quaternion(),weight));sk.set_bone_global_pose(ids[0],shoulder)
  var upper=sk.get_bone_global_pose(ids[1]);var elbow=sk.get_bone_global_pose(ids[2]);var wrist=sk.get_bone_global_pose(ids[3])
  var a=upper.origin;var b=elbow.origin;var c=wrist.origin;var l1=a.distance_to(b);var l2=b.distance_to(c);var delta=target-a
  if delta.length()<.0001:return {"valid":false,"diagnostic":"degenerate hand target"}
  var axis=delta.normalized();var distance=clampf(delta.length(),absf(l1-l2)+.0001,l1+l2-.0001)
  var soft_span=8.0*weight
  var soft_start=l1+l2-soft_span
  if soft_span>.0001 and delta.length()>soft_start:distance=soft_start+soft_span*tanh((delta.length()-soft_start)/soft_span)
  if absf(distance-delta.length())>.001:reach_clamps+=1
  var along=(l1*l1-l2*l2+distance*distance)/(2*distance);var height=sqrt(maxf(0,l1*l1-along*along))
  var pole=b.lerp(source[2].origin,weight)-a;pole-=axis*pole.dot(axis)
  if pole.length_squared()<.000001:pole=(b-a)-axis*(b-a).dot(axis)
  if pole.length_squared()<.000001:return {"valid":false,"diagnostic":"degenerate elbow pole"}
  var desired_elbow=a+axis*along+pole.normalized()*height;var desired_hand=a+axis*distance
  # Preserve source arm twist, then rotate only enough to meet exact chain direction.
  upper.basis=Basis(upper.basis.get_rotation_quaternion().slerp(source[1].basis.get_rotation_quaternion(),weight));sk.set_bone_global_pose(ids[1],upper)
  elbow=sk.get_bone_global_pose(ids[2]);upper=sk.get_bone_global_pose(ids[1]);upper.basis=Basis(Quaternion((elbow.origin-upper.origin).normalized(),(desired_elbow-upper.origin).normalized()))*upper.basis;sk.set_bone_global_pose(ids[1],upper)
  elbow=sk.get_bone_global_pose(ids[2]);elbow.basis=Basis(elbow.basis.get_rotation_quaternion().slerp(source[2].basis.get_rotation_quaternion(),weight));sk.set_bone_global_pose(ids[2],elbow)
  elbow=sk.get_bone_global_pose(ids[2]);wrist=sk.get_bone_global_pose(ids[3]);elbow.basis=Basis(Quaternion((wrist.origin-elbow.origin).normalized(),(desired_hand-elbow.origin).normalized()))*elbow.basis;sk.set_bone_global_pose(ids[2],elbow)
  wrist=sk.get_bone_global_pose(ids[3]);wrist.basis=target_basis;sk.set_bone_global_pose(ids[3],wrist)
  max_residual=maxf(max_residual,wrist.origin.distance_to(target))
  var rotations=[]
  for id in ids:rotations.append(sk.get_bone_pose_rotation(id).normalized())
  if not previous.is_empty():
   for j in rotations.size():
    var jump=previous[j].angle_to(rotations[j])
    if jump>max_local_jump:max_local_jump=jump;max_step_phase=phase;max_step_bone=RIGHT[j]
  previous=rotations
  for bone in sk.get_bone_count():
   if bone in ids:continue
   var pose=sk.get_bone_pose(bone);var old=untouched[bone]
   max_nonright_error=maxf(max_nonright_error,pose.origin.distance_to(old.origin))
   for col in range(3):max_basis_error=maxf(max_basis_error,pose.basis[col].distance_to(old.basis[col]))
  samples.append({"time":phase*length,"rotations":rotations})
 var fitted=original.duplicate(true)
 for i in range(fitted.get_track_count()-1,-1,-1):
  if fitted.track_get_type(i)==Animation.TYPE_ROTATION_3D and track_paths.values().has(fitted.track_get_path(i)):fitted.remove_track(i)
 for j in RIGHT.size():
  var track=fitted.add_track(Animation.TYPE_ROTATION_3D);fitted.track_set_path(track,track_paths[RIGHT[j]]);fitted.track_set_interpolation_type(track,Animation.INTERPOLATION_LINEAR)
  for row in samples:fitted.rotation_track_insert_key(track,row.time,row.rotations[j])
 var library=p.get_animation_library("").duplicate();library.remove_animation("ShieldAttack");library.add_animation("ShieldAttack",fitted)
 p.stop();p.remove_animation_library("");p.add_animation_library("",library)
 var result={"valid":true,"diagnostic":"121 initialization-only two-bone right-arm samples; preserve non-right tracks and bone positions; source twist/pole from owned Slash","samples":samples.size(),"max_target_residual_skeleton_units":max_residual,"reach_clamped_samples":reach_clamps,"max_nonright_local_error":max_nonright_error,"max_right_local_step_radians":max_local_jump,"max_right_step_phase":max_step_phase,"max_right_step_bone":max_step_bone,"max_nonright_basis_column_error":max_basis_error,"original_animation_unchanged":original!=fitted,"library_owned":library!=original_library,"source_animation_sha256_before":original_hash_before,"source_animation_sha256_after":animation_fingerprint(original),"source_library_sha256_before":library_hash_before,"source_library_sha256_after":library_fingerprint(original_library),"soft_reach_margin_skeleton_units":8.0,"source_target_note":"Unreachable source hand positions projected to reachable chain; soft extension avoids straight-elbow popping. Residual is reported, not zeroed."}
 model.set_meta("shield_attack_fit_042",result);return result
