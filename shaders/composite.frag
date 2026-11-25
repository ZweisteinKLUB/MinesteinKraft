#version 330 core

#include "env.glsl"

// HDR -> display: bloom, light shafts, exposure, ACES filmic curve, grading, vignette, sRGB
layout (location = 0) out vec4 fragColor;

uniform sampler2D u_hdr;
uniform sampler2D u_bloom;
uniform sampler2D u_godrays;
uniform float u_bloom_strength;
uniform float u_godray_strength;
uniform vec3 u_godray_tint;

in vec2 uv;

// ACES fitted (Stephen Hill)
const mat3 ACES_IN = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
const mat3 ACES_OUT = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);

vec3 rrt_odt(vec3 v) {
    vec3 a = v * (v + 0.0245786) - 0.000090537;
    vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081;
    return a / b;
}

vec3 aces(vec3 c) { return clamp(ACES_OUT * rrt_odt(ACES_IN * c), 0.0, 1.0); }

void main() {
    vec3 hdr = texture(u_hdr, uv).rgb;
    vec3 bloom = texture(u_bloom, uv).rgb;
    hdr += bloom * u_bloom_strength;
    hdr += texture(u_godrays, uv).rgb * u_godray_tint * u_godray_strength;

    vec3 col = hdr * camera.w * 0.85;  // exposure

    // grading: grey storms, cooler nights (the eye loses colors in the dark)
    float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
    float sat = 1.0 - 0.3 * ambient_sky.w * horizon.w - 0.35 * (1.0 - smoothstep(0.0, 0.15, sun_dir.y + 0.05));
    col = mix(vec3(l), col, sat);
    col = aces(col);

    // vignette
    vec2 d = uv - 0.5;
    col *= 1.0 - 0.28 * dot(d, d) * 2.0;

    col = pow(col, vec3(1.0 / 2.2));
    col += (ign(gl_FragCoord.xy) - 0.5) / 255.0;  // dithering: no banding in the sky
    float luma = dot(col, vec3(0.299, 0.587, 0.114));
    fragColor = vec4(col, luma);
}
