shader_type spatial;
render_mode unshaded, cull_disabled;
uniform sampler2D atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform vec4 pigment : source_color = vec4(0.65, 0.71, 0.69, 1.0);
uniform float metallic = 0.0;
uniform float roughness = 1.0;
uniform float vegetation = 0.0;
uniform vec3 lamp;
uniform vec3 side_lamp;
uniform float side_power;
uniform float explored_front;
uniform float time_clock;
uniform float borrow_time;
uniform float obstruction;
uniform float side_flash;
uniform float art_time;
uniform vec2 pocket_center;
uniform vec2 pocket_radius;
varying vec3 world;
varying vec3 normal_world;
float brush_noise(vec2 p) {
	vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);
	float a=fract(sin(dot(i,vec2(127.1,311.7)))*43758.5453);
	float b=fract(sin(dot(i+vec2(1,0),vec2(127.1,311.7)))*43758.5453);
	float c=fract(sin(dot(i+vec2(0,1),vec2(127.1,311.7)))*43758.5453);
	float d=fract(sin(dot(i+vec2(1,1),vec2(127.1,311.7)))*43758.5453);
	return mix(mix(a,b,f.x),mix(c,d,f.x),f.y);
}
void vertex() {
	if (vegetation > 0.5) {
		VERTEX.x += sin(art_time * 0.65 + VERTEX.y * 1.1) * max(VERTEX.y, 0.0) * 0.012;
	}
	world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	normal_world = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}
void fragment() {
	vec3 original = texture(atlas, UV).rgb;
	float value = dot(original, vec3(0.2126, 0.7152, 0.0722));
	vec3 base = mix(vec3(value), original, vegetation > 0.5 ? 0.34 : 0.48) * pigment.rgb;
	float distance_to_lamp=length((world-lamp)*vec3(1.0,0.65,1.0));
	float soft_distance=distance_to_lamp*(1.0+brush_noise(world.xz*0.62)*0.08);
	float warm=exp(-soft_distance*soft_distance*0.24)*(1.0-smoothstep(2.65,3.8,soft_distance));
	float known = 1.0 - smoothstep(explored_front-0.25, explored_front+0.25, world.x);
	known *= (1.0-smoothstep(2.2,3.6,abs(world.z))) * step(-15.0,world.x);
	vec3 n = normalize(normal_world);
	float direct = max(0.0,dot(n,normalize(lamp-world)));
	float form = smoothstep(0.0,1.0,direct*0.7 + max(n.y,0.0)*0.3);
	float wet = 1.0-smoothstep(0.02,0.30,world.y);
	base *= 1.0 - wet * (vegetation > 0.5 ? 0.05 : 0.17);
	vec3 cold = base * vec3(0.20,0.34,0.52)*known*(0.55+max(n.y,0.0)*0.45);
	vec3 lit = base * vec3(1.28,1.08,0.77)*warm*(0.52+form*0.85);
	ALBEDO = max(cold,lit);
	METALLIC = metallic;
	ROUGHNESS = roughness;
}
