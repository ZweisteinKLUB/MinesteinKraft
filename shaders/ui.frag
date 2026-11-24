#version 330 core

layout (location = 0) out vec4 fragColor;

in vec2 uv;
uniform sampler2D u_ui;

void main() {
    fragColor = texture(u_ui, uv);
}
