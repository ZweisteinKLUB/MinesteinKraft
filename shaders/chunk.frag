#version 330 core

#include "env.glsl"
#include "sky.glsl"
#include "lighting.glsl"

layout (location = 0) out vec4 fragColor;

uniform sampler2DArray u_texture_array_0;
uniform int u_shadow_pass;  // 1: drawing into a shadow map (depth only)

in vec2 uv;
in float ao;
in vec3 frag_world_pos;

flat in int face_id;
flat in int voxel_id;

const vec3 FACE_NORMALS[6] = vec3[6](
    vec3(0, 1, 0), vec3(0, -1, 0), vec3(1, 0, 0), vec3(-1, 0, 0), vec3(0, 0, -1), vec3(0, 0, 1)
);
// per block id: air, sand, grass, dirt, stone, snow, leaves, wood
const float ROUGHNESS[8] = float[8](1.0, 0.9, 0.8, 0.92, 0.6, 0.5, 0.65, 0.75);
const float POROSITY[8] = float[8](0.0, 0.9, 0.6, 0.85, 0.35, 0.1, 0.4, 0.5);  // darkens when wet
const int LEAVES_ID = 6;
const vec3 SNOW_ALBEDO = vec3(0.86, 0.9, 0.96);


// moving light pattern of sunlight refracted by waves
float caustics(vec2 p, float t) {
    float a = sin(p.x * 1.7 + t * 1.3) * sin(p.y * 1.3 - t * 0.9);
    float b = sin((p.x + p.y) * 0.9 - t * 1.1) * sin((p.x - p.y) * 1.1 + t * 0.7);
    return pow(abs(a + b) * 0.5, 2.0);
}

void main() {
    if (u_shadow_pass == 1) {
        fragColor = vec4(1.0);
        return;
    }
    vec2 face_uv = uv;
    face_uv.x = uv.x / 3.0 - float(min(face_id, 2)) / 3.0;
    vec3 albedo = srgb_to_linear(texture(u_texture_array_0, vec3(face_uv, float(voxel_id))).rgb);

    vec3 pos = frag_world_pos;
    vec3 n = FACE_NORMALS[face_id];
    vec3 v = normalize(camera.xyz - pos);
    float rough = ROUGHNESS[voxel_id & 7];
    float water_depth = fog_params.w - pos.y;  // > 0 under the sea

    float sky_vis = sky_visibility(pos, n);
    float exposed = sky_exposure(pos, n) * step(water_depth, 0.0);

    // ---------------------------------------------------------------- weather on the ground
    float top = smoothstep(0.5, 0.9, n.y);
    float patches = texture(u_noise, pos.xz * 0.045).g;
    float snow = top * exposed * smoothstep(patches * 0.55, patches * 0.55 + 0.2, weather.w);
    float wet = weather.z * exposed * mix(0.6, 1.0, top) * (1.0 - snow);
    float puddle = top * wet * smoothstep(0.55, 0.6, texture(u_noise, pos.xz * 0.03 + 0.5).r);

    albedo = mix(albedo, SNOW_ALBEDO, snow);
    albedo *= mix(1.0, 0.45, wet * POROSITY[voxel_id & 7]);
    albedo *= mix(1.0, 0.45, puddle);
    rough = mix(rough, 0.5, snow);
    rough = mix(rough, 0.18, wet * 0.8);
    rough = mix(rough, 0.03, puddle);

    // ---------------------------------------------------------------- direct light
    vec3 l = light_dir.xyz;
    float ndl = dot(n, l);
    float sun_shadow = cloud_shadow(pos);
    float shadow = ndl > 0.0 ? shadow_factor(pos, n) * sun_shadow : 0.0;
    vec3 direct = light_color.rgb * saturate(ndl) * shadow * mix(1.0, ao, 0.35);

    vec3 h = normalize(v + l);
    float f0 = mix(0.03, 0.02, wet);
    float fresnel_l = fresnel_schlick(dot(h, v), f0);
    vec3 specular = light_color.rgb * ggx_specular(n, v, l, max(rough, 0.04)) * fresnel_l * shadow;

    // leaves let some light through
    vec3 translucent = vec3(0.0);
    if (voxel_id == LEAVES_ID) {
        float back = pow(saturate(dot(-v, l)), 4.0) * 0.6 + saturate(-ndl) * 0.25;
        translucent = light_color.rgb * vec3(0.9, 1.0, 0.5) * back * sun_shadow * sky_vis;
    }

    // ---------------------------------------------------------------- indirect light
    vec3 ambient = ambient_light(n, sky_vis) * ao;
    vec3 flash = flash_light(n, sky_vis) * ao;

    // sky reflected by smooth (wet) surfaces
    vec3 r = reflect(-v, n);
    float fresnel_v = fresnel_schlick(dot(n, v), f0);
    float smooth_ = (1.0 - rough) * (1.0 - rough);
    vec3 reflection = sky_radiance(r) * max(fresnel_v, 0.1 * puddle) * smooth_ * sky_vis * ao;

    // under the sea: light absorbed on its way down, caustics
    if (water_depth > 0.0) {
        vec3 absorb = exp(-vec3(0.42, 0.11, 0.06) * water_depth);
        float c = caustics(pos.xz, zenith.w) * exp(-0.12 * water_depth);
        direct = direct * absorb * (0.7 + 2.5 * c);
        direct += light_color.rgb * absorb * c * 0.4 * saturate(n.y) * sun_shadow;
        ambient *= exp(-vec3(0.28, 0.08, 0.04) * water_depth);
        specular *= absorb;
        reflection *= 0.0;
    }

    vec3 col = albedo * (direct + ambient + flash + translucent) + specular + reflection;
    col = apply_fog(col, pos);
    fragColor = vec4(col, 1.0);
}
