#version 330 core

layout (location = 0) out vec4 fragColor;

in vec2 uv;
in float alpha;
flat in int kind;
in vec3 tint;

void main() {
    float a;
    if (kind == 0) {        // rain streak: thin, brighter in the middle
        a = (1.0 - abs(uv.x)) * (1.0 - uv.y * uv.y);
    } else if (kind == 1) { // snow flake: soft disk
        a = 1.0 - smoothstep(0.35, 1.0, length(uv));
    } else {                // splash: thin ring
        float r = length(uv);
        a = smoothstep(0.65, 0.85, r) * (1.0 - smoothstep(0.85, 1.0, r));
    }
    a *= alpha;
    if (a < 0.004) discard;
    fragColor = vec4(tint, a);
}
