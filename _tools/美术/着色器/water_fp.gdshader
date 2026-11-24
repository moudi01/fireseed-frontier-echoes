shader_type spatial;
// Forward+ native transparent water. No screen-texture readback and no
// GLES3 color-transport compensation. Depth is used only for distance absorption.
render_mode blend_mix, depth_draw_never, cull_back, specular_schlick_ggx;

uniform sampler2D depth_texture : hint_depth_texture, repeat_disable, filter_nearest;
uniform int display_mode = 3;
uniform float phase_seconds = 2.0;
uniform vec3 lamp_position = vec3(-1.75, 1.45, 1.25);
uniform float near_plane = 0.2;
uniform float far_plane = 70.0;
uniform vec3 shallow_color : source_color = vec3(0.10, 0.26, 0.28);
uniform vec3 deep_color : source_color = vec3(0.008, 0.030, 0.040);
uniform float absorption = 0.22;
uniform float ripple_strength = 0.020;

varying vec3 surface_world;

void vertex() {
    surface_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    // Forward+ depth is reverse-Z (1 near, 0 far). Convert to a view-space
    // depth in metres, and compare it with the water plane in the SAME metric.
    // Mixing view-space z with Euclidean camera distance bends the shoreline.
    float depth = textureLod(depth_texture, SCREEN_UV, 0.0).r;
    float normal_depth = 1.0 - depth;
    float scene_z = 2.0 * near_plane * far_plane
                  / (near_plane + far_plane - normal_depth * (far_plane - near_plane));
    float surface_z = -(VIEW_MATRIX * vec4(surface_world, 1.0)).z;
    float water_depth = max(scene_z - surface_z, 0.0);

    // A depth gradient marks the opaque silhouette crossing the plane. Absolute
    // depth alone would put a ring on submerged platform tops.
    float waterline_gradient = length(vec2(dFdx(water_depth), dFdy(water_depth)));
    float contact = (1.0 - smoothstep(0.0, 0.55, water_depth))
                  * smoothstep(0.02, 0.12, waterline_gradient);

    if (display_mode == 6) {
        ALBEDO = vec3(depth);
        ALPHA = 1.0;
    } else if (display_mode == 8) {
        ALBEDO = vec3(clamp(scene_z / 30.0, 0.0, 1.0));
        ALPHA = 1.0;
    } else if (display_mode == 10) {
        ALBEDO = vec3(clamp(water_depth / 2.0, 0.0, 1.0));
        ALPHA = 1.0;
    } else if (display_mode == 11) {
        ALBEDO = vec3(0.0);
        EMISSION = vec3(smoothstep(0.02, 0.12, waterline_gradient));
        ALPHA = 1.0;
    } else if (water_depth <= 0.0) {
        // The water plane must not paint a film over dry bank geometry in front of it.
        discard;
    } else {
        vec2 p = surface_world.xz;
        float t = phase_seconds;
        float a0 = dot(p, vec2(2.2, 1.0)) + t * 0.55;
        float b0 = dot(p, vec2(-0.9, 3.1)) - t * 0.36;
        vec2 slope = vec2(2.2, 1.0) * cos(a0) * ripple_strength
                   + vec2(-0.9, 3.1) * cos(b0) * ripple_strength * 0.7;
        vec3 world_normal = normalize(vec3(-slope.x, 1.0, -slope.y));
        NORMAL = normalize((VIEW_MATRIX * vec4(world_normal, 0.0)).xyz);

        // Break the long parallel crests: phase warping makes the lit lines
        // curve and end, instead of reading as contour lines on a flat sheet.
        float a = a0 + 0.9 * sin(dot(p, vec2(0.37, 0.91)) * 1.3 + 0.20 * t);
        float b = b0 + 0.7 * sin(dot(p, vec2(1.13, -0.42)) * 1.7 - 0.15 * t);
        float grain = sin(dot(p, vec2(4.1, 6.3)) * 1.9 + 0.23 * t)
                    * sin(dot(p, vec2(2.3, -3.7)) * 2.7 - 0.17 * t);
        float ripple_line = smoothstep(0.94, 1.0, sin(a + 0.75 * sin(b)) * (0.60 + 0.40 * grain));
        float ripple_break = 0.5 + 0.5 * sin(dot(p, vec2(0.21, 0.13)) + 0.17 * t);

        float absorbed = 1.0 - exp(-absorption * min(water_depth, 9.0));
        // Immersion hue reads the shallow 0.2-0.6 m range, where the old seal sits.
        float immersion = 1.0 - exp(-water_depth / 0.30);
        vec3 water_color = mix(shallow_color, deep_color,
            clamp(immersion * 0.45 + absorbed * 0.25, 0.0, 1.0));

        // Keep the existing light hierarchy: warm lamp area, low cold explored
        // path, and black unknown water. Same footprint as stone.gdshader.
        float lamp_distance = length(lamp_position - surface_world);
        float lamp_gate = 1.0 - smoothstep(4.0, 8.0, lamp_distance);
        float known = 1.0 - smoothstep(5.3, 7.5, length(p - vec2(-1.5, 1.2)));
        float back_path = smoothstep(1.8, 3.5, p.y) * (1.0 - smoothstep(3.0, 6.0, abs(p.x + 2.0)));
        float explored = max(known, back_path);
        float visible_gate = max(lamp_gate, explored * 0.45);

        // Waterline: narrow low-intensity response where an opaque surface crosses
        // the plane. It fades within ~0.14 m of view-space depth, so submerged
        // platform tops do not get an outline ring.
        // Waterline and immersion are carried by stone_fp.gdshader, because the
        // water surface is depth-tested behind the opaque silhouette and cannot
        // draw on those pixels.
        ALBEDO = water_color * (0.10 + 0.90 * visible_gate);
        ALPHA = clamp((0.42 + 0.48 * absorbed) * (0.10 + 0.90 * visible_gate), 0.0, 0.95);
        ROUGHNESS = 0.08;
        METALLIC = 0.0;
        SPECULAR = 0.45;

        if (display_mode == 2) {
            // Lowest-water control: color and transparency only, no depth response.
            ALBEDO = shallow_color;
            ALPHA = 0.28;
            ROUGHNESS = 0.12;
            EMISSION = vec3(0.0);
        } else {
            vec3 view_dir = normalize(CAMERA_POSITION_WORLD - surface_world);
            float fresnel = 0.04 + 0.50 * pow(1.0 - max(dot(view_dir, world_normal), 0.0), 5.0);
            float shallow = 1.0 - smoothstep(0.0, 0.55, water_depth);
            float lamp_near = smoothstep(0.10, 0.85, lamp_gate);
            vec3 sky_sheen = vec3(0.10, 0.20, 0.24) * (0.08 + 0.40 * fresnel)
                           * (1.0 - 0.85 * absorbed) * visible_gate
                           * (1.0 + 0.25 * shallow + 0.45 * lamp_near);
            vec3 ripple_sheen = vec3(0.14, 0.30, 0.32) * ripple_line
                              * (0.35 + 0.65 * ripple_break) * 0.032
                              * (1.0 - 0.70 * absorbed) * visible_gate
                              * (1.0 + 0.55 * shallow);
            vec3 lamp_sheen = vec3(0.55, 0.36, 0.18) * lamp_near * fresnel * 0.035;
            vec3 to_lamp = lamp_position - surface_world;
            float falloff = pow(max(1.0 - lamp_distance / 5.5, 0.0), 2.0);
            vec3 half_dir = normalize(view_dir + normalize(to_lamp));
            float highlight = pow(max(dot(half_dir, world_normal), 0.0), 28.0);
            EMISSION = sky_sheen + ripple_sheen + lamp_sheen
                     + vec3(1.0, 0.56, 0.22) * highlight * falloff * 0.22;
        }
    }
}
