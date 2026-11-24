shader_type spatial;
// Forward+ shoreline rock: Quaternius atlas colour plus the same wet band,
// submerged tint and explored/unknown mask as the procedural stone.
uniform sampler2D atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform vec3 tint : source_color = vec3(0.82, 0.86, 0.83);
uniform vec3 lamp_position = vec3(-1.75, 1.45, 1.25);
uniform bool water_enabled = true;
varying vec3 world_point;

void vertex() {
    world_point = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    vec3 color = texture(atlas, UV).rgb * tint;
    vec2 p = world_point.xz;
    float water_gate = water_enabled ? 1.0 : 0.0;
    float wet = (1.0 - smoothstep(0.0, 0.30, abs(world_point.y))) * water_gate;
    color *= mix(1.0, 0.68, wet);

    float depth = max(-world_point.y, 0.0);
    float absorption = (1.0 - exp(-depth * 0.9)) * water_gate;
    vec3 water_tint = vec3(0.55, 0.80, 0.88);
    color = mix(color, color * water_tint, absorption * 0.75);
    color *= mix(1.0, 0.92, absorption);

    float known = 1.0 - smoothstep(5.3, 7.5, length(p - vec2(-1.5, 1.2)));
    float back_path = smoothstep(1.8, 3.5, p.y) * (1.0 - smoothstep(3.0, 6.0, abs(p.x + 2.0)));
    float explored = max(known, back_path);
    ALBEDO = color * explored;
    ROUGHNESS = mix(0.92, 0.42, wet);
    METALLIC = 0.0;

    // A short wet sheen at the waterline, gated by lamp and explored area so the
    // far shoreline stays black and the rock does not get an outline ring.
    float lamp_gate = 1.0 - smoothstep(4.0, 8.0, distance(lamp_position, world_point));
    vec3 wet_sheen = mix(vec3(0.30, 0.60, 0.64), vec3(1.0, 0.70, 0.38), lamp_gate);
    EMISSION = wet_sheen * wet * 0.04 * lamp_gate * explored;
}
