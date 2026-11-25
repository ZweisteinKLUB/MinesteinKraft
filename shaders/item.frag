#version 330 core

#include "env.glsl"
#include "sky.glsl"
#include "lighting.glsl"

layout (location = 0) out vec4 fragColor;

uniform sampler2DArray u_texture_array_0;
uniform int u_shadow_pass;  // 1: drawing into a shadow map (depth only)

in vec2 uv;
in vec3 normal;
in vec3 frag_world_pos;
flat in int face_id;
flat in int voxel_id;

void main() {
    if (u_shadow_pass == 1) {
        fragColor = vec4(1.0);
        return;
    }
    // same layout of the block textures as chunk.frag: top, side, bottom per layer
    vec2 face_uv = uv;
    face_uv.x = uv.x / 3.0 - float(min(face_id, 2)) / 3.0;
    vec3 albedo = srgb_to_linear(texture(u_texture_array_0, vec3(face_uv, float(voxel_id))).rgb);

    vec3 pos = frag_world_pos;
    vec3 n = normalize(normal);
    vec3 v = normalize(camera.xyz - pos);
    vec3 l = light_dir.xyz;
    float water_depth = fog_params.w - pos.y;

    float sky_vis = sky_visibility(pos, vec3(0.0, 1.0, 0.0));
    float ndl = dot(n, l);
    float shadow = ndl > 0.0 ? shadow_factor(pos, n) * cloud_shadow(pos) : 0.0;
    vec3 direct = light_color.rgb * saturate(ndl) * shadow;
    vec3 h = normalize(v + l);
    vec3 specular = light_color.rgb * ggx_specular(n, v, l, 0.6) * fresnel_schlick(dot(h, v), 0.03) * shadow;
    vec3 ambient = ambient_light(n, sky_vis);

    vec3 col = albedo * (direct + ambient + flash_light(n, sky_vis)) + specular;
    if (water_depth > 0.0) col *= exp(-vec3(0.42, 0.11, 0.06) * water_depth);
    col = apply_fog(col, pos);
    fragColor = vec4(col, 1.0);
}
