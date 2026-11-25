#version 330 core

#include "env.glsl"
#include "waves.glsl"

// grid in [-1, 1]^2, denser near the camera
layout (location = 0) in vec2 in_grid;

uniform mat4 m_proj;
uniform mat4 m_view;
uniform float u_radius;      // blocks covered around the camera
uniform vec2 u_center;       // follows the camera (snapped to whole blocks)
uniform sampler2D u_heightmap;

out vec3 frag_world_pos;
out vec2 rest_xz;      // undisplaced position (normals are recomputed per pixel)
out float wave_amp;    // local wave scale (calm near the shore and far away)

float column_top(vec2 xz) {
    ivec2 c = ivec2(floor(xz)) & (int(screen.z) - 1);
    return texelFetch(u_heightmap, c, 0).r * 255.0;
}

void main() {
    vec2 g = in_grid * (0.12 + 0.88 * abs(in_grid));
    vec2 xz = u_center + g * u_radius;
    float dist = length(xz - camera.xz);

    // waves break down in shallow water, and fade far away (the normals keep the detail)
    float depth = fog_params.w - column_top(xz);
    float amp = smoothstep(0.0, 3.5, depth) * (1.0 - smoothstep(60.0, 160.0, dist));
    vec3 n;
    vec3 offset = gerstner(xz, amp, zenith.w, n);

    vec3 pos = vec3(xz.x, fog_params.w, xz.y) + offset;
    frag_world_pos = pos;
    rest_xz = xz;
    wave_amp = amp;
    gl_Position = m_proj * m_view * vec4(pos, 1.0);
}
