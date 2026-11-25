#version 330 core

#include "env.glsl"
#include "sky.glsl"
#include "lighting.glsl"

layout (location = 0) out vec4 fragColor;

uniform vec3 u_tint;        // added color (hit flash), 0 = none
uniform int u_shadow_pass;  // 1: drawing into a shadow map (depth only)

in vec3 color;
in float emissive;
in vec3 normal;
in vec3 frag_world_pos;

void main() {
    if (u_shadow_pass == 1) {
        fragColor = vec4(1.0);
        return;
    }
    vec3 albedo = color;  // glTF vertex colors are linear
    vec3 n = normalize(normal);
    vec3 pos = frag_world_pos;
    vec3 v = normalize(camera.xyz - pos);
    vec3 l = light_dir.xyz;
    float water_depth = fog_params.w - pos.y;

    float sky_vis = sky_visibility(pos, vec3(0.0, 1.0, 0.0));
    float ndl = dot(n, l);
    float shadow = ndl > 0.0 ? shadow_factor(pos, n) * cloud_shadow(pos) : 0.0;
    vec3 direct = light_color.rgb * saturate(ndl) * shadow;
    // wet skin and stone shine a little in the rain
    float rough = mix(0.7, 0.3, weather.z * sky_exposure(pos, vec3(0.0, 1.0, 0.0)));
    vec3 h = normalize(v + l);
    vec3 specular = light_color.rgb * ggx_specular(n, v, l, rough) * fresnel_schlick(dot(h, v), 0.04) * shadow;
    // soft wrap light on the dark side: bodies are rounder than blocks
    vec3 ambient = ambient_light(n, sky_vis) * (0.75 + 0.25 * saturate(n.y));

    vec3 col = albedo * (direct + ambient + flash_light(n, sky_vis)) + specular;
    if (water_depth > 0.0) col *= exp(-vec3(0.42, 0.11, 0.06) * water_depth);
    col = mix(col, albedo * 6.0, emissive);  // glowing parts (eyes)
    col += u_tint * (light_color.rgb + ambient_sky.rgb + 0.2);
    col = apply_fog(col, pos);
    fragColor = vec4(col, 1.0);
}
