extends "res://admin_actor.gd"

var _muzzle_node: Node3D
var _muzzle_rig: Skeleton3D
var _muzzle_bone := -1
var _bolt_release_time := -1.0


func assemble_guard(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	if not super.assemble_guard(scene, travel_library, profile):
		return false
	_bolt_release_time = float(profile.get("bolt_release_time", -1.0))
	var socket: String = profile.get("muzzle_socket", "")
	if socket.is_empty():
		return true
	_muzzle_node = find_child(socket, true, false) as Node3D
	if _muzzle_node == null:
		for rig: Skeleton3D in find_children("*", "Skeleton3D", true, false):
			var bone := rig.find_bone(socket)
			if bone >= 0:
				_muzzle_rig = rig
				_muzzle_bone = bone
				break
	return true


func bolt_origin() -> Vector3:
	if is_instance_valid(_muzzle_node):
		return _muzzle_node.global_position
	if is_instance_valid(_muzzle_rig) and _muzzle_bone >= 0:
		_muzzle_rig.force_update_all_bone_transforms()
		return _muzzle_rig.to_global(_muzzle_rig.get_bone_global_pose(_muzzle_bone).origin)
	return Vector3.INF


func bolt_delay(default_delay: float) -> float:
	return _bolt_release_time / CAST_SPEED if _bolt_release_time >= 0.0 else default_delay
