shader_type spatial;
// Forward+ stone surface. Adds a wet band at the waterline and a light cold
// absorption below it. The shared Compatibility stone shader is untouched.
uniform vec4 stone_color : source_color = vec4(0.25, 0.30, 0.29, 1.0);
uniform bool engraved = false;
uniform bool water_enabled = true;
uniform float read_gain = 1.0;
uniform vec3 lamp_position = vec3(-1.75, 1.45, 1.25);
varying vec3 world_point;

void vertex() {
    world_point = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    vec2 p = world_point.xz;
    float grain = sin(p.x * 7.3 + sin(p.y * 3.5)) * sin(p.y * 9.1) * 0.035;
    vec3 color = stone_color.rgb * (1.0 + grain);
    if (engraved) {
        // Dark incisions in an OPAQUE stone material, not a transparent decal.
        vec2 local_p = (p - vec2(0.35, -1.20));
        float border = abs(max(abs(local_p.x) / 1.25, abs(local_p.y) / 0.88) - 0.77);
        float ring = abs(length(local_p * vec2(1.0, 1.18)) - 0.50);
        float stem = max(abs(local_p.x) - 0.035, abs(local_p.y) - 0.44);
        float cross_line = max(abs(local_p.y) - 0.033, abs(local_p.x) - 0.42);
        float cuts = max(1.0 - smoothstep(0.015, 0.035, min(border, ring)),
                         1.0 - smoothstep(0.0, 0.012, min(stem, cross_line)));
        color *= mix(1.0, 0.22, cuts);
    }

    // Wet band: narrow darkening just above/below y=0, with a glossier response.
    float water_gate = water_enabled ? 1.0 : 0.0;
    float wet = (1.0 - smoothstep(0.0, 0.18, abs(world_point.y))) * water_gate;
    color *= mix(1.0, 0.55, wet);

    // Submerged stone keeps its local contrast but shifts cold and loses a little
    // brightness, so the old seal reads as a submerged surface rather than dry rock.
    float depth = max(-world_point.y, 0.0);
    float absorption = (1.0 - exp(-depth * 1.5)) * water_gate;
    vec3 water_tint = vec3(0.55, 0.80, 0.88);
    color = mix(color, color * water_tint, absorption * 0.90);
    color *= mix(1.0, 0.90, absorption);
    if (engraved) {
        // The seal sits in a dim part of the lamp falloff; compensate the
        // submerged tint so its cuts stay readable.
        color *= mix(1.0, 1.35, water_gate);
    }
    color *= read_gain;

    // Deliberate explored footprint: the far unknown stays black even under ambient.
    float known = 1.0 - smoothstep(5.3, 7.5, length(p - vec2(-1.5, 1.2)));
    float back_path = smoothstep(1.8, 3.5, p.y) * (1.0 - smoothstep(3.0, 6.0, abs(p.x + 2.0)));
    float explored = max(known, back_path);
    float lamp_gate = 1.0 - smoothstep(4.0, 8.0, distance(lamp_position, world_point));

    ALBEDO = color * explored;
    ROUGHNESS = mix(0.94, 0.40, wet);

    // The wet band catches a low sheen independent of the coarse low-poly normal,
    // so it reads as a waterline instead of a flat shadow. It follows the same
    // lamp/explored gate as the water, so the far shoreline stays black.
    vec3 wet_sheen = mix(vec3(0.30, 0.60, 0.64), vec3(1.0, 0.70, 0.38), lamp_gate);
    EMISSION = wet_sheen * wet * 0.04 * lamp_gate * explored;
}
