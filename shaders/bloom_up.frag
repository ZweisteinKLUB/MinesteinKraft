#version 330 core

// 3x3 tent upsample, added (blending) to the next larger level
layout (location = 0) out vec4 fragColor;

uniform sampler2D u_source;
uniform vec2 u_texel;
uniform float u_radius;

in vec2 uv;

void main() {
    vec2 o = u_texel * u_radius;
    vec3 col = texture(u_source, uv).rgb * 4.0;
    col += (texture(u_source, uv + vec2(-o.x, 0)).rgb + texture(u_source, uv + vec2(o.x, 0)).rgb
          + texture(u_source, uv + vec2(0, -o.y)).rgb + texture(u_source, uv + vec2(0, o.y)).rgb) * 2.0;
    col += texture(u_source, uv + vec2(-o.x, -o.y)).rgb + texture(u_source, uv + vec2(o.x, -o.y)).rgb
         + texture(u_source, uv + vec2(-o.x, o.y)).rgb + texture(u_source, uv + vec2(o.x, o.y)).rgb;
    fragColor = vec4(col / 16.0, 1.0);
}
