extends RefCounted
## Rest-pose bounds, including skin inverse binds. A mesh AABB alone can be
## misleading when imported armatures and inverse binds use different scales.

static func _transforms(node: Node, parent: Transform3D, result: Dictionary) -> void:
	var transform := parent
	if node is Node3D:
		transform = parent * node.transform
	result[node] = transform
	for child in node.get_children():
		_transforms(child, transform, result)

static func measure(root: Node, parent: Transform3D = Transform3D.IDENTITY, posed: bool = false, mesh_filter: String = "") -> Dictionary:
	var transforms := {}
	_transforms(root, parent, transforms)
	var points := PackedVector3Array()
	var errors := PackedStringArray()
	var skinned_vertices := 0
	for node in transforms:
		if not node is MeshInstance3D or node.mesh == null:
			continue
		if posed and not node.is_visible_in_tree():
			continue
		if not mesh_filter.is_empty() and not str(node.name).begins_with(mesh_filter):
			continue
		var transform: Transform3D = transforms[node]
		if node.skin == null:
			var box: AABB = node.get_aabb()
			for i in range(8):
				points.append(transform * box.get_endpoint(i))
			continue
		var skeleton := node.get_node_or_null(node.skeleton) as Skeleton3D
		if skeleton == null or not transforms.has(skeleton):
			errors.append("Skinned mesh has no resolvable Skeleton3D")
			continue
		var binds: Array[Transform3D] = []
		for i in range(node.skin.get_bind_count()):
			var bone: int = node.skin.get_bind_bone(i)
			var name: StringName = node.skin.get_bind_name(i)
			if not name.is_empty():
				bone = skeleton.find_bone(name)
			if bone < 0 or bone >= skeleton.get_bone_count():
				errors.append("Skin bind refers to an invalid bone")
				break
			var bone_transform := skeleton.get_bone_global_pose(bone) if posed else skeleton.get_bone_global_rest(bone)
			binds.append(transforms[skeleton] * bone_transform * node.skin.get_bind_pose(i))
		if binds.size() != node.skin.get_bind_count():
			continue
		for surface in range(node.mesh.get_surface_count()):
			var arrays: Array = node.mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var bones = arrays[Mesh.ARRAY_BONES]
			var weights = arrays[Mesh.ARRAY_WEIGHTS]
			if bones == null or weights == null or vertices.is_empty():
				errors.append("Skinned mesh has no vertex influences")
				continue
			var influences: int = bones.size() / vertices.size()
			if influences not in [4, 8] or weights.size() != bones.size():
				errors.append("Unexpected skin influence layout")
				continue
			for vertex in range(vertices.size()):
				var position := Vector3.ZERO
				var total := 0.0
				for influence in range(influences):
					var index := vertex * influences + influence
					var weight: float = weights[index]
					if weight <= 0.0:
						continue
					var bind: int = bones[index]
					if bind < 0 or bind >= binds.size():
						errors.append("Vertex refers to an invalid skin bind")
						continue
					position += (binds[bind] * vertices[vertex]) * weight
					total += weight
				if total <= 0.0:
					errors.append("Vertex has no positive skin weights")
					continue
				points.append(position / total)
				skinned_vertices += 1
	var bounds := AABB()
	if not points.is_empty():
		bounds = AABB(points[0], Vector3.ZERO)
		for point in points:
			bounds = bounds.expand(point)
	return {"bounds": bounds, "skinned_vertices": skinned_vertices, "errors": errors}
