shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never;
uniform vec3 lamp = vec3(-5.6, 1.1, 0.0);
uniform vec3 side_lamp = vec3(-3.0, 0.8, -2.1);
uniform float side_power = 0.0;
uniform float explored_front = -4.0;
uniform float time_clock = 0.0;
uniform float borrow_time = -1.0;
uniform float obstruction = 0.0;
uniform float side_flash = 0.0;
uniform vec2 pocket_center = vec2(-3.7, 0.10);
uniform vec2 pocket_radius = vec2(0.76, 0.92);
varying vec3 world;
void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
void fragment() {
	vec2 local = (world.xz - pocket_center) / pocket_radius;
	float radius = length(local);
	if (radius >= 1.0) { discard; }
	float warm = 1.0 - smoothstep(0.6, 3.8, length((world - lamp) * vec3(1.0, 0.6, 1.0)));
	float forward_mask = smoothstep(lamp.x + 0.30, lamp.x + 1.0, world.x) * (1.0 - smoothstep(0.65, 1.2, abs(world.z)));
	warm *= 1.0 - obstruction * forward_mask * 0.65;
	float known = (1.0 - smoothstep(explored_front - 0.25, explored_front + 0.25, world.x));
	known *= (1.0 - smoothstep(1.6, 2.8, abs(world.z))) * step(-10.5, world.x);
	float visibility = max(warm, known * 0.15);
	// Small moving opaque crests cover the submerged mark at water height.
	float crest = smoothstep(0.90, 1.0, sin(length(local * vec2(0.8, 1.0) + vec2(0.3, -0.2)) * 18.0 - time_clock * 1.4));
	float rim = smoothstep(0.80, 1.0, radius);
	ALBEDO = vec3(0.008, 0.034, 0.046) * visibility + vec3(0.08, 0.15, 0.17) * crest * warm;
	ALPHA = 0.18 + crest * 0.50 + rim * 0.15;
}
