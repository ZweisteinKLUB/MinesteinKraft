// Sky radiance, clouds and fog (needs env.glsl). Linear HDR colors.

uniform sampler2D u_noise;  // tileable smooth noise: r coarse, g medium, b fine, a fine (other seed)

// Henyey-Greenstein phase function (forward scattering for g > 0)
float hg_phase(float mu, float g) {
    float g2 = g * g;
    return (1.0 - g2) / (4.0 * PI * pow(1.0 + g2 - 2.0 * g * mu, 1.5));
}

float overcast() { return smoothstep(0.5, 1.0, horizon.w); }

// how much the sun is setting or rising (0 by day and by night)
float sunset_amount() {
    float y = sun_dir.y;
    return exp(-max(y, 0.0) * 7.0) * smoothstep(-0.22, 0.0, y);
}

// clear sky in a direction (no sun disk, moon or clouds): gradient, sun glow, sunset band
vec3 sky_radiance(vec3 dir) {
    float y = dir.y;
    float mu = dot(dir, sun_dir.xyz);
    // at sunset the horizon glows on the side of the sun, and turns pink / blue opposite
    float towards_sun = pow(saturate(mu * 0.5 + 0.5), 2.0);
    vec3 opposite = mix(horizon.rgb, zenith.rgb * 1.6 + vec3(0.05, 0.015, 0.04) * sunset_amount(), 0.75);
    vec3 hz = mix(horizon.rgb, mix(opposite, horizon.rgb, towards_sun), sunset_amount());
    vec3 col = mix(hz, zenith.rgb, pow(saturate(y), 0.5));
    col *= mix(1.0, 0.6, smoothstep(0.0, -0.35, y));  // below the horizon: haze over the sea

    float clear_sky = 1.0 - 0.85 * overcast();
    vec3 sun = sky_light.rgb;
    col += sun * clear_sky * (0.05 * hg_phase(mu, 0.8) + 0.015 * hg_phase(mu, 0.2));
    // warm band at the horizon on the side of a low sun
    col += sun * clear_sky * 0.12 * pow(saturate(mu * 0.5 + 0.5), 6.0) * exp(-abs(y) * 7.0);
    float moon_mu = dot(dir, moon_dir.xyz);
    col += vec3(0.6, 0.7, 1.0) * 0.004 * sun_dir.w * hg_phase(moon_mu, 0.85) * (1.0 - overcast());
    col += vec3(0.75, 0.8, 1.0) * sun_disk.w * 0.2;  // lightning lights up the whole sky
    return col;
}

// cloud density in [0, 1] over a world position on the cloud layer (octaves: 1..4 of detail);
// detail_weight < 1 for far clouds (the fine noise would only flicker there)
float cloud_density(vec2 xz, int octaves, float detail_weight) {
    vec2 p = (xz + clouds.xy) * 0.00032;
    // shape: two coarse octaves, remapped by the cloud cover
    float base = texture(u_noise, p).r * 0.65 + texture(u_noise, p * 2.1 + 0.3).g * 0.35;
    float cover = horizon.w;
    float d = saturate((base - (1.0 - cover) * 0.85) / max(0.25 + cover * 0.4, 0.05));
    // detail erodes the edges (puffy borders), not the cores
    float detail = 0.0, amp = 0.5;
    vec2 q = p * 6.0 + 0.11;
    for (int i = 0; i < octaves; i++) {
        detail += amp * texture(u_noise, q).b;
        amp *= 0.5;
        q = q * 2.17 + vec2(0.37, 0.71);
    }
    d = saturate(d - detail * 0.45 * detail_weight * (1.0 - d));
    return smoothstep(0.0, 0.6, d);
}

// cloud layer seen in a direction: rgb color, a coverage
vec4 sky_clouds(vec3 dir) {
    if (dir.y < 0.015) return vec4(0.0);
    float t = (clouds.z - camera.y) / dir.y;
    vec2 xz = camera.xz + dir.xz * t;
    float d = cloud_density(xz, 4, exp(-t * 0.00012));
    if (d <= 0.001) return vec4(0.0);

    vec3 l = light_dir.xyz;
    float towards = cloud_density(xz + l.xz / max(l.y, 0.08) * 120.0, 2, 1.0);
    float mu = dot(dir, l);
    float dark = ambient_sky.w;
    vec3 light = sky_light.rgb * (1.0 - 0.8 * dark);
    // seen from below: thin parts let the light through, thick cores are grey
    float through = exp(-d * 3.0) * (1.0 - 0.6 * towards);
    float powder = 1.0 - exp(-d * 4.0);
    vec3 col = ambient_sky.rgb * mix(0.95, 0.7, d) * (1.0 - 0.45 * dark * d);
    col += light * (0.05 + through * (0.25 + 1.6 * hg_phase(mu, 0.6)) + 0.16 * powder * (1.0 - towards));
    col += vec3(0.75, 0.8, 1.0) * sun_disk.w * 0.5;  // lit from inside by lightning

    float alpha = smoothstep(0.0, 0.7, d);
    float far = 1.0 - exp(-t * 0.00006);
    col = mix(col, sky_radiance(dir), far);    // aerial perspective
    alpha *= 1.0 - smoothstep(0.6, 1.0, far);  // vanish at the horizon
    return vec4(col, alpha);
}

// optical depth of the weather's ground fog along a ray (exponential height fog)
float ground_fog(vec3 from, vec3 dir, float dist) {
    float density = fog_color.w * 0.09;
    if (density <= 0.0) return 0.0;
    const float falloff = 0.045;  // fog layer thickness ~ 22 blocks above the sea
    float h0 = max(from.y - fog_params.w, 0.0);
    float dy = dir.y * dist;
    float integral = abs(dy) < 0.01 ? dist : (1.0 - exp(-falloff * dy)) / (falloff * dir.y);
    return density * exp(-falloff * h0) * integral;
}

// color the fog takes in a direction (the sky behind it, then the weather fog)
vec3 fog_tint(vec3 dir) {
    vec3 sky = sky_radiance(vec3(dir.x, max(dir.y, -0.02), dir.z));
    return mix(sky, fog_color.rgb, saturate(fog_color.w * 1.2));
}

// distance fog for a surface at world position pos
vec3 apply_fog(vec3 col, vec3 pos) {
    vec3 d = pos - camera.xyz;
    float dist = length(d);
    vec3 dir = d / max(dist, 1e-4);
    if (fog_params.z > 0.5) {  // camera under water
        col *= vec3(0.45, 0.75, 1.0);
        return mix(col, water_fog.rgb, 1.0 - exp(-water_fog.w * dist * dist));
    }
    float haze = 0.0005 + 0.004 * weather.x + 0.0006 * horizon.w;
    float optical = dist * haze + ground_fog(camera.xyz, dir, dist);
    float edge = smoothstep(fog_params.x, fog_params.y, dist);  // hides the edge of the loaded area
    float f = 1.0 - exp(-optical) * (1.0 - edge);
    return mix(col, fog_tint(dir), f);
}
