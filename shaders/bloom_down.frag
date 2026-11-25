#version 330 core

// 13-tap downsample (Jimenez 2014); the first pass keeps only the bright parts
layout (location = 0) out vec4 fragColor;

uniform sampler2D u_source;
uniform vec2 u_texel;       // 1 / source size
uniform int u_first;
uniform float u_threshold;  // in exposed units

in vec2 uv;

vec3 tap(vec2 o) { return texture(u_source, uv + o * u_texel).rgb; }

float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

vec3 prefilter(vec3 c) {
    float l = luma(c);
    float knee = u_threshold * 0.5;
    float soft = clamp(l - u_threshold + knee, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee + 1e-5);
    float contrib = max(soft, l - u_threshold) / max(l, 1e-5);
    return c * contrib / (1.0 + l * 0.02);  // tames single very bright pixels (fireflies)
}

void main() {
    vec3 a = tap(vec2(-2, 2)), b = tap(vec2(0, 2)), c = tap(vec2(2, 2));
    vec3 d = tap(vec2(-2, 0)), e = tap(vec2(0, 0)), f = tap(vec2(2, 0));
    vec3 g = tap(vec2(-2, -2)), h = tap(vec2(0, -2)), i = tap(vec2(2, -2));
    vec3 j = tap(vec2(-1, 1)), k = tap(vec2(1, 1)), l = tap(vec2(-1, -1)), m = tap(vec2(1, -1));
    vec3 col = e * 0.125 + (a + c + g + i) * 0.03125 + (b + d + f + h) * 0.0625 + (j + k + l + m) * 0.125;
    if (u_first == 1) col = prefilter(col);
    fragColor = vec4(max(col, 0.0), 1.0);
}
