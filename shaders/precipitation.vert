#version 330 core

#include "env.glsl"

// Rain drops, snow flakes and splashes, all positioned here from gl_InstanceID (no CPU work).
// Draw 6 vertices per instance.

uniform mat4 m_proj;
uniform mat4 m_view;
uniform int u_mode;            // 0: falling drops / flakes, 1: splashes on the ground
uniform sampler2D u_heightmap;

out vec2 uv;
out float alpha;
flat out int kind;             // 0 rain, 1 snow, 2 splash
out vec3 tint;

const vec2 CORNERS[6] = vec2[6](vec2(-1, -1), vec2(1, -1), vec2(1, 1), vec2(-1, -1), vec2(1, 1), vec2(-1, 1));

float column_top(vec2 xz) {
    ivec2 c = ivec2(floor(xz)) & (int(screen.z) - 1);
    return texelFetch(u_heightmap, c, 0).r * 255.0;
}

float wrap(float v, float r) { return mod(v + r, 2.0 * r) - r; }

void hide() { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); alpha = 0.0; }

void main() {
    int id = gl_InstanceID;
    vec2 corner = CORNERS[gl_VertexID];
    uv = corner;
    vec3 rnd = hash33(vec3(float(id) * 0.137, float(id) * 1.731, 3.17));
    vec3 rnd2 = hash33(rnd * 91.7 + 1.3);
    float t = zenith.w;
    float R = clouds.w;
    vec3 cam = camera.xyz;
    vec3 light = ambient_sky.rgb + light_color.rgb * 0.35 + vec3(0.75, 0.8, 1.0) * sun_disk.w * 2.0;

    if (rnd2.z > weather.x) { hide(); return; }  // intensity: fewer particles

    if (u_mode == 1) {
        // splash: a ring growing where a drop hits (on the ground or the sea)
        float life = fract(t * (1.6 + rnd.z) + rnd2.x);
        float cycle = floor(t * (1.6 + rnd.z) + rnd2.x);
        vec2 jitter = hash33(vec3(rnd.xy * 17.0, cycle)).xy;
        vec2 xz = cam.xz + (fract(rnd.xy + jitter) * 2.0 - 1.0) * R * 0.55;
        float ground = max(column_top(xz), fog_params.w);
        if (weather.y > rnd.z || ground > screen.w || ground < cam.y - R) { hide(); return; }
        float size = 0.03 + 0.08 * life;
        vec3 p = vec3(xz.x + corner.x * size, ground + 0.03, xz.y + corner.y * size);
        kind = 2;
        alpha = (1.0 - life) * 0.22;
        tint = light;
        gl_Position = m_proj * m_view * vec4(p, 1.0);
        return;
    }

    // falling particle, anchored in the world, wrapped in a box around the camera
    bool snow_weather = weather.y > rnd.z;
    float speed_rain = 10.0 + 3.0 * rnd.x;
    float speed_snow = 1.1 + 0.6 * rnd.y;
    vec2 drift_rain = wind.xy * wind.z * 5.0;
    vec2 drift_snow = wind.xy * (0.4 + wind.z * 2.0);

    float H = R * 1.6;
    float y_snow = cam.y + wrap(rnd.y * 2.0 * H - t * speed_snow - cam.y, H * 0.5) + H * 0.15;
    bool is_snow = snow_weather || y_snow > screen.w;
    float speed = is_snow ? speed_snow : speed_rain;
    vec2 drift = is_snow ? drift_snow : drift_rain;
    float y = is_snow ? y_snow : cam.y + wrap(rnd.y * 2.0 * H - t * speed - cam.y, H * 0.5) + H * 0.15;
    vec2 xz = rnd.xz * 4.0 * R + drift * t;
    if (is_snow) xz += vec2(sin(t * 1.3 + rnd.x * 40.0), cos(t * 1.1 + rnd.z * 40.0)) * 0.35;
    xz = cam.xz + vec2(wrap(xz.x - cam.xz.x, R), wrap(xz.y - cam.xz.y, R));
    vec3 p = vec3(xz.x, y, xz.y);

    if (p.y < column_top(p.xz) || p.y < fog_params.w) { hide(); return; }  // sheltered / in the sea

    vec3 to_cam = cam - p;
    float dist = length(to_cam);
    float fade = smoothstep(is_snow ? 1.5 : 0.6, is_snow ? 4.0 : 2.5, dist) * (1.0 - smoothstep(R * 0.6, R, dist));
    if (is_snow) {
        vec3 side = normalize(cross(vec3(0.0, 1.0, 0.0), to_cam));
        vec3 up = normalize(cross(to_cam, side));
        float size = 0.035 + 0.03 * rnd2.x;
        p += (side * corner.x + up * corner.y) * size;
        kind = 1;
        alpha = fade * 0.9;
        tint = light * 0.95;
    } else {
        vec3 vel = vec3(drift.x, -speed, drift.y);
        vec3 axis = normalize(vel);
        vec3 side = normalize(cross(axis, to_cam));
        float len = 0.35 + 0.25 * rnd2.y;  // motion blur streak
        p += side * corner.x * 0.012 + axis * corner.y * len;
        kind = 0;
        alpha = fade * 0.32;
        tint = light * 0.9 + sky_light.rgb * 0.05;
    }
    gl_Position = m_proj * m_view * vec4(p, 1.0);
}
