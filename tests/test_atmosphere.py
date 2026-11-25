import random
import pytest
from settings import glm, DAY_LENGTH, LUNAR_CYCLE_DAYS
from atmosphere.daycycle import DayCycle, arc_direction, sun_angle
from atmosphere.weather import Weather, WeatherParams, TARGETS, NEXT, KINDS, CLEAR, RAIN, SNOW
from atmosphere.lighting import compute_lighting, sky_colors, transmittance, luminance
from atmosphere.environment import Environment, Strike


# ---------------------------------------------------------------------- day cycle
def test_sun_rises_east_culminates_south_sets_west():
    assert glm.length(DayCycle(12).sun_direction) == pytest.approx(1.0)
    rise, noon, sets, midnight = (DayCycle(h).sun_direction for h in (6, 12, 18, 0))
    assert rise.y == pytest.approx(0, abs=1e-6) and rise.x > 0.99          # east
    assert noon.y > 0.8 and noon.z > 0                                      # high, south
    assert sets.y == pytest.approx(0, abs=1e-6) and sets.x < -0.99         # west
    assert midnight.y < -0.8


def test_clock_wraps_and_counts_days():
    c = DayCycle(23.0, day=4)
    c.advance(DAY_LENGTH / 12)  # two game hours
    assert c.day == 5 and c.hours == pytest.approx(1.0)
    c.advance_hours(48)
    assert c.day == 7 and c.clock_text() == '01:00'


def test_full_moon_rises_when_the_sun_sets():
    full = DayCycle(0.0, day=int(LUNAR_CYCLE_DAYS / 2))  # phase exactly 0.5
    assert full.moon_phase == pytest.approx(0.5)
    assert full.moon_illumination == pytest.approx(1.0)
    assert glm.dot(full.moon_direction, full.sun_direction) == pytest.approx(-1.0, abs=1e-5)
    new = DayCycle(0.0, 0)  # phase exactly 0
    assert new.moon_illumination < 0.05
    assert glm.dot(new.moon_direction, new.sun_direction) > 0.99


def test_sky_rotation_carries_the_sun_arc():
    for hours in (3.0, 9.0, 15.0):
        c = DayCycle(hours, 0)
        rotated = glm.vec3(glm.rotate(glm.mat4(), sun_angle(c.fraction), glm.vec3(0, -0.5735764, 0.819152))
                           * glm.vec4(1, 0, 0, 0))
        assert glm.distance(rotated, arc_direction(sun_angle(c.fraction))) < 1e-4


# ---------------------------------------------------------------------- weather
def test_weather_tables_are_consistent():
    assert set(TARGETS) == set(KINDS) == set(NEXT)
    for kind, nexts in NEXT.items():
        assert set(nexts) <= set(KINDS)
        for value in TARGETS[kind].as_tuple():
            assert 0.0 <= value <= 1.0


def test_weather_changes_at_random_and_settles():
    w = Weather(CLEAR, rng=random.Random(3))
    seen = set()
    for _ in range(4000):  # 4000 game hours, one hour per second
        w.update(1.0, 1.0)
        seen.add(w.kind)
        for v in w.params.as_tuple():
            assert 0.0 <= v <= 1.0
    assert len(seen) >= 5
    w.set_kind(RAIN)
    w.hours_left = 1e9
    for _ in range(300):
        w.update(1.0, 0.0)
    assert w.params.rain == pytest.approx(TARGETS[RAIN].rain, abs=1e-3)
    assert w.wetness == pytest.approx(1.0)


def test_snow_settles_then_melts():
    w = Weather(SNOW, rng=random.Random(1))
    w.hours_left = 1e9
    for _ in range(600):
        w.update(1.0, 0.0)
    assert w.snow_cover > 0.9 and w.wetness < 0.05
    w.set_kind(CLEAR)
    w.hours_left = 1e9
    for _ in range(2000):
        w.update(1.0, 0.0)
    assert w.snow_cover < 0.05


def test_weather_is_reproducible_with_a_seed():
    a, b = Weather(CLEAR, random.Random(7)), Weather(CLEAR, random.Random(7))
    for _ in range(500):
        a.update(1.0, 1.0)
        b.update(1.0, 1.0)
    assert a.kind == b.kind and a.params == b.params


def test_params_lerp():
    a, b = WeatherParams(), WeatherParams(clouds=1.0, rain=0.5)
    mid = a.lerp(b, 0.5)
    assert mid.clouds == 0.5 and mid.rain == 0.25


# ---------------------------------------------------------------------- lighting
def test_sun_reddens_near_the_horizon():
    noon, low = transmittance(0.9), transmittance(0.03)
    assert noon.x > 0.85 and noon.z > 0.7
    assert low.x > 3 * low.z  # sunset: red rather than blue


def test_night_is_darker_than_day_but_exposed():
    clear = TARGETS[CLEAR]
    day = compute_lighting(DayCycle(12).sun_direction, DayCycle(12).moon_direction, 0.5, clear)
    c = DayCycle(0, day=4)
    night = compute_lighting(c.sun_direction, c.moon_direction, 1.0, clear)
    assert luminance(night.ambient_sky) < 0.05 * luminance(day.ambient_sky)
    assert night.exposure > 3 * day.exposure
    assert night.stars > 0.9 and day.stars == 0
    assert glm.length(night.sun_color) == 0
    # the moon casts the shadows at night
    assert glm.dot(night.light_dir, glm.normalize(c.moon_direction)) > 0.99


def test_storm_blocks_the_sun_and_greys_the_sky():
    sun = DayCycle(12).sun_direction
    clear = compute_lighting(sun, -sun, 0.5, TARGETS[CLEAR])
    storm = compute_lighting(sun, -sun, 0.5, TARGETS['storm'])
    assert luminance(storm.light_color) < 0.2 * luminance(clear.light_color)
    z = storm.zenith
    assert max(z.x, z.y, z.z) - min(z.x, z.y, z.z) < 0.5 * (clear.zenith.z - clear.zenith.x)
    flash = compute_lighting(sun, -sun, 0.5, TARGETS['storm'], flash=1.0)
    assert luminance(flash.ambient_sky) > luminance(storm.ambient_sky)


def test_sky_keyframes_continuous():
    prev = None
    for i in range(-100, 101):
        z, h = sky_colors(i / 100)
        if prev is not None:
            assert glm.distance(z, prev[0]) < 0.08 and glm.distance(h, prev[1]) < 0.2
        prev = (z, h)


# ---------------------------------------------------------------------- environment
class FakeStore:
    def __init__(self):
        self.meta = {}

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)

    def set_meta(self, key, value):
        self.meta[key] = str(value)


def test_environment_saves_and_restores():
    store = FakeStore()
    env = Environment(store, rng=random.Random(2))
    env.skip_time(5.5)
    env.weather.set_kind(SNOW)
    env.save()
    again = Environment(store, rng=random.Random(2))
    assert again.clock.hours == pytest.approx(env.clock.hours)
    assert again.weather.kind == SNOW


def test_storm_strikes_lightning():
    env = Environment(rng=random.Random(5))
    env.weather.set_kind('storm')
    env.weather.hours_left = 1e9
    flashes = 0
    for _ in range(60 * 60):  # one minute
        env.update(1 / 60, glm.vec3(100, 20, 100))
        flashes += env.flash > 0.5
    assert flashes > 0
    strike = Strike(0, 0, 1)
    assert strike.flash() == pytest.approx(1.0)
    strike.age = 1.4
    assert strike.flash() < 0.01 and not strike.visible
