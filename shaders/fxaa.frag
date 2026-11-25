#version 330 core

// FXAA (simplified, after Timothy Lottes): smooths the jagged edges of the blocks
layout (location = 0) out vec4 fragColor;

uniform sampler2D u_ldr;    // rgb + luma in alpha
uniform vec2 u_texel;

in vec2 uv;

void main() {
    vec4 c = texture(u_ldr, uv);
    float lm = c.a;
    float ln = textureOffset(u_ldr, uv, ivec2(0, 1)).a;
    float ls = textureOffset(u_ldr, uv, ivec2(0, -1)).a;
    float le = textureOffset(u_ldr, uv, ivec2(1, 0)).a;
    float lw = textureOffset(u_ldr, uv, ivec2(-1, 0)).a;
    float lne = textureOffset(u_ldr, uv, ivec2(1, 1)).a;
    float lnw = textureOffset(u_ldr, uv, ivec2(-1, 1)).a;
    float lse = textureOffset(u_ldr, uv, ivec2(1, -1)).a;
    float lsw = textureOffset(u_ldr, uv, ivec2(-1, -1)).a;
    float lo = min(lm, min(min(ln, ls), min(le, lw)));
    float hi = max(lm, max(max(ln, ls), max(le, lw)));
    float range = hi - lo;
    if (range < max(0.0312, hi * 0.125)) {
        fragColor = vec4(c.rgb, 1.0);
        return;
    }
    vec2 dir;
    dir.x = -((lnw + lne) - (lsw + lse));
    dir.y = ((lnw + lsw) - (lne + lse));
    float reduce = max((lnw + lne + lsw + lse) * 0.03125, 1.0 / 128.0);
    float rcp = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
    dir = clamp(dir * rcp, vec2(-8.0), vec2(8.0)) * u_texel;
    vec3 a = 0.5 * (texture(u_ldr, uv + dir * (1.0 / 3.0 - 0.5)).rgb + texture(u_ldr, uv + dir * (2.0 / 3.0 - 0.5)).rgb);
    vec3 b = a * 0.5 + 0.25 * (texture(u_ldr, uv + dir * -0.5).rgb + texture(u_ldr, uv + dir * 0.5).rgb);
    float lb = dot(b, vec3(0.299, 0.587, 0.114));
    fragColor = vec4((lb < lo || lb > hi) ? a : b, 1.0);
}
