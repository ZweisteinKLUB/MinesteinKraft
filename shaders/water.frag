#version 330 core

#include "env.glsl"
#include "sky.glsl"
#include "lighting.glsl"
#include "waves.glsl"

layout (location = 0) out vec4 fragColor;

uniform sampler2D u_scene_color;  // opaque scene (copy): refraction and reflections
uniform sampler2D u_scene_depth;
uniform int u_ssr;                // screen space reflections on / off
uniform float u_near;
uniform float u_far;

in vec3 frag_world_pos;
in vec2 rest_xz;
in float wave_amp;

const vec3 ABSORPTION = vec3(0.40, 0.085, 0.055);   // per block: red is absorbed first
const vec3 SCATTER = vec3(0.012, 0.075, 0.085);      // color of the light scattered back by the water

float linear_depth(float d) {
    float z = d * 2.0 - 1.0;
    return 2.0 * u_near * u_far / (u_far + u_near - z * (u_far - u_near));
}

// height of the small ripples (two layers drifting with the wind)
float ripple_height(vec2 p, float t) {
    vec2 w = wind.xy * (0.6 + wind.z);
    float a = texture(u_noise, p * 0.05 + w * t * 0.006).b;
    float b = texture(u_noise, p * 0.12 - vec2(w.y, -w.x) * t * 0.009).a;
    return a * 0.6 + b * 0.4;
}

// rings of raindrops falling on the water
vec2 rain_rings(vec2 p, float t) {
    vec2 grad = vec2(0.0);
    for (int layer = 0; layer < 2; layer++) {
        vec2 q = p * (1.3 + float(layer) * 0.7) + float(layer) * 17.3;
        vec2 cell = floor(q);
        for (int j = -1; j <= 1; j++)
        for (int i = -1; i <= 1; i++) {
            vec2 c = cell + vec2(i, j);
            float h = hash12(c);
            vec2 center = c + 0.2 + 0.6 * vec2(h, hash12(c + 5.7));
            float life = fract(t * (0.9 + h * 0.6) + h * 13.0);
            vec2 d = q - center;
            float r = length(d);
            float ring = r - life * 0.9;
            float wave = sin(ring * 30.0) * exp(-ring * ring * 60.0) * (1.0 - life);
            grad += d / max(r, 1e-3) * wave;
        }
    }
    return grad;
}

// world position of the opaque surface behind a screen point
float scene_distance(vec2 uv) {
    return linear_depth(texture(u_scene_depth, uv).r);
}

// screen space reflection: rgb, a = confidence (0: use the sky)
vec4 trace_reflection(vec3 pos, vec3 r, float view_dist) {
    float t = 0.4;
    float step_len = 0.5 + view_dist * 0.02;
    vec3 prev = pos;
    for (int i = 0; i < 40; i++) {
        vec3 p = pos + r * t;
        vec4 clip = view_proj * vec4(p, 1.0);
        if (clip.w <= u_near) break;
        vec2 uv = clip.xy / clip.w * 0.5 + 0.5;
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) break;
        float scene = scene_distance(uv);
        float diff = clip.w - scene;
        if (diff > 0.0 && diff < step_len * 2.5 + 0.5) {
            // refine between the last two points
            vec3 a = prev, b = p;
            for (int k = 0; k < 5; k++) {
                vec3 m = (a + b) * 0.5;
                vec4 mc = view_proj * vec4(m, 1.0);
                vec2 muv = mc.xy / mc.w * 0.5 + 0.5;
                if (mc.w > scene_distance(muv)) b = m; else a = m;
            }
            vec4 hc = view_proj * vec4(b, 1.0);
            vec2 huv = hc.xy / hc.w * 0.5 + 0.5;
            if (texture(u_scene_depth, huv).r >= 1.0) break;  // the sky: analytic is better
            vec2 border = smoothstep(0.0, 0.08, huv) * smoothstep(1.0, 0.92, huv);
            float fade = border.x * border.y * (1.0 - float(i) / 40.0);
            return vec4(texture(u_scene_color, huv).rgb, fade);
        }
        prev = p;
        t += step_len;
        step_len *= 1.12;
    }
    return vec4(0.0);
}

void main() {
    vec3 pos = frag_world_pos;
    vec3 to_cam = camera.xyz - pos;
    float view_dist = length(to_cam);
    vec3 v = to_cam / view_dist;
    float t = zenith.w;
    vec2 screen_uv = gl_FragCoord.xy / screen.xy;

    // ---------------------------------------------------------------- normal
    vec3 n;
    gerstner(rest_xz, wave_amp, t, n);
    float e = 0.08;
    float h0 = ripple_height(rest_xz, t);
    vec2 slope = vec2(ripple_height(rest_xz + vec2(e, 0.0), t) - h0,
                      ripple_height(rest_xz + vec2(0.0, e), t) - h0) / e;
    float ripple = (0.05 + 0.2 * wind.z) * (1.0 - smoothstep(20.0, 120.0, view_dist) * 0.8);
    slope *= ripple;
    float rain_here = weather.x * (1.0 - weather.y) * smoothstep(40.0, 5.0, view_dist);
    if (rain_here > 0.01) slope += rain_rings(rest_xz, t) * rain_here * 0.35;
    n = normalize(n + vec3(-slope.x, 0.0, -slope.y));

    // ---------------------------------------------------------------- under water: surface from below
    if (fog_params.z > 0.5) {
        vec3 nd = -n;  // facing down to the camera
        float cos_i = saturate(dot(v, nd));
        // inside Snell's window (~49 degrees): the world above; outside: total internal reflection
        vec2 uv = screen_uv + nd.xz * 0.03;
        vec3 above = texture(u_scene_color, uv).rgb * 0.85 + water_fog.rgb * 0.3;
        above += light_color.rgb * pow(saturate(dot(-v, light_dir.xyz)), 60.0) * 2.0;
        vec3 reflected = water_fog.rgb * 1.15;
        vec3 col = mix(reflected, above, smoothstep(0.6, 0.72, cos_i));
        fragColor = vec4(apply_fog(col, pos), 1.0);
        return;
    }

    // ---------------------------------------------------------------- refraction
    float shadow = shadow_factor(pos, vec3(0.0, 1.0, 0.0)) * cloud_shadow(pos);
    float water_dist = linear_depth(gl_FragCoord.z);  // view depth, like the scene depths
    float thickness = max(scene_distance(screen_uv) - water_dist, 0.0);
    vec2 refr_uv = screen_uv + n.xz * 0.035 * saturate(thickness * 0.5);
    float refr_thickness = scene_distance(refr_uv) - water_dist;
    if (refr_thickness < 0.0) {  // the distorted lookup hit something in front of the water
        refr_uv = screen_uv;
    } else {
        thickness = refr_thickness;
    }
    // the light crosses the depth of water twice: down to the floor and back up along the view
    float depth_below = thickness * (1.0 + saturate(v.y));
    vec3 transmit = exp(-ABSORPTION * depth_below);
    vec3 floor_col = texture(u_scene_color, refr_uv).rgb;
    vec3 lit = ambient_sky.rgb * 0.9 + light_color.rgb * saturate(light_dir.y) * shadow * 0.7;
    vec3 scatter = SCATTER * lit;
    vec3 refracted = floor_col * transmit + scatter * (1.0 - transmit);

    // ---------------------------------------------------------------- reflection
    vec3 r = reflect(-v, n);
    r.y = abs(r.y);  // waves never reflect below the horizon
    float fresnel = fresnel_schlick(dot(n, v), 0.02);
    vec4 cl = sky_clouds(r);
    vec3 reflected = mix(sky_radiance(r), cl.rgb, cl.a);
    if (u_ssr == 1) {
        vec4 hit = trace_reflection(pos, r, view_dist);
        reflected = mix(reflected, hit.rgb, hit.a);
    }

    // ---------------------------------------------------------------- sun glints
    float rough = 0.06 + 0.1 * wind.z;
    vec3 h = normalize(v + light_dir.xyz);
    vec3 glint = light_color.rgb * ggx_specular(n, v, light_dir.xyz, rough)
               * fresnel_schlick(dot(h, v), 0.02) * shadow;

    vec3 col = mix(refracted, reflected, fresnel) + glint;

    // ---------------------------------------------------------------- foam
    float foam_noise = texture(u_noise, rest_xz * 0.35 + wind.xy * t * 0.02).b;
    float shore = 1.0 - smoothstep(0.0, 0.9, thickness + foam_noise * 0.6 - 0.25 * sin(t * 1.3 + rest_xz.x * 0.4));
    float crest = smoothstep(0.7, 1.0, (pos.y - fog_params.w) / max(wind.w * 1.1, 0.01)) * smoothstep(0.4, 0.9, wind.z);
    float foam = saturate(max(shore * 0.8, crest * 0.7) * smoothstep(0.45, 0.75, foam_noise + 0.15));
    vec3 foam_col = vec3(0.85, 0.9, 0.92) * (lit + light_color.rgb * saturate(light_dir.y) * shadow * 0.3);
    col = mix(col, foam_col, foam);

    col = apply_fog(col, pos);
    fragColor = vec4(col, 1.0);
}
