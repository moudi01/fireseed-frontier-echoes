shader_type spatial;
render_mode blend_mix, depth_draw_never, specular_disabled;
uniform sampler2D albedo_map : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
void fragment() {
	vec4 tex = texture(albedo_map, UV);
	ALBEDO = tex.rgb;
	ROUGHNESS = 1.0;
	// Reject generated low-alpha haze; retain a small softened contour.
	ALPHA = smoothstep(0.35, 0.72, tex.a);
}
