// Surface lighting: soft cascaded shadows, cloud shadows, sky occlusion, GGX specular, and the
// indirect light (sky dome + light bounced by the sunlit ground). Needs env.glsl and sky.glsl.

uniform sampler2DShadow u_shadow0;
uniform sampler2DShadow u_shadow1;
uniform sampler2D u_heightmap;  // r: top of the highest block of each column / 255 (wraps around)

const vec2 POISSON[12] = vec2[12](
    vec2(-0.326, -0.406), vec2(-0.840, -0.074), vec2(-0.696, 0.457), vec2(-0.203, 0.621),
    vec2(0.962, -0.195), vec2(0.473, -0.480), vec2(0.519, 0.767), vec2(0.185, -0.893),
    vec2(0.507, 0.064), vec2(0.896, 0.412), vec2(-0.322, -0.933), vec2(-0.792, -0.598)
);

float sample_shadow_map(sampler2DShadow map, vec3 c, float radius, float angle) {
    float s = sin(angle), co = cos(angle);
    mat2 rot = mat2(co, s, -s, co);
    float sum = 0.0;
    for (int i = 0; i < 12; i++) {
        sum += texture(map, vec3(c.xy + rot * POISSON[i] * radius, c.z));
    }
    return sum / 12.0;
}

// 1 = lit, 0 = in the shadow of the main light
float shadow_factor(vec3 pos, vec3 n) {
    if (light_dir.w < 0.5) return 1.0;
    float size = shadow_params.z;
    float jitter = ign(gl_FragCoord.xy) * 2.0 * PI;
    float ndl = dot(n, light_dir.xyz);
    int count = int(shadow_params.w);
    for (int i = 0; i < count; i++) {
        float radius = i == 0 ? shadow_params.x : shadow_params.y;
        float texel = 2.0 * radius / size;
        // normal offset: move the lookup off the surface by about a texel (no acne)
        vec3 p = pos + n * texel * (1.2 + 1.5 * (1.0 - saturate(ndl)));
        vec4 c = shadow_vp[i] * vec4(p, 1.0);
        vec3 uvz = c.xyz * 0.5 + 0.5;
        vec2 edge = abs(uvz.xy - 0.5) * 2.0;
        float border = max(edge.x, edge.y);
        if (border < 0.98 && uvz.z < 1.0) {
            float soft = (1.0 + 3.5 * light_color.w) / size;
            uvz.z -= 0.0004 * (i + 1);
            float s = i == 0 ? sample_shadow_map(u_shadow0, uvz, soft * 1.6, jitter)
                             : sample_shadow_map(u_shadow1, uvz, soft, jitter);
            // fade out at the outer border of the last cascade
            if (i == count - 1) s = mix(s, 1.0, smoothstep(0.8, 0.98, border));
            return s;
        }
    }
    return 1.0;
}

// clouds passing between the surface and the light
float cloud_shadow(vec3 pos) {
    vec3 l = light_dir.xyz;
    vec2 xz = pos.xz + l.xz / max(l.y, 0.1) * (clouds.z - pos.y);
    return 1.0 - 0.8 * cloud_density(xz, 2, 1.0);
}

float column_top(vec2 xz) {
    int mask = int(screen.z) - 1;
    ivec2 c = ivec2(floor(xz)) & mask;
    return texelFetch(u_heightmap, c, 0).r * 255.0;
}

// how much of the sky the point sees (1 open air, ~0 deep in a cave)
float sky_visibility(vec3 pos, vec3 n) {
    vec3 p = pos + n * 0.5;
    float v = 2.0 * exp(-max(column_top(p.xz) - p.y, 0.0) * 0.2);
    v += exp(-max(column_top(p.xz + vec2(2.5, 0.0)) - p.y, 0.0) * 0.2);
    v += exp(-max(column_top(p.xz - vec2(2.5, 0.0)) - p.y, 0.0) * 0.2);
    v += exp(-max(column_top(p.xz + vec2(0.0, 2.5)) - p.y, 0.0) * 0.2);
    v += exp(-max(column_top(p.xz - vec2(0.0, 2.5)) - p.y, 0.0) * 0.2);
    return v / 6.0;
}

// is the point directly under the open sky (rain, snow and wetness reach it)?
float sky_exposure(vec3 pos, vec3 n) {
    vec3 p = pos + n * 0.5;
    return smoothstep(-0.5, 0.4, p.y - column_top(p.xz));
}

float ggx_specular(vec3 n, vec3 v, vec3 l, float roughness) {
    vec3 h = normalize(v + l);
    float a = roughness * roughness;
    float a2 = a * a;
    float ndh = saturate(dot(n, h));
    float ndv = max(dot(n, v), 1e-3);
    float ndl = saturate(dot(n, l));
    float denom = ndh * ndh * (a2 - 1.0) + 1.0;
    float d = a2 / (PI * denom * denom);
    float k = a * 0.5;
    float g = ndv / (ndv * (1.0 - k) + k) * ndl / (ndl * (1.0 - k) + k);
    return d * g / (4.0 * ndv + 1e-4);  // includes the n.l factor
}

float fresnel_schlick(float cos_theta, float f0) {
    return f0 + (1.0 - f0) * pow(1.0 - saturate(cos_theta), 5.0);
}

// indirect light: sky dome above, ground bounce below (a cheap radiosity), cave minimum
vec3 ambient_light(vec3 n, float sky_vis) {
    vec3 dome = mix(ambient_ground.rgb, ambient_sky.rgb, n.y * 0.5 + 0.5);
    // light bounced by sunlit surfaces nearby reaches walls and undersides
    vec3 bounce = light_color.rgb * ambient_ground.rgb * saturate(light_dir.y) * (1.0 - abs(n.y)) * 0.6;
    return (dome + bounce) * sky_vis + vec3(ambient_ground.w);
}

// light of a lightning flash, from the sky
vec3 flash_light(vec3 n, float sky_vis) {
    return vec3(0.75, 0.8, 1.0) * sun_disk.w * 0.5 * saturate(n.y * 0.6 + 0.4) * sky_vis;
}
