#version 330 core

layout (location = 0) out vec4 fragColor;

const vec3 gamma = vec3(2.2);
const vec3 inv_gamma = 1.0 / gamma;
const vec3 sun_dir = normalize(vec3(0.4, 1.0, 0.25));

uniform vec3 bg_color;
uniform float water_line;
uniform float u_underwater;
uniform vec3 water_fog_color;
uniform float water_fog_density;
uniform float u_fog_start;
uniform float u_fog_end;
uniform vec3 u_tint;        // added color (hit flash), 0 = none

in vec3 color;
in float emissive;
in vec3 normal;
in vec3 frag_world_pos;

float sky_fog(float dist) {
    float haze = 1.0 - exp2(-0.00001 * dist * dist);
    return max(haze, smoothstep(u_fog_start, u_fog_end, dist));
}

void main() {
    vec3 col = pow(color, gamma);
    vec3 n = normalize(normal);
    // sun + sky ambient (lighter from above), close to the block face shading
    float light = 0.45 + 0.55 * max(dot(n, sun_dir), 0.0) + 0.1 * n.y;
    col = mix(col * light, col * 1.6, emissive);
    col += u_tint;

    float fog_dist = gl_FragCoord.z / gl_FragCoord.w;
    if (frag_world_pos.y < water_line) {
        float depth = water_line - frag_world_pos.y;
        col *= mix(vec3(0.25, 0.55, 1.0) * exp(-0.08 * depth), vec3(1.0), emissive * 0.5);
    }
    if (u_underwater > 0.5) {
        col *= vec3(0.45, 0.75, 1.0);
        col = mix(col, pow(water_fog_color, gamma), 1.0 - exp(-water_fog_density * fog_dist * fog_dist));
    } else {
        col = mix(col, pow(bg_color, gamma), sky_fog(fog_dist) * (1.0 - 0.5 * emissive));
    }
    fragColor = vec4(pow(col, inv_gamma), 1.0);
}
