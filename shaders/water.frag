#version 330 core

layout (location = 0) out vec4 fragColor;

const vec3 gamma = vec3(2.2);
const vec3 inv_gamma = 1.0 / gamma;

in vec2 uv;

uniform sampler2D u_texture_0;
uniform float water_line;
uniform float u_underwater;
uniform vec3 water_fog_color;
uniform float water_fog_density;

void main() {
    vec3 tex_col = texture(u_texture_0, uv).rgb;
    tex_col = pow(tex_col, gamma);
    float fog_dist = gl_FragCoord.z / gl_FragCoord.w;
    float alpha;

    if (u_underwater > 0.5) {
        // surface seen from below: bright, rippled, fading into the water fog
        tex_col = mix(tex_col, vec3(0.35, 0.7, 0.85), 0.6);
        float fog = 1.0 - exp(-water_fog_density * fog_dist * fog_dist);
        tex_col = mix(tex_col, pow(water_fog_color, gamma), fog);
        alpha = mix(0.75, 1.0, fog);
    } else {
        alpha = mix(0.5, 0.0, 1.0 - exp(-0.000002 * fog_dist * fog_dist));
    }

    tex_col = pow(tex_col, inv_gamma);
    fragColor = vec4(tex_col, alpha);
}
