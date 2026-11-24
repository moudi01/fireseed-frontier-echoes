extends RefCounted
## Model-owned palm anchors derived once from the imported skin's hand regions.
static func prepare(model: Node):
	var grips={};var meshes=model.find_children("CharacterBody*","MeshInstance3D",true,false)
	for side in ["Left","Right"]:
		var total=Vector3.ZERO;var count=0
		for mesh in meshes:
			if mesh.skin==null:continue
			var skeleton=mesh.get_node(mesh.skeleton);var bone=skeleton.find_bone(side+"Hand")
			for surface in range(mesh.mesh.get_surface_count()):
				var a=mesh.mesh.surface_get_arrays(surface);var vertices=a[Mesh.ARRAY_VERTEX];var bones=a[Mesh.ARRAY_BONES];var weights=a[Mesh.ARRAY_WEIGHTS]
				if bones==null or weights==null:continue
				var influences=bones.size()/vertices.size()
				for i in range(vertices.size()):
					for j in range(influences):
						var k=i*influences+j;var bind=int(bones[k]);var name=mesh.skin.get_bind_name(bind);var mapped=skeleton.find_bone(name) if not name.is_empty() else mesh.skin.get_bind_bone(bind)
						if mapped==bone and weights[k]>.7:
							total+=mesh.skin.get_bind_pose(bind)*vertices[i];count+=1;break
		if count>0:grips[side]=total/count
	model.set_meta("palm_grips",grips)
	if grips.size()!=2:
		var issues=model.get_meta("action_issues",[]).duplicate();issues.append("缺少手掌握持区域");model.set_meta("action_issues",issues)
static func palm(model: Node,side: String) -> Vector3:
	var skeleton=model.find_children("*","Skeleton3D",true,false)[0];var bone=skeleton.find_bone(side+"Hand")
	return skeleton.global_transform*skeleton.get_bone_global_pose(bone)*model.get_meta("palm_grips",{}).get(side,Vector3.ZERO)
