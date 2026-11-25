#version 330 core

#include "env.glsl"

layout (location = 0) out vec4 fragColor;

in vec2 uv;

uniform sampler2DArray u_cracks;
uniform float stage;

void main() {
    vec4 crack = texture(u_cracks, vec3(uv, stage));
    if (crack.a < 0.1) discard;
    // lit like the block under it (roughly), so it does not glow at night
    vec3 light = ambient_sky.rgb + light_color.rgb * 0.5 + vec3(ambient_ground.w);
    fragColor = vec4(srgb_to_linear(crack.rgb) * light, crack.a);
}
