// Shared state of the sky and the camera, written once per frame (render/env_buffer.py).
// std140: keep in sync with ENV_LAYOUT in render/env_buffer.py.
layout(std140) uniform Env {
    mat4 shadow_vp[2];    // world -> light clip space, per shadow cascade
    mat4 sky_rot;         // celestial sphere -> world (stars)
    mat4 inv_view_proj;   // clip -> world of the camera (sky, post-processing)
    mat4 view_proj;       // world -> clip of the camera (screen space reflections)
    vec4 sun_dir;         // xyz towards the sun, w: moon illumination
    vec4 moon_dir;        // xyz towards the moon, w: star visibility
    vec4 light_dir;       // xyz towards the shadow-casting light (sun or moon), w: light on
    vec4 light_color;     // rgb direct light reaching the ground, w: shadow softness
    vec4 sun_disk;        // rgb radiance of the sun disk, w: lightning flash
    vec4 sky_light;       // rgb sun + moon light above the clouds, w: day fraction (0.5 noon)
    vec4 zenith;          // rgb sky color overhead, w: time (s)
    vec4 horizon;         // rgb sky color at the horizon, w: cloud cover
    vec4 ambient_sky;     // rgb light from the sky dome, w: cloud darkness
    vec4 ambient_ground;  // rgb light bounced by the ground, w: minimum (cave) ambient
    vec4 fog_color;       // rgb, w: ground fog of the weather
    vec4 fog_params;      // x: opaque fog start, y: end, z: camera underwater, w: water line
    vec4 weather;         // x: precipitation, y: snow share, z: wet ground, w: snow cover
    vec4 wind;            // xy direction, z: strength, w: wave height
    vec4 camera;          // xyz camera position, w: exposure
    vec4 shadow_params;   // xy: cascade radii, z: shadow map size, w: cascade count
    vec4 water_fog;       // rgb underwater fog color, w: density
    vec4 clouds;          // xy: drift of the clouds, z: cloud altitude, w: precipitation radius
    vec4 bolt;            // xyz: ground point of the last lightning bolt, w: its flash
    vec4 screen;          // xy: viewport size, zw: heightmap size, snow line
};

const float PI = 3.14159265;

float saturate(float x) { return clamp(x, 0.0, 1.0); }
vec3 srgb_to_linear(vec3 c) { return pow(c, vec3(2.2)); }

// interleaved gradient noise: per-pixel jitter without visible pattern
float ign(vec2 frag) { return fract(52.9829189 * fract(dot(frag, vec2(0.06711056, 0.00583715)))); }

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float hash13(vec3 p3) {
    p3 = fract(p3 * 0.1031);
    p3 += dot(p3, p3.zyx + 31.32);
    return fract((p3.x + p3.y) * p3.z);
}

vec3 hash33(vec3 p3) {
    p3 = fract(p3 * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yxz + 33.33);
    return fract((p3.xxy + p3.yxx) * p3.zyx);
}
