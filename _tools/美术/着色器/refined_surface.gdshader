shader_type spatial;
render_mode unshaded, cull_disabled;
uniform vec4 pigment : source_color = vec4(0.35, 0.42, 0.47, 1.0);
uniform float family = 0.0;
uniform float kind = 0.0;
uniform float submerged = 0.0;
uniform vec3 lamp = vec3(-5.2, 0.9, 0.1);
uniform vec3 side_lamp = vec3(-3.3, 0.7, -1.0);
uniform float side_power = 0.0;
uniform float explored_front = -4.0;
uniform float time_clock = 0.0;
uniform float borrow_time = -1.0;
uniform float obstruction = 0.0;
uniform float side_flash = 0.0;
uniform float roll_strength = 0.0;
uniform float art_time = 0.0;
uniform float arch_simplify = 0.0;
uniform vec2 pocket_center = vec2(-3.35, 0.82);
uniform vec2 pocket_radius = vec2(0.76, 0.92);
varying vec3 world;
varying vec3 normal_world;
varying vec3 face_tint;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float mark(vec2 p) {
	vec2 q = abs(p);
	float a = (1.0 - smoothstep(0.025, 0.045, abs(q.x - 0.28))) * (1.0 - smoothstep(0.18, 0.23, q.y));
	float b = (1.0 - smoothstep(0.020, 0.040, abs(q.y - 0.20))) * (1.0 - smoothstep(0.22, 0.29, q.x));
	return max(a, b) * step(-0.08, p.x + p.y);
}
void vertex() {
	if (kind > 1.5 && kind < 2.5) { VERTEX.y += roll_strength * pow(UV.x, 3.0) * 0.34; }
	if (family > 2.5 && family < 3.5) { VERTEX.x += sin(art_time * 0.55 + VERTEX.y * 1.4) * UV.y * 0.012; }
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	// Flatten carved-face shading only; positions, opening and silhouette stay intact.
	float face_mask = smoothstep(0.12, 0.28, abs(VERTEX.z));
	vec3 broad_normal = vec3(0.0, 0.0, VERTEX.z < 0.0 ? -1.0 : 1.0);
	vec3 restrained_normal = normalize(mix(NORMAL, broad_normal, arch_simplify * face_mask));
	normal_world = normalize(MODEL_NORMAL_MATRIX * restrained_normal);
	face_tint = mix(vec3(1.0), COLOR.rgb, step(0.001, length(COLOR.rgb)));
}
void fragment() {
	float distance_to_lamp = length((world-lamp)*vec3(1.0,0.65,1.0));
	float soft_distance = distance_to_lamp * (1.0 + noise(world.xz*0.62)*0.08);
	float warm = exp(-soft_distance*soft_distance*0.24) * (1.0-smoothstep(2.65,3.8,soft_distance));
	float known = 1.0 - smoothstep(explored_front - 0.25, explored_front + 0.25, world.x);
	known *= (1.0 - smoothstep(2.2, 3.6, abs(world.z))) * step(-15.0, world.x);
	float visibility = max(warm, known * 0.18);
	float side = (1.0 - smoothstep(0.1, 1.65, length(world - side_lamp))) * side_power;
	float brush = noise(world.xz * 2.3 + world.y * vec2(0.3, 0.8));
	float small_brush = noise(world.xz * 9.5);
	vec3 n = normalize(normal_world);
	float direct = max(0.0, dot(n, normalize(lamp - world)));
	float form = smoothstep(0.0,1.0,direct*0.7+max(n.y,0.0)*0.3);
	if (family > 0.5 && family < 1.5) { form = 0.52 + direct*0.12; }
	vec3 base = pigment.rgb * face_tint * (0.80 + brush * 0.28 + small_brush * 0.045);
	float wet = 1.0 - smoothstep(0.0, 0.30, world.y);
	if (family < 1.5) { base *= 1.0 - wet * 0.23; }
	if (family > 1.5 && family < 2.5) { base *= 0.8 + brush * 0.3; }
	vec3 cold = base * vec3(0.20, 0.34, 0.52) * known * (0.55 + max(n.y, 0.0) * 0.45);
	vec3 lit = base * vec3(1.28, 1.08, 0.77) * warm * (0.52 + form * 0.85);
	vec3 result = max(cold, lit) + base * vec3(0.20, 0.31, 0.40) * side * 0.22;
	if (kind > 0.5 && kind < 1.5) {
		if (length((world.xz - pocket_center) / pocket_radius) < 1.0) { discard; }
		float broad = noise(world.xz * 0.8);
		float wave = sin(world.x * 2.2 + world.z * 4.8 + noise(world.xz * 1.7) * 3.0 - art_time * 0.45);
		float crest = smoothstep(0.94, 1.0, wave) * smoothstep(0.30, 0.65, noise(world.xz * 3.2));
		result = mix(vec3(0.007, 0.021, 0.034), vec3(0.022, 0.057, 0.067), broad) * max(warm, known * 0.10);
		float lamp_trace = exp(-pow((world.x - lamp.x) * 0.8, 2.0)) * crest * warm;
		result += vec3(0.10, 0.18, 0.19) * crest * max(warm * 0.40, known * 0.025);
		result += vec3(0.17, 0.12, 0.05) * lamp_trace * 0.20;
		// A finite shallow-water transition around the existing projected pocket.
		float pool = 1.0-smoothstep(1.0,1.85,length((world.xz-pocket_center)/pocket_radius));
		result += vec3(0.010,0.035,0.045)*pool*warm;
	}
	if (kind > 1.5 && kind < 2.5) {
		float edge = abs(UV.y - 0.5) + sin(world.x * 9.0) * 0.018;
		if (edge > 0.47) { discard; }
		result *= 0.36;
		result += vec3(0.12, 0.18, 0.20) * mark(UV - 0.5) * visibility * 0.32;
	}
	if (kind > 5.5 && kind < 6.5) {
		if (mark(UV - 0.5) < 0.10) { discard; }
		result = vec3(0.09, 0.18, 0.20) * visibility;
	}
	if (kind > 6.5) {
		float r = length((UV - 0.5) * 2.0);
		if (abs(r - 0.72) > 0.022 || sin(UV.x * 17.0 + UV.y * 9.0) < 0.2) { discard; }
		result = vec3(0.045, 0.11, 0.13) * warm * 0.38;
	}
	if (submerged > 0.5) {
		float depth = clamp((0.045-world.y)/0.8,0.0,1.0);
		float local_lamp = 1.0-smoothstep(0.65,3.4,length(world.xz-lamp.xz));
		if (kind > 5.5 && kind < 6.5) { result = vec3(0.11,0.24,0.25)*local_lamp*0.78; }
		result = result*vec3(0.65,0.88,0.94)*(1.35-depth*0.25) + vec3(0.008,0.025,0.030)*local_lamp*(1.0-depth*0.35);
	}
	ALBEDO = result;
}
