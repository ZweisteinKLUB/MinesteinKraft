#version 330 core

#include "env.glsl"
#include "sky.glsl"

layout (location = 0) out vec4 fragColor;

in vec2 uv;

const float SUN_RADIUS = 0.0125;   // radians (drawn a bit larger than the real sun)
const float MOON_RADIUS = 0.030;

vec3 sun_disk_color(vec3 dir) {
    float mu = dot(dir, sun_dir.xyz);
    float r = acos(clamp(mu, -1.0, 1.0)) / SUN_RADIUS;
    if (r > 1.0) return vec3(0.0);
    float limb = 1.0 - 0.6 * (1.0 - sqrt(max(1.0 - r * r, 0.0)));  // limb darkening
    return sun_disk.rgb * limb * smoothstep(1.0, 0.85, r);
}

vec3 moon_color(vec3 dir) {
    vec3 m = moon_dir.xyz;
    vec3 right = normalize(cross(m, abs(m.y) > 0.99 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0)));
    vec3 up = cross(right, m);
    vec2 q = vec2(dot(dir, right), dot(dir, up)) / MOON_RADIUS;
    float rr = dot(q, q);
    if (dot(dir, m) < 0.0 || rr > 1.0) return vec3(0.0);
    // a lit sphere: the phase comes from the direction of the sun
    vec3 nrm = q.x * right + q.y * up - sqrt(1.0 - rr) * m;
    float lit = smoothstep(-0.05, 0.15, dot(nrm, sun_dir.xyz));
    float maria = texture(u_noise, q * 0.18 + 0.4).g;
    float albedo = mix(0.55, 1.05, smoothstep(0.35, 0.65, maria)) * (0.92 + 0.08 * texture(u_noise, q * 0.7).b);
    vec3 col = vec3(1.0, 0.97, 0.9) * 1.4 * albedo * (lit + 0.012);  // + earthshine
    return col * smoothstep(1.0, 0.92, rr);
}

vec3 stars(vec3 dir) {
    vec3 c = transpose(mat3(sky_rot)) * dir;  // world -> celestial sphere
    vec3 p = c * 260.0;
    vec3 cell = floor(p);
    float h = hash13(cell);
    if (h < 0.982) return vec3(0.0);
    vec3 star = cell + 0.25 + 0.5 * hash33(cell + 7.1);
    float pixel = length(fwidth(p));
    float d = length(p - star);
    float b = pow((h - 0.982) / 0.018, 4.0) * 1.2 + 0.04;
    float twinkle = 0.75 + 0.25 * sin(zenith.w * (2.0 + 5.0 * h) + h * 400.0);
    vec3 tint = mix(vec3(0.7, 0.8, 1.0), vec3(1.0, 0.85, 0.7), hash13(cell + 3.3));
    float shape = smoothstep(1.0 * pixel, 0.0, d);
    return tint * b * twinkle * shape * smoothstep(-0.02, 0.25, dir.y);
}

// faint band of the milky way
vec3 milky_way(vec3 dir) {
    vec3 c = transpose(mat3(sky_rot)) * dir;
    float band = exp(-pow(dot(c, normalize(vec3(0.3, 0.2, 1.0))) * 4.0, 2.0));
    float clumps = texture(u_noise, vec2(atan(c.x, c.y) * 0.6, c.z * 0.8)).g;
    return vec3(0.55, 0.6, 0.8) * band * smoothstep(0.35, 0.8, clumps) * 0.012 * smoothstep(0.0, 0.3, dir.y);
}

void main() {
    vec4 clip = vec4(uv * 2.0 - 1.0, 1.0, 1.0);
    vec4 world = inv_view_proj * clip;
    vec3 dir = normalize(world.xyz / world.w - camera.xyz);

    if (fog_params.z > 0.5 && dir.y < 0.0) {  // under water, looking down: the deep water
        fragColor = vec4(water_fog.rgb, 1.0);
        return;
    }

    vec3 col = sky_radiance(dir);
    float night = moon_dir.w;
    col += (stars(dir) + milky_way(dir)) * night;
    col += moon_color(dir);
    col += sun_disk_color(dir) * (1.0 - overcast());

    vec4 cl = sky_clouds(dir);
    col = mix(col, cl.rgb, cl.a);

    // the weather fog and the rain veil hide the horizon
    float veil = saturate(fog_color.w * 1.2) * (1.0 - smoothstep(-0.05, 0.5, dir.y));
    veil = max(veil, weather.x * 0.55 * (1.0 - smoothstep(0.0, 0.35, dir.y)));
    col = mix(col, fog_tint(dir), veil);
    fragColor = vec4(col, 1.0);
}
