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

// ---------------------------------------------------------------- night sky
// Galactic frame on the celestial sphere: the core of the milky way culminates high in the
// south around midnight, and its band arches across the whole sky.
const vec3 GALACTIC_CORE = vec3(-0.9290, -0.3661, 0.0530);
const vec3 GALACTIC_POLE = vec3(0.1606, -0.5281, -0.8338);
const float NOISE_TILES = 9.0;  // the noise repeats this many times around the band (seamless)

vec4 noise_grad(vec2 uv, vec2 dx, vec2 dy) { return textureGrad(u_noise, uv, dx, dy); }

// galactic coordinates of a celestial direction: (longitude in [-pi, pi], sin latitude)
vec2 galactic(vec3 c) {
    vec3 east = cross(GALACTIC_POLE, GALACTIC_CORE);
    return vec2(atan(dot(c, east), dot(c, GALACTIC_CORE)), dot(c, GALACTIC_POLE));
}

// milky way: rgb radiance, a = how dense the band is there (more stars)
vec4 milky_way(vec3 c) {
    vec2 g = galactic(c);
    float l = g.x, b = g.y;
    // noise coordinates, with derivatives that ignore the wrap of the longitude
    vec2 uv = vec2(l, b) * (NOISE_TILES / (2.0 * PI));  // same scale along and across
    vec2 dx = dFdx(uv), dy = dFdy(uv);
    dx.x -= round(dx.x / NOISE_TILES) * NOISE_TILES;
    dy.x -= round(dy.x / NOISE_TILES) * NOISE_TILES;

    float coarse = noise_grad(uv + vec2(0.13, 0.5), dx, dy).r;
    float medium = noise_grad(uv * 2.0 + vec2(0.37, 0.21), dx * 2.0, dy * 2.0).g;
    float fine = noise_grad(uv * 4.0 + vec2(0.71, 0.4), dx * 4.0, dy * 4.0).b;
    float grain = noise_grad(uv * 11.0, dx * 11.0, dy * 11.0).a;

    float core = exp(-l * l / (2.0 * 0.55 * 0.55));         // brighter towards the center
    float width = (0.13 + 0.08 * core) * (0.7 + 0.6 * coarse);
    float wavy = b + (coarse - 0.5) * 0.08;                  // the band is not a perfect circle
    float band = exp(-wavy * wavy / (width * width));
    float bulge = exp(-(l * l / 0.22 + b * b / 0.05));     // the bright galactic bulge

    // star clouds: clumps of unresolved stars
    float clouds_ = 0.45 + 1.1 * smoothstep(0.15, 0.9, coarse * 0.5 + medium * 0.38 + fine * 0.12);
    float glow = band * (0.3 + 0.9 * core) * clouds_ * (0.92 + 0.16 * grain) + bulge * (1.6 + 0.8 * medium);

    // dust lanes: the great rift along the middle of the band, and dark filaments
    float rift_w = 0.025 + 0.035 * coarse;
    float rift_b = b - 0.012 - (coarse - 0.5) * 0.06 - (medium - 0.5) * 0.015;
    float rift = exp(-rift_b * rift_b / (rift_w * rift_w)) * smoothstep(2.2, 0.3, abs(l));
    rift *= smoothstep(0.15, 0.75, coarse * 0.7 + medium * 0.3);
    float filaments = smoothstep(0.45, 0.9, medium * 0.8 + fine * 0.2) * smoothstep(0.3, 0.7, coarse) * band;
    float dust = saturate(rift * 0.85 + filaments * 0.4);
    glow *= 1.0 - 0.85 * dust;

    vec3 outer = vec3(0.72, 0.84, 1.0);
    vec3 inner = vec3(1.0, 0.88, 0.7);
    vec3 col = mix(outer, inner, saturate(core * 0.45 + bulge));
    col *= glow;
    // reddish glowing nebulae here and there along the band
    col += vec3(1.0, 0.32, 0.42) * smoothstep(0.72, 0.92, fine * 0.7 + grain * 0.3) * band * core * 0.5;
    col = mix(col, col * vec3(1.0, 0.88, 0.78), dust);  // starlight reddened by the dust
    return vec4(col * 0.014, saturate(band * (1.0 - dust) + bulge));
}

// one layer of stars: one candidate per cell of an equi-angular cube map of the sphere
vec3 star_layer(vec3 c, float cells, float density, float brightness, float seed, float pixel) {
    vec3 a = abs(c);
    int face;
    vec3 fc;  // (u, v, major) for this face
    if (a.x >= a.y && a.x >= a.z) { face = c.x > 0.0 ? 0 : 1; fc = vec3(c.y, c.z, c.x); }
    else if (a.y >= a.z) { face = c.y > 0.0 ? 2 : 3; fc = vec3(c.x, c.z, c.y); }
    else { face = c.z > 0.0 ? 4 : 5; fc = vec3(c.x, c.y, c.z); }
    vec2 uv = atan(fc.xy / abs(fc.z)) * (4.0 / PI);    // equi-angular: cells of the same size
    vec2 cell = floor((uv * 0.5 + 0.5) * cells);

    vec3 id = vec3(cell, float(face) * 131.0 + seed);
    float h = hash13(id);
    if (h > density) return vec3(0.0);
    vec3 r = hash33(id + 17.3);

    // the star direction, kept away from the cell borders (its light is not cut)
    vec2 suv = (cell + 0.3 + 0.4 * r.xy) / cells * 2.0 - 1.0;
    vec3 sf = vec3(tan(suv * (PI / 4.0)), sign(fc.z));
    vec3 star;
    if (face < 2) star = vec3(sf.z, sf.x, sf.y);
    else if (face < 4) star = vec3(sf.x, sf.z, sf.y);
    else star = vec3(sf.x, sf.y, sf.z);
    star = normalize(star);

    // many faint stars, a few bright ones
    float flux = brightness * (0.05 + pow(r.z, 7.0) * 3.0);
    // point spread over about a pixel: the stars stay sharp dots at any resolution
    float d = length(c - star) / pixel;
    float sigma = 0.5 + 0.35 * sqrt(r.z * r.z * brightness);
    float psf = exp(-0.5 * d * d / (sigma * sigma));
    psf += 0.04 * exp(-d * 0.9) * r.z * r.z;  // soft halo around the brightest

    // color from the star temperature: blue-white, white, yellow, orange
    float t = hash13(id + 5.7);
    vec3 tint = t < 0.12 ? vec3(0.68, 0.8, 1.0) : t < 0.55 ? vec3(1.0) :
                t < 0.82 ? vec3(1.0, 0.9, 0.74) : vec3(1.0, 0.72, 0.48);
    // twinkling
    float phase = hash13(id + 9.1) * 6.2832;
    float twinkle = 1.0 + 0.3 * sin(zenith.w * (3.0 + 6.0 * r.x) + phase) * sin(zenith.w * 1.7 + phase * 3.0);
    return tint * flux * twinkle * psf;
}

vec3 night_sky(vec3 dir) {
    vec3 c = transpose(mat3(sky_rot)) * dir;  // world -> celestial sphere
    float pixel = max(length(dFdx(c)), length(dFdy(c)));
    // the full moon washes the faint stars and the milky way out
    float moonlight = sun_dir.w * smoothstep(-0.05, 0.3, moon_dir.y);
    vec4 mw = milky_way(c);
    float dense = mw.a;
    vec3 col = mw.rgb * (1.0 - 0.6 * moonlight);
    vec3 s = star_layer(c, 420.0, 0.10 + 0.45 * dense, 0.04 * (1.0 - 0.7 * moonlight), 1.0, pixel);
    s += star_layer(c, 170.0, 0.16 + 0.2 * dense, 0.12 * (1.0 - 0.4 * moonlight), 2.0, pixel);
    s += star_layer(c, 55.0, 0.18, 0.5, 3.0, pixel);
    col += s;
    // seen through more air near the horizon: dimmer and redder
    float y = max(dir.y, 0.0);
    vec3 extinction = exp(-vec3(0.12, 0.2, 0.35) / (y + 0.06));
    return col * extinction * smoothstep(-0.02, 0.08, dir.y);
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
    // a darker sky high up on moonless nights: the milky way stands out
    float moonless = 1.0 - sun_dir.w * smoothstep(-0.05, 0.3, moon_dir.y);
    col *= 1.0 - 0.5 * night * moonless * smoothstep(0.0, 0.4, dir.y);
    if (night > 0.0) col += night_sky(dir) * night;
    col += moon_color(dir);
    col += sun_disk_color(dir) * (1.0 - overcast());

    vec4 cl = sky_clouds(dir);
    cl.rgb *= 1.0 - 0.4 * night * moonless;  // dark clouds hide the stars
    col = mix(col, cl.rgb, cl.a);

    // the weather fog and the rain veil hide the horizon
    float veil = saturate(fog_color.w * 1.2) * (1.0 - smoothstep(-0.05, 0.5, dir.y));
    veil = max(veil, weather.x * 0.55 * (1.0 - smoothstep(0.0, 0.35, dir.y)));
    col = mix(col, fog_tint(dir), veil);
    fragColor = vec4(col, 1.0);
}
