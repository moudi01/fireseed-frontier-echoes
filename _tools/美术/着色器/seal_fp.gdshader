shader_type spatial;
// Forward+ Meshy seal platform: atlas albedo + normal + roughness with the
// same wet band, submerged tint and explored/unknown mask as the rest of FP.
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_disable;
uniform sampler2D roughness_tex : filter_linear_mipmap, repeat_disable;
uniform vec3 lamp_position = vec3(-1.75, 1.45, 1.25);
uniform bool water_enabled = true;
uniform float read_gain = 1.70;
varying vec3 world_point;

void vertex() {
    world_point = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    vec3 color = texture(albedo_tex, UV).rgb;
    NORMAL_MAP = texture(normal_tex, UV).rgb;
    NORMAL_MAP_DEPTH = 1.0;
    ROUGHNESS = texture(roughness_tex, UV).r;

    vec2 p = world_point.xz;
    float water_gate = water_enabled ? 1.0 : 0.0;
    float wet = (1.0 - smoothstep(0.0, 0.22, abs(world_point.y))) * water_gate;
    color *= mix(1.0, 0.62, wet);

    float depth = max(-world_point.y, 0.0);
    float absorption = (1.0 - exp(-depth * 1.5)) * water_gate;
    vec3 water_tint = vec3(0.55, 0.80, 0.88);
    color = mix(color, color * water_tint, absorption * 0.70);
    color *= mix(1.0, 0.90, absorption);
    color *= read_gain;

    float known = 1.0 - smoothstep(5.3, 7.5, length(p - vec2(-1.5, 1.2)));
    float back_path = smoothstep(1.8, 3.5, p.y) * (1.0 - smoothstep(3.0, 6.0, abs(p.x + 2.0)));
    float explored = max(known, back_path);
    ALBEDO = color * explored;
    METALLIC = 0.0;
}
