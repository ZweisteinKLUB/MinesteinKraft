#version 330 core

layout (location = 0) in vec3 in_position;

uniform mat4 m_proj;
uniform mat4 m_view;
uniform vec2 u_origin;  // cell coordinates of the mesh origin (mesh follows the player)
uniform float u_time;
uniform float cloud_scale;

void main() {
    vec3 pos = vec3(in_position);
    pos.xz = (pos.xz + u_origin) * cloud_scale;

    float time = 300.0 * sin(0.01 * u_time);
    pos.xz += time;
    gl_Position = m_proj * m_view * vec4(pos, 1.0);
}
