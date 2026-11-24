#version 330 core

layout (location = 0) out vec4 fragColor;

const vec3 gamma = vec3(2.2);
const vec3 inv_gamma = 1.0 / gamma;

uniform sampler2DArray u_texture_array_0;
uniform vec3 bg_color;
uniform float water_line;
uniform float u_time;
uniform float u_underwater;      // 1.0 when the camera is below the water line
uniform vec3 water_fog_color;
uniform float water_fog_density;

in vec2 uv;
in float shading;
in vec3 frag_world_pos;

flat in int face_id;
flat in int voxel_id;


// moving light pattern of sunlight refracted by waves
float caustics(vec2 p, float t) {
    float a = sin(p.x * 1.7 + t * 1.3) * sin(p.y * 1.3 - t * 0.9);
    float b = sin((p.x + p.y) * 0.9 - t * 1.1) * sin((p.x - p.y) * 1.1 + t * 0.7);
    return pow(abs(a + b) * 0.5, 2.0);
}


void main() {
    vec2 face_uv = uv;
    face_uv.x = uv.x / 3.0 - float(min(face_id, 2)) / 3.0;

    vec3 tex_col = texture(u_texture_array_0, vec3(face_uv, float(voxel_id))).rgb;
    tex_col = pow(tex_col, gamma);

    tex_col *= shading;

    float fog_dist = gl_FragCoord.z / gl_FragCoord.w;

    if (frag_world_pos.y < water_line) {
        // underwater surfaces: blue absorption, darker with depth, caustics
        float depth = water_line - frag_world_pos.y;
        tex_col *= vec3(0.25, 0.55, 1.0) * exp(-0.08 * depth);
        tex_col += vec3(0.35, 0.55, 0.6) * caustics(frag_world_pos.xz, u_time) * exp(-0.15 * depth);
    }

    if (u_underwater > 0.5) {
        tex_col *= vec3(0.45, 0.75, 1.0);  // light absorbed by the water around the camera
        tex_col = mix(tex_col, pow(water_fog_color, gamma),
                      1.0 - exp(-water_fog_density * fog_dist * fog_dist));
    } else {
        tex_col = mix(tex_col, pow(bg_color, gamma), (1.0 - exp2(-0.00001 * fog_dist * fog_dist)));
    }

    tex_col = pow(tex_col, inv_gamma);
    fragColor = vec4(tex_col, 1.0);
}
