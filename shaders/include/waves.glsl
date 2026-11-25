// Gerstner waves pushed by the wind (needs env.glsl). Shared by water.vert and water.frag.

const int WAVES = 6;
const float WAVE_LENGTH[WAVES] = float[WAVES](17.0, 11.0, 7.3, 4.9, 3.3, 26.0);
const float WAVE_ANGLE[WAVES] = float[WAVES](0.0, 0.45, -0.55, 0.95, -1.25, -0.2);
const float WAVE_SHARE[WAVES] = float[WAVES](0.30, 0.20, 0.14, 0.09, 0.06, 0.21);
const float STEEPNESS = 0.55;
const float G = 9.8;

// displacement (xyz) of the surface point resting at xz; amp scales the waves (0 = flat)
vec3 gerstner(vec2 xz, float amp, float t, out vec3 normal) {
    vec3 offset = vec3(0.0);
    vec3 nrm = vec3(0.0, 1.0, 0.0);
    float base = atan(wind.y, wind.x);
    for (int i = 0; i < WAVES; i++) {
        float a = base + WAVE_ANGLE[i];
        vec2 d = vec2(cos(a), sin(a));
        float k = 2.0 * PI / WAVE_LENGTH[i];
        float c = sqrt(G / k);
        float A = wind.w * amp * WAVE_SHARE[i] * (WAVE_LENGTH[i] / 12.0);
        float q = STEEPNESS / (k * max(A, 1e-4) * float(WAVES));
        q = min(q, 1.0);
        float f = k * (dot(d, xz) - c * t);
        float s = sin(f), co = cos(f);
        offset.xz += q * A * d * co;
        offset.y += A * s;
        float wa = k * A;
        nrm.xz -= d * wa * co;
        nrm.y -= q * wa * s;
    }
    normal = normalize(nrm);
    return offset;
}
