#version 330 core

layout (location = 0) in vec2 in_tex_coord_0;
layout (location = 1) in vec3 in_position;

uniform mat4 m_proj;
uniform mat4 m_view;
uniform mat4 m_model;

out vec2 uv;

void main() {
    uv = in_tex_coord_0;
    // slightly larger than the block to avoid z-fighting, smaller than the marker frame
    gl_Position = m_proj * m_view * m_model * vec4((in_position - 0.5) * 1.004 + 0.5, 1.0);
}
