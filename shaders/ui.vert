#version 330 core

// full-screen quad generated from gl_VertexID (draw 4 vertices as a triangle strip)
out vec2 uv;

void main() {
    vec2 p = vec2(float((gl_VertexID & 1) * 2 - 1), float((gl_VertexID >> 1) * 2 - 1));
    uv = p * 0.5 + 0.5;
    gl_Position = vec4(p, 0.0, 1.0);
}
