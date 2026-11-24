#version 330 core

layout (location = 0) in vec2 in_tex_coord;
layout (location = 1) in vec3 in_position;

uniform mat4 m_proj;
uniform mat4 m_view;
uniform int water_area;
uniform float water_line;
uniform vec2 u_center;  // follows the camera (snapped to whole blocks)

out vec2 uv;


void main() {
    vec3 pos = in_position;
    pos.xz = (pos.xz - 0.5) * float(water_area) + u_center;
    pos.y += water_line;
    uv = pos.xz;  // anchored to the world: the texture does not slide with the camera
    gl_Position = m_proj * m_view * vec4(pos, 1.0);
}
