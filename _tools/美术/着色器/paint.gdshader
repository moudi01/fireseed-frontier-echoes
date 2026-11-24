shader_type spatial;
render_mode unshaded, cull_disabled;
uniform vec4 pigment : source_color = vec4(0.2, 0.28, 0.32, 1.0);
uniform vec3 lamp = vec3(-5.6, 1.1, 0.0);
uniform vec3 side_lamp = vec3(-3.0, 0.8, -2.1);
uniform float side_power = 0.0;
uniform float explored_front = -4.0;
uniform float kind = 0.0; // 0 solid, 1 lake, 2 shadow, 3 glow, 4 contact, 6 imprint
uniform float time_clock = 0.0;
uniform float borrow_time = -1.0;
uniform float obstruction = 0.0;
uniform float side_flash = 0.0;
uniform float roll_strength = 0.0;
uniform float character_rim = 0.0;
uniform float beacon = 0.0;
uniform float submerged = 0.0;
uniform vec2 pocket_center = vec2(-3.7, 0.10);
uniform vec2 pocket_radius = vec2(0.76, 0.92);
varying vec3 world;
varying vec3 face_normal;
float old_mark(vec2 p) {
	vec2 q = abs(p);
	float a = (1.0 - smoothstep(0.025, 0.045, abs(q.x - 0.28))) * (1.0 - smoothstep(0.18, 0.23, q.y));
	float b = (1.0 - smoothstep(0.020, 0.040, abs(q.y - 0.20))) * (1.0 - smoothstep(0.22, 0.29, q.x));
	float crack = (1.0 - smoothstep(0.014, 0.030, abs(p.y - p.x * 0.45 - 0.04))) * (1.0 - smoothstep(0.10, 0.19, q.x));
	return max(max(a, b) * step(-0.08, p.x + p.y), crack * 0.6);
}
void vertex() {
	// Only near-shore sheets bend. They stay zero-thickness surfaces.
	if (kind > 1.5 && kind < 2.5) {
		VERTEX.y += roll_strength * pow(clamp(UV.x, 0.0, 1.0), 3.0) * 0.34;
	}
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	face_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}
void fragment() {
	float dist = length((world - lamp) * vec3(1.0, 0.6, 1.0));
	float warm = 1.0 - smoothstep(0.6, 3.8, dist);
	float forward_mask = smoothstep(lamp.x + 0.30, lamp.x + 1.0, world.x) * (1.0 - smoothstep(0.65, 1.2, abs(world.z)));
	float blocked_warm = warm * (1.0 - obstruction * forward_mask * 0.65);
	float side = (1.0 - smoothstep(0.1, 1.65, length(world - side_lamp))) * side_power;
	float known = (1.0 - smoothstep(explored_front - 0.25, explored_front + 0.25, world.x));
	known *= (1.0 - smoothstep(1.6, 2.8, abs(world.z))) * step(-10.5, world.x);
	float form = floor((dot(normalize(face_normal), normalize(vec3(-0.4, 0.9, 0.5))) * 0.5 + 0.5) * 4.0) / 4.0;
	float brush = sin(world.x * 6.3 + sin(world.z * 3.5)) * sin(world.z * 7.0 + world.y * 4.0) * 0.035;
	vec3 base = pigment.rgb * (0.50 + form * 0.50 + brush);
	vec3 cool = base * vec3(0.24, 0.37, 0.54) * known;
	vec3 lit = base * vec3(1.4, 1.05, 0.67) * blocked_warm * 1.3;
	vec3 side_tint = mix(vec3(0.50, 0.65, 0.8), vec3(1.0, 0.72, 0.34), side_flash);
	lit += base * side_tint * side * (0.32 + side_flash * 0.18);
	vec3 result = max(cool, lit);
	result += vec3(0.016, 0.026, 0.039) * known * character_rim * smoothstep(0.15, 0.7, form) * (1.0 - warm);
	if (kind > 0.5 && kind < 1.5) {
		// Disjoint surface domains: only the local veil draws inside this pocket.
		if (length((world.xz - pocket_center) / pocket_radius) < 1.0) { discard; }
		// Opaque, controlled illusion of an offset/deeper imprint; no reflection pass.
		float cell = floor((world.x + 4.25) / 1.1);
		vec2 deep = vec2(fract((world.x + 4.25) / 1.1) - 0.5, (world.z + 0.30) / 1.28);
		float route = step(0.0, cell) * step(cell, 8.0) * (1.0 - smoothstep(0.6, 1.0, abs(world.z)));
		float source = old_mark(deep) * route;
		float cue = borrow_time < 0.0 ? 0.0 : smoothstep(0.0, 0.22, borrow_time - cell * 0.20);
		float ring_dist = length(vec2(world.x * 0.72 + 1.3, world.z * 1.1 - 0.4));
		float wave = sin(ring_dist * 13.0 - time_clock * 1.5 + sin(world.x * 1.8) * 0.7);
		float ripples = smoothstep(0.94, 1.0, wave) * (0.45 + 0.55 * sin(world.z * 3.0 + world.x * 1.1));
		float path_edge = abs(abs(world.z) - 0.65 + sin(world.x * 7.0 + time_clock) * 0.025);
		float contact_line = (1.0 - smoothstep(0.015, 0.07, path_edge)) * route;
		result += vec3(0.045, 0.100, 0.120) * source * warm * (0.35 + cue * 0.5);
		result += vec3(0.07, 0.15, 0.18) * ripples * max(blocked_warm * 0.50, known * 0.03);
		result += vec3(0.10, 0.18, 0.19) * contact_line * blocked_warm * cue * 0.45;
	}
	if (kind > 1.5 && kind < 2.5) {
		float irregular = sin(world.x * 9.0) * 0.018 + sin(world.x * 21.0) * 0.009;
		float edge_dist = abs(UV.y - 0.5) + irregular;
		if (edge_dist > 0.47) { discard; }
		// A few wave interruptions eat into the outline instead of plank crossbars.
		float edge_wave = sin(world.x * 12.0 + time_clock * 0.8) * 0.5 + 0.5;
		if (edge_dist > 0.42 && edge_wave > 0.72) { discard; }
		float edge = smoothstep(0.40, 0.47, edge_dist);
		float stamp = old_mark(UV - vec2(0.5));
		result = max(vec3(0.012, 0.022, 0.034) * known, result * 0.38);
		result += vec3(0.18, 0.25, 0.27) * (stamp * 0.36 + edge * 0.18) * max(blocked_warm, known * 0.13);
		result += vec3(0.09, 0.15, 0.18) * roll_strength * edge * blocked_warm;
	}
	if (kind > 2.5 && kind < 3.5) {
		result = pigment.rgb * max(warm, side * 0.45) * 1.8;
		result = mix(result, vec3(0.60, 0.38, 0.14) * (0.65 + side_flash * 0.40), beacon * side_power);
	}
	if (kind > 3.5 && kind < 4.5) {
		float radius = length((UV - 0.5) * 2.0);
		float coverage = (1.0 - smoothstep(0.20, 1.0, radius)) * 0.72;
		float grain = fract(sin(dot(floor(FRAGCOORD.xy), vec2(12.9898, 78.233))) * 43758.5453);
		if (grain > coverage) { discard; }
		result *= 0.30;
	}
	if (kind > 5.5) {
		if (old_mark(UV - vec2(0.5)) < 0.1) { discard; }
		result += vec3(0.10, 0.13, 0.13) * max(warm, known * 0.15);
	}
	if (submerged > 0.5) {
		float depth = max(0.0, 0.045 - world.y);
		vec3 absorption = exp(-vec3(1.8, 0.65, 0.38) * depth);
		vec3 deep_tint = vec3(0.008, 0.025, 0.032) * max(warm, known * 0.12);
		float cue = borrow_time < 0.0 ? 0.0 : smoothstep(0.0, 0.22, borrow_time);
		result = mix(deep_tint, result * absorption, 0.60);
		if (kind > 5.5) { result *= 0.35 + cue * 0.65; }
	}
	ALBEDO = result;
}
