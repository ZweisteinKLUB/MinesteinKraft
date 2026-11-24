#version 330 core

layout (location = 0) out vec4 fragColor;

in vec2 uv;

uniform sampler2DArray u_cracks;
uniform float stage;

void main() {
    vec4 crack = texture(u_cracks, vec3(uv, stage));
    if (crack.a < 0.1) discard;
    fragColor = crack;
}
