#version 330 core

layout (location = 0) out vec4 fragColor;

uniform float u_brightness;  // flicker of the bolt

in float edge;
in float intensity;

void main() {
    float core = exp(-edge * edge * 6.0);
    vec3 col = vec3(0.8, 0.85, 1.0) * core * intensity * u_brightness * 60.0;
    fragColor = vec4(col, 1.0);  // additive
}
