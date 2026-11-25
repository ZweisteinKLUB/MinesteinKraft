#version 330 core

// one triangle covering the screen (draw 3 vertices), at the far plane
out vec2 uv;

void main() {
    vec2 p = vec2(float((gl_VertexID & 1) << 2) - 1.0, float((gl_VertexID & 2) << 1) - 1.0);
    uv = p * 0.5 + 0.5;
    gl_Position = vec4(p, 1.0, 1.0);
}
