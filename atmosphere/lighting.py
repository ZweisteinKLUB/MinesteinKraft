"""Light and sky colors for a sun / moon position and a weather (linear HDR RGB).

The sun color comes from the thickness of air its light crosses (reddened near the horizon);
the sky colors from keyframes over the sun elevation (night, blue hour, sunset, day). Clouds
grey everything, block the direct light and soften the shadows. The exposure brightens the
night so the world stays playable while looking dark and blue.
"""
from dataclasses import dataclass
from settings import glm, math, SUN_ILLUMINANCE, MOON_ILLUMINANCE, NIGHT_EXPOSURE, DAY_EXPOSURE

# atmospheric extinction per air mass (red, green, blue): blue is scattered first
EXTINCTION = glm.vec3(0.045, 0.10, 0.22)

# sky keyframes over the sine of the sun elevation: (sin, zenith, horizon)
SKY_KEYS = (
    (-1.00, glm.vec3(0.0022, 0.0035, 0.0090), glm.vec3(0.0040, 0.0060, 0.0120)),
    (-0.25, glm.vec3(0.0025, 0.0040, 0.0100), glm.vec3(0.0050, 0.0070, 0.0140)),
    (-0.10, glm.vec3(0.010, 0.018, 0.050), glm.vec3(0.040, 0.030, 0.050)),
    (0.00, glm.vec3(0.060, 0.110, 0.260), glm.vec3(0.700, 0.300, 0.120)),
    (0.10, glm.vec3(0.140, 0.300, 0.700), glm.vec3(0.900, 0.620, 0.420)),
    (0.30, glm.vec3(0.160, 0.380, 0.900), glm.vec3(0.700, 0.820, 0.980)),
    (1.00, glm.vec3(0.140, 0.360, 0.900), glm.vec3(0.620, 0.780, 0.980)),
)

MOON_COLOR = glm.vec3(0.62, 0.72, 1.0)   # moonlight looks bluish to the eye
OVERCAST_COLOR = glm.vec3(0.55, 0.58, 0.62)


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def air_mass(sin_elevation):
    """Relative thickness of atmosphere crossed by light (1 at the zenith, ~40 at the horizon)."""
    s = max(sin_elevation, -0.05)
    return 1.0 / (s + 0.05 + 0.02 * math.exp(-8.0 * s)) * 1.05


def transmittance(sin_elevation):
    m = air_mass(sin_elevation)
    return glm.vec3(math.exp(-EXTINCTION.x * m), math.exp(-EXTINCTION.y * m), math.exp(-EXTINCTION.z * m))


def sky_colors(sin_elevation):
    """(zenith, horizon) sky radiance for the sun at this elevation, clear weather."""
    s = max(-1.0, min(1.0, sin_elevation))
    for (s0, z0, h0), (s1, z1, h1) in zip(SKY_KEYS, SKY_KEYS[1:]):
        if s <= s1:
            t = smoothstep(s0, s1, s)
            return glm.mix(z0, z1, t), glm.mix(h0, h1, t)
    return SKY_KEYS[-1][1], SKY_KEYS[-1][2]


def luminance(c):
    return 0.2126 * c.x + 0.7152 * c.y + 0.0722 * c.z


def overcast(color, amount, darkness):
    """Grey a sky color under clouds (keeps its brightness, then darkens it)."""
    grey = OVERCAST_COLOR * (luminance(color) / luminance(OVERCAST_COLOR))
    return glm.mix(color, grey, amount) * (1.0 - 0.88 * darkness * amount)


@dataclass
class Lighting:
    sun_color: glm.vec3        # direct sunlight reaching the ground (0 at night)
    moon_color: glm.vec3       # direct moonlight
    light_dir: glm.vec3        # the shadow-casting light: the sun by day, the moon at night
    light_color: glm.vec3      # its color (with cloud dimming)
    sun_disk: glm.vec3         # radiance of the sun disk in the sky
    zenith: glm.vec3
    horizon: glm.vec3
    ambient_sky: glm.vec3      # light from the sky dome (above)
    ambient_ground: glm.vec3   # light bounced by the ground (below)
    fog_color: glm.vec3
    exposure: float
    stars: float               # star visibility
    shadow_softness: float     # 0 sharp, 1 very soft (overcast)


def compute_lighting(sun_dir, moon_dir, moon_illumination, weather, flash=0.0):
    """Lighting for the given sky bodies and ``WeatherParams``; ``flash`` is a lightning flash (0..1)."""
    s = sun_dir.y
    clouds, dark = weather.clouds, weather.darkness
    overcast_amount = smoothstep(0.35, 1.0, clouds)

    # direct light: the clouds block it (the remaining partial cover is shaded in the shaders)
    direct_block = 1.0 - 0.92 * smoothstep(0.65, 1.0, clouds) * (0.5 + 0.5 * dark)
    sun_visible = smoothstep(-0.03, 0.04, s)
    sun_t = transmittance(s)
    sun_color = sun_t * (SUN_ILLUMINANCE * sun_visible)
    moon_visible = smoothstep(-0.03, 0.06, moon_dir.y)
    moon_color = MOON_COLOR * (MOON_ILLUMINANCE * moon_visible * (0.15 + 0.85 * moon_illumination))

    # the shadows follow the sun by day, the moon at night (switch while both are dim)
    if s > -0.06 or moon_dir.y <= 0.0:
        light_dir, light_color = glm.vec3(sun_dir), glm.vec3(sun_color)
    else:
        light_dir, light_color = glm.vec3(moon_dir), glm.vec3(moon_color)
    light_dir.y = max(light_dir.y, 0.02)  # never exactly grazing: keeps the shadow map finite
    light_dir = glm.normalize(light_dir)
    light_color *= direct_block

    zenith, horizon = sky_colors(s)
    zenith = overcast(zenith, overcast_amount, dark)
    horizon = overcast(horizon, overcast_amount, dark)

    # ambient: the sky dome; under clouds the light is diffuse (less direct, more ambient)
    ambient_sky = (zenith * 0.55 + horizon * 0.45) * 1.7
    ambient_sky += (sun_color + moon_color) * (1.0 - direct_block) * 0.22
    ambient_sky += moon_color * 0.25  # moonlit night sky
    ground_albedo = glm.vec3(0.32, 0.36, 0.22)  # grass and sand, average
    ambient_ground = ground_albedo * (ambient_sky * 0.5 + light_color * max(light_dir.y, 0.0) * 0.35)

    fog_color = glm.mix(horizon, zenith, 0.25)
    # ground fog takes the color of the diffuse light
    fog_color = glm.mix(fog_color, ambient_sky * 0.75, weather.fog * 0.7)

    if flash > 0.0:
        bolt = glm.vec3(0.75, 0.8, 1.0) * (flash * 0.35)
        zenith += bolt * 0.3
        horizon += bolt * 0.3
        ambient_sky += bolt
        fog_color += bolt * 0.2

    day = smoothstep(-0.12, 0.25, s)
    exposure = NIGHT_EXPOSURE + (DAY_EXPOSURE - NIGHT_EXPOSURE) * day
    exposure *= 1.0 + 0.25 * overcast_amount * dark * day  # the eye adapts to dark skies
    stars = smoothstep(-0.08, -0.25, s) * (1.0 - smoothstep(0.3, 0.8, clouds))

    return Lighting(
        sun_color=sun_color, moon_color=moon_color, light_dir=light_dir, light_color=light_color,
        sun_disk=sun_t * (40.0 * SUN_ILLUMINANCE * sun_visible), zenith=zenith, horizon=horizon,
        ambient_sky=ambient_sky, ambient_ground=ambient_ground, fog_color=fog_color,
        exposure=exposure, stars=stars, shadow_softness=overcast_amount,
    )
