#version 330 core

// light shafts: the bright sky around the sun, blurred radially towards the sun
layout (location = 0) out vec4 fragColor;

uniform sampler2D u_hdr;
uniform sampler2D u_depth;
uniform vec2 u_light_uv;    // light position on the screen
uniform float u_jitter;

in vec2 uv;

const int SAMPLES = 40;

void main() {
    vec2 delta = (u_light_uv - uv) / float(SAMPLES) * 0.9;
    float offset = fract(sin(dot(uv, vec2(12.9898, 78.233)) + u_jitter) * 43758.5453);
    vec2 p = uv + delta * offset;
    vec3 sum = vec3(0.0);
    float weight = 1.0;
    for (int i = 0; i < SAMPLES; i++) {
        float sky = step(0.99999, texture(u_depth, p).r);
        vec3 c = min(texture(u_hdr, p).rgb, vec3(12.0));
        sum += c * sky * weight;
        weight *= 0.965;
        p += delta;
    }
    fragColor = vec4(sum / float(SAMPLES), 1.0);
}
