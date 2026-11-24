extends RefCounted
## AD-03: reversible, UV-anchored material separation for the three verified bodies.
## The source atlas, geometry, skin, skeleton and animations remain untouched.
## This contract covers the current gloved characters; it does not claim bare-hand masks.
const PATHS = {
	"shield":"res://assets/shield_armor036.glb",
	"infantry":"res://assets/infantry_armor036.glb",
	"archer":"res://assets/archer_armor036.glb"
}
const PALETTES = {"shield":Color("729b91"),"infantry":Color("ac6651"),"archer":Color("748c59")}
const MASK_SIZE = 256
const BODY_PARTS = ["CharacterBody_Refined", "Armor_Shoulders"]
static var material_cache: Dictionary = {}
static var shared_shader: Shader

static func prepare(model: Node) -> Dictionary:
	var profile = str(model.get_meta("action_profile", ""))
	var report = {"valid":false,"applied":0,"profile":profile,"enabled":false,"materials":[],"issues":[]}
	if not PATHS.has(profile) or model.scene_file_path != PATHS.get(profile, ""):
		report.issues.append("未登记的身体资产")
	elif not model.has_meta("action_issues") or not model.get_meta("action_issues").is_empty():
		report.issues.append("动作/骨架契约未通过")
	else:
		var skeletons = model.find_children("*", "Skeleton3D", true, false)
		var expected: Array = preload("res://core/skill_presentation.gd").profiles()[profile].rig
		if skeletons.size() != 1 or skeletons[0].get_bone_count() != expected.size():
			report.issues.append("骨架数量或骨骼数量已变化")
		else:
			for index in range(expected.size()):
				if str(skeletons[0].get_bone_name(index)) != expected[index].name or skeletons[0].get_bone_parent(index) != int(expected[index].parent):
					report.issues.append("骨骼层级已变化")
					break
				var rest: Transform3D = skeletons[0].get_bone_rest(index)
				var values = []
				for vector in [rest.basis.x, rest.basis.y, rest.basis.z, rest.origin]:
					values.append_array([vector.x, vector.y, vector.z])
				for component in range(12):
					if absf(float(values[component]) - float(expected[index].rest[component])) > .001:
						report.issues.append("绑定姿态已变化")
						break
				if not report.issues.is_empty():
					break
	if not report.issues.is_empty():
		return report
	var slots = []
	var surfaces = []
	var layout = []
	var part_counts = {}
	var atlas: Texture2D
	for item in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = item
		if mesh_node.mesh == null:
			continue
		for surface in range(mesh_node.mesh.get_surface_count()):
			var source = mesh_node.mesh.surface_get_material(surface)
			if not source is StandardMaterial3D or not str(source.resource_name).begins_with("Material_0"):
				continue
			if str(mesh_node.name) not in BODY_PARTS:
				report.issues.append("未登记的同名身体材质网格：" + str(mesh_node.name))
				continue
			if mesh_node.skin == null or source.albedo_texture == null:
				report.issues.append("身体表面缺少蒙皮或原图：" + str(mesh_node.name))
				continue
			var arrays = mesh_node.mesh.surface_get_arrays(surface)
			var issue = surface_issue(arrays)
			if not issue.is_empty():
				report.issues.append(str(mesh_node.name) + "：" + issue)
				continue
			if atlas != null and atlas != source.albedo_texture:
				report.issues.append("已登记身体与肩甲不再共用原图集")
				continue
			atlas = source.albedo_texture
			slots.append({"mesh":mesh_node,"surface":surface,"source":source})
			surfaces.append(arrays)
			part_counts[str(mesh_node.name)] = int(part_counts.get(str(mesh_node.name), 0)) + 1
			# Content/layout identity prevents a different UV mesh reusing an older mask.
			layout.append([str(model.get_path_to(mesh_node)),surface,arrays[Mesh.ARRAY_VERTEX],arrays[Mesh.ARRAY_TEX_UV],arrays[Mesh.ARRAY_INDEX]])
	for part in BODY_PARTS:
		if int(part_counts.get(part, 0)) != 1:
			report.issues.append("需要唯一已登记图集表面：" + part)
	if not report.issues.is_empty():
		return report
	var layout_key = str(layout.hash())
	if model.has_meta("character_surface_report"):
		var previous: Dictionary = model.get_meta("character_surface_report")
		if previous.get("layout_key", "") == layout_key:
			return previous.duplicate(true)
		report.issues.append("已处理模型的身体UV布局已变化")
		return report
	var key = profile + ":" + str(atlas.get_instance_id()) + ":" + layout_key
	if not material_cache.has(key):
		var mask = region_mask(surfaces)
		if mask == null:
			report.issues.append("身体与肩甲UV未产生有效数据遮罩")
			return report
		var material = ShaderMaterial.new()
		material.shader = shader()
		material.resource_name = "AD03_Body_" + profile
		material.set_shader_parameter("body_tex", atlas)
		material.set_shader_parameter("region_tex", mask)
		material.set_shader_parameter("cloth_color", PALETTES[profile])
		material.set_shader_parameter("inspect_channels", false)
		material.set_meta("art_family", "body_separated")
		material.set_meta("surface_profile", profile)
		material.set_meta("layout_key", layout_key)
		material_cache[key] = material
	var originals = []
	for slot in slots:
		var styled: ShaderMaterial = material_cache[key]
		originals.append({"mesh":model.get_path_to(slot.mesh),"surface":slot.surface,"original":slot.mesh.get_surface_override_material(slot.surface),"styled":styled})
		slot.mesh.set_surface_override_material(slot.surface, styled)
		report.materials.append({"mesh":str(slot.mesh.name),"surface":slot.surface,"family":"body_separated"})
	report.valid = true
	report.applied = originals.size()
	report.enabled = true
	report.layout_key = layout_key
	model.set_meta("character_surface_originals", originals)
	model.set_meta("character_surface_enabled", true)
	model.set_meta("character_surface_report", report)
	return report.duplicate(true)

static func set_enabled(model: Node, value: bool) -> void:
	if not model.has_meta("character_surface_originals"):
		return
	for record in model.get_meta("character_surface_originals"):
		var mesh_node = model.get_node_or_null(record.mesh)
		if mesh_node is MeshInstance3D:
			mesh_node.set_surface_override_material(record.surface, record.styled if value else record.original)
	model.set_meta("character_surface_enabled", value)
	var report: Dictionary = model.get_meta("character_surface_report").duplicate(true)
	report.enabled = value
	model.set_meta("character_surface_report", report)

static func classify_color(color: Color) -> String:
	# Diagnostic labels only: this CPU helper does NOT prove the fragment masks.
	# The real GPU probe uses inspect_channels and the UV anatomical guards below.
	var spread = maxf(color.r, maxf(color.g, color.b)) - minf(color.r, minf(color.g, color.b))
	if color.r > color.g * 1.08 and color.g > color.b * 1.12 and color.r > .55 and color.g > .30 and color.b > .20 and color.g - color.b < (color.r - color.g) * 1.45:
		return "skin"
	if color.g > color.r * 1.12 and color.g > color.b * 1.10:
		return "cloth"
	if color.r > color.b * 1.45 and color.g > color.b * 1.32 and color.r > .32 and color.g > .25:
		return "cloth"
	if spread < .16 and color.r > .63 and color.g > .60:
		return "linen"
	if spread < .115 and color.r > .30 and color.b > .29:
		return "iron"
	return "leather"

static func surface_issue(arrays: Array) -> String:
	if arrays.size() < Mesh.ARRAY_MAX or arrays[Mesh.ARRAY_VERTEX] == null or arrays[Mesh.ARRAY_VERTEX].is_empty():
		return "缺少顶点"
	if arrays[Mesh.ARRAY_TEX_UV] == null or arrays[Mesh.ARRAY_TEX_UV].size() != arrays[Mesh.ARRAY_VERTEX].size():
		return "缺少UV或UV数量不符"
	if arrays[Mesh.ARRAY_INDEX] == null or arrays[Mesh.ARRAY_INDEX].is_empty() or arrays[Mesh.ARRAY_INDEX].size() % 3 != 0:
		return "需要非空索引三角形"
	var points: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	for index in indices:
		if index < 0 or index >= points.size():
			return "索引越界"
	for index in range(points.size()):
		if not points[index].is_finite() or not uvs[index].is_finite() or uvs[index].x < -.001 or uvs[index].x > 1.001 or uvs[index].y < -.001 or uvs[index].y > 1.001:
			return "顶点或UV不在登记数据范围"
	var usable = false
	for offset in range(0, indices.size(), 3):
		if absf((uvs[indices[offset + 1]] - uvs[indices[offset]]).cross(uvs[indices[offset + 2]] - uvs[indices[offset]])) > .0000001:
			usable = true
			break
	return "" if usable else "UV三角形全部退化"

static func region_mask(surfaces: Array) -> ImageTexture:
	# A DATA atlas derived from existing UV/rest positions, not a retouched colour image.
	# It stays attached to the original UV through every skeletal pose. R=rest height,
	# G=distance from centreline, B=coverage. Only broad anatomical guard regions use it.
	var image = Image.create(MASK_SIZE, MASK_SIZE, false, Image.FORMAT_RGB8)
	image.fill(Color(0, 0, 0))
	if surfaces.is_empty():
		return null
	var painted = 0
	for arrays in surfaces:
		if not surface_issue(arrays).is_empty():
			return null
		painted += paint_surface(image, arrays)
	return ImageTexture.create_from_image(image) if painted > 0 else null

static func paint_surface(image: Image, arrays: Array) -> int:
	var painted = 0
	var points: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	for offset in range(0, indices.size(), 3):
		var a = indices[offset]
		var b = indices[offset + 1]
		var c = indices[offset + 2]
		var p = uvs[a] * (MASK_SIZE - 1)
		var q = uvs[b] * (MASK_SIZE - 1)
		var r = uvs[c] * (MASK_SIZE - 1)
		var area = (q - p).cross(r - p)
		if absf(area) < .001:
			continue
		var low = Vector2i(maxi(0, int(floor(minf(p.x, minf(q.x, r.x))))), maxi(0, int(floor(minf(p.y, minf(q.y, r.y))))))
		var high = Vector2i(mini(MASK_SIZE - 1, int(ceil(maxf(p.x, maxf(q.x, r.x))))), mini(MASK_SIZE - 1, int(ceil(maxf(p.y, maxf(q.y, r.y))))))
		for y in range(low.y, high.y + 1):
			for x in range(low.x, high.x + 1):
				var sample_point = Vector2(x, y)
				var wb = (sample_point - p).cross(r - p) / area
				var wc = (q - p).cross(sample_point - p) / area
				var wa = 1.0 - wb - wc
				# A small UV gutter prevents unmapped seams in bilinear data sampling.
				if minf(wa, minf(wb, wc)) >= -.035:
					var position = points[a] * wa + points[b] * wb + points[c] * wc
					image.set_pixel(x, y, Color(clampf(position.y / 1.75, 0, 1), clampf(absf(position.x) / .8, 0, 1), 1))
					painted += 1
	return painted

static func shader() -> Shader:
	if shared_shader != null:
		return shared_shader
	shared_shader = Shader.new()
	shared_shader.code = """shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;
uniform sampler2D body_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D region_tex : filter_linear, repeat_disable;
uniform vec4 cloth_color : source_color = vec4(0.45, 0.6, 0.55, 1.0);
uniform bool inspect_channels = false;
void fragment(){
 vec3 original = texture(body_tex, UV).rgb;
 vec3 softened = textureLod(body_tex, UV, 2.0).rgb;
 // Compatibility already samples in sRGB; converting twice turns iron into linen.
 vec3 srgb = OUTPUT_IS_SRGB ? original : pow(max(original, vec3(0.00001)), vec3(0.454545));
 vec3 region = texture(region_tex, UV).rgb;
 float head = smoothstep(0.835, 0.88, region.r) * smoothstep(0.3, 0.8, region.b);
 float boot = 1.0 - smoothstep(0.23, 0.31, region.r);
 // This registered cast wears gloves. Do not dye its hand/boot leather as cloth.
 float glove = smoothstep(0.38,0.52,region.g) * smoothstep(0.30,0.40,region.r) * (1.0-smoothstep(0.64,0.74,region.r));
 float torso = (1.0-smoothstep(0.36, 0.49, region.g)) * smoothstep(0.43, 0.53, region.r) * (1.0-smoothstep(0.82, 0.88, region.r));
 float spread = max(srgb.r,max(srgb.g,srgb.b))-min(srgb.r,min(srgb.g,srgb.b));
 float skin = smoothstep(0.025,0.075,srgb.r-srgb.g) * smoothstep(0.025,0.08,srgb.g-srgb.b) * smoothstep(0.48,0.65,srgb.r) * smoothstep(0.19,0.28,srgb.b) * (1.0-smoothstep(1.3,1.6,(srgb.g-srgb.b)/max(0.01,srgb.r-srgb.g))) * smoothstep(0.805,0.86,region.r);
 float linen = smoothstep(0.56,0.72,min(srgb.r,srgb.g)) * (1.0-smoothstep(0.14,0.25,spread)) * (1.0-skin);
 float ochre = smoothstep(0.07,0.16,srgb.r-srgb.b) * smoothstep(0.055,0.14,srgb.g-srgb.b) * smoothstep(0.24,0.39,srgb.g) * (1.0-skin) * (1.0-head);
 float neutral_metal = (1.0-smoothstep(0.07,0.16,spread)) * smoothstep(0.30,0.48,srgb.r) * (1.0-linen) * (1.0-head) * (1.0-boot);
 // Restrict neutral steel to shoulder/arm armour, leaving trousers as dark fabric.
 float shoulder = smoothstep(0.73,0.79,region.r) * (1.0-smoothstep(0.85,0.9,region.r)) * smoothstep(0.15,0.30,region.g);
 float metal = neutral_metal * shoulder;
 float cloth = max(ochre, torso * 0.15) * (1.0-skin) * (1.0-linen) * (1.0-boot) * (1.0-glove);
 float low_luma = dot(softened,vec3(0.299,0.587,0.114));
 float broad_shade = clamp(1.0+(low_luma-0.35)*0.15,0.95,1.10);
 vec3 leather = vec3(0.135,0.073,0.038) * clamp(0.75+low_luma*1.7,0.75,1.25);
 float warm_brown = smoothstep(0.10,0.16,srgb.r-srgb.g) * (1.0-smoothstep(0.42,0.62,srgb.g));
 vec3 color = mix(original,leather,0.32*max(max(boot,glove),warm_brown)*(1.0-head)*(1.0-skin)*(1.0-linen)*(1.0-cloth));
 color = mix(color,mix(cloth_color.rgb*broad_shade,original,0.16),cloth*0.94);
 color = mix(color,vec3(0.73,0.655,0.51)*broad_shade,linen*0.58);
 color = mix(color,vec3(0.235,0.285,0.30)*broad_shade,metal*0.72);
 // Face/eyes/hair retain their authored atlas; no procedural noise or painted shadows.
 color = mix(color,original,head*0.86);
 color = mix(color,mix(original,softened,0.15)*vec3(1.02,1.0,0.985),skin*0.92);
 ALBEDO = max(color,vec3(0.0));
 METALLIC = metal;
 ROUGHNESS = mix(mix(0.82,0.96,max(cloth,linen)),0.57,metal);
 ROUGHNESS = mix(ROUGHNESS,0.91,skin);
 SPECULAR = mix(0.20,0.46,metal);
 if(inspect_channels){ ALBEDO=vec3(0.0); EMISSION=vec3(skin,cloth,metal); }
}
"""
	return shared_shader
