"""The ``Env`` uniform block (shaders/include/env.glsl): sky, light, weather and camera state."""
import numpy as np
from settings import glm, FOG_START, FOG_END, WATER_LINE, WATER_FOG_COLOR, WATER_FOG_DENSITY, \
    PRECIPITATION_RADIUS, HEIGHTMAP_SIZE, SNOW_LVL, MIN_AMBIENT, WAVE_HEIGHT

# std140 layout: names in declaration order, 16 floats per mat4, 4 per vec4
MATRICES = ('shadow_vp0', 'shadow_vp1', 'sky_rot', 'inv_view_proj', 'view_proj')
VECTORS = ('sun_dir', 'moon_dir', 'light_dir', 'light_color', 'sun_disk', 'sky_light', 'zenith',
           'horizon', 'ambient_sky', 'ambient_ground', 'fog_color', 'fog_params', 'weather', 'wind',
           'camera', 'shadow_params', 'water_fog', 'clouds', 'bolt', 'screen')
ENV_FLOATS = 16 * len(MATRICES) + 4 * len(VECTORS)
ENV_SIZE = ENV_FLOATS * 4

_OFFSET = {}
_pos = 0
for _name in MATRICES:
    _OFFSET[_name] = (_pos, 16)
    _pos += 16
for _name in VECTORS:
    _OFFSET[_name] = (_pos, 4)
    _pos += 4


def gamma_to_linear(c):
    return glm.vec3(c.x ** 2.2, c.y ** 2.2, c.z ** 2.2)


class EnvBuffer:
    def __init__(self, ctx):
        self.data = np.zeros(ENV_FLOATS, dtype='f4')
        self.buffer = ctx.buffer(reserve=ENV_SIZE, dynamic=True)

    def set(self, name, value, w=None):
        start, size = _OFFSET[name]
        if size == 16:
            self.data[start:start + 16] = np.frombuffer(value.to_bytes(), dtype='f4')  # column-major
        else:
            values = list(value) if not isinstance(value, (int, float)) else [value]
            if w is not None:
                values = values[:3] + [w]
            values += [0.0] * (4 - len(values))
            self.data[start:start + 4] = values

    def fill(self, env, camera, shadows, viewport, flash_point=None):
        """Write the state of the frame (env: atmosphere.Environment)."""
        lit = env.lighting
        clock, weather = env.clock, env.weather
        p = weather.params
        s = self.set
        s('shadow_vp0', shadows.matrices[0])
        s('shadow_vp1', shadows.matrices[1])
        s('sky_rot', clock.sky_rotation)
        view_proj = camera.m_proj * camera.m_view
        s('inv_view_proj', glm.inverse(view_proj))
        s('view_proj', view_proj)
        s('sun_dir', clock.sun_direction, clock.moon_illumination)
        s('moon_dir', clock.moon_direction, lit.stars)
        s('light_dir', lit.light_dir, 1.0 if shadows.active else 0.0)
        s('light_color', lit.light_color, lit.shadow_softness)
        s('sun_disk', lit.sun_disk, env.flash)
        s('sky_light', lit.sun_color + lit.moon_color, clock.fraction)
        s('zenith', lit.zenith, env.time)
        s('horizon', lit.horizon, p.clouds)
        s('ambient_sky', lit.ambient_sky, p.darkness)
        s('ambient_ground', lit.ambient_ground, MIN_AMBIENT)
        s('fog_color', lit.fog_color, p.fog)
        s('fog_params', (FOG_START, FOG_END, 1.0 if camera.camera_underwater else 0.0, WATER_LINE))
        s('weather', (p.rain, p.snow, weather.wetness, weather.snow_cover))
        wx, wz = weather.wind_direction
        low, high = WAVE_HEIGHT
        s('wind', (wx, wz, p.wind, low + (high - low) * p.wind ** 1.5))
        s('camera', camera.view_position, lit.exposure)
        s('shadow_params', (*shadows.radii, float(shadows.size), float(shadows.cascades)))
        # underwater fog: darker at night, like everything else
        day = 0.04 + 0.96 * min(1.0, max(0.0, (clock.sun_direction.y + 0.1) * 4.0))
        s('water_fog', gamma_to_linear(WATER_FOG_COLOR) * day, WATER_FOG_DENSITY)
        s('clouds', (env.cloud_offset.x, env.cloud_offset.y, env.cloud_altitude, PRECIPITATION_RADIUS))
        bolt = flash_point or (0.0, 0.0, 0.0)
        s('bolt', bolt, env.flash)
        s('screen', (float(viewport[0]), float(viewport[1]), float(HEIGHTMAP_SIZE), float(SNOW_LVL)))
        self.buffer.write(self.data.tobytes())

    def bind(self, binding):
        self.buffer.bind_to_uniform_block(binding)

    def release(self):
        self.buffer.release()
