shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never;
uniform vec3 lamp = vec3(-5.2, 0.9, 0.1);
uniform vec3 side_lamp;
uniform float side_power;
uniform float explored_front;
uniform float time_clock;
uniform float borrow_time;
uniform float obstruction;
uniform float side_flash;
uniform float art_time = 0.0;
uniform vec2 pocket_center;
uniform vec2 pocket_radius;
varying vec3 world;
void vertex() { world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	vec2 p = (world.xz - pocket_center) / pocket_radius;
	float r = length(p);
	if (r >= 1.0) { discard; }
	float warm = 1.0 - smoothstep(0.65, 3.8, length((world - lamp) * vec3(1.0, 0.65, 1.0)));
	float known = 1.0 - smoothstep(explored_front - 0.25, explored_front + 0.25, world.x);
	float crest = smoothstep(0.86,1.0,sin(dot(p,vec2(5.0,8.0))-art_time*0.45));
	float shallow = 1.0-smoothstep(0.45,1.0,r);
	ALBEDO = vec3(0.018,0.060,0.075)*max(warm,known*0.08) + vec3(0.045,0.11,0.12)*crest*warm*0.4;
	ALPHA = 0.12 + crest*0.16 + smoothstep(0.75,1.0,r)*0.12 + shallow*0.03;
}
