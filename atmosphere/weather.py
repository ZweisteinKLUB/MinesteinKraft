"""Random weather: clear, cloudy, fog, rain, storm and snow, with smooth transitions.

Each weather lasts a random number of game hours, then the next one is drawn from a table of
likely successions (a storm comes after rain, fog rather at dawn...). The visible parameters
(cloud cover, rain, wind...) glide towards the targets of the current weather, so a change
takes a little while, like a front coming in. Wet ground and snow cover build up and fade.
"""
import random
from dataclasses import dataclass, fields, replace
from settings import math, WEATHER_DURATION_HOURS, WEATHER_TRANSITION_S, WETNESS_RATES, SNOW_COVER_RATES

CLEAR, CLOUDY, FOG, RAIN, STORM, SNOW = 'clear', 'cloudy', 'fog', 'rain', 'storm', 'snow'
KINDS = (CLEAR, CLOUDY, FOG, RAIN, STORM, SNOW)
NAMES = {CLEAR: 'Beau temps', CLOUDY: 'Nuageux', FOG: 'Brouillard', RAIN: 'Pluie',
         STORM: 'Orage', SNOW: 'Neige'}


@dataclass
class WeatherParams:
    """What a weather looks like. Every value is in [0, 1]."""
    clouds: float = 0.0       # cloud cover of the sky
    darkness: float = 0.0     # thick, grey, light-blocking clouds
    rain: float = 0.0         # precipitation intensity (rain, or snow above the snow line)
    snow: float = 0.0         # precipitation falls as snow everywhere
    fog: float = 0.0          # ground fog
    wind: float = 0.0         # wind strength (clouds, rain slant, waves)
    lightning: float = 0.0    # chance of lightning strikes

    def lerp(self, other, t):
        return WeatherParams(*(a + (b - a) * t for a, b in
                               zip(self.as_tuple(), other.as_tuple())))

    def as_tuple(self):
        return tuple(getattr(self, f.name) for f in fields(self))


TARGETS = {
    CLEAR:  WeatherParams(clouds=0.25, wind=0.25),
    CLOUDY: WeatherParams(clouds=0.62, darkness=0.15, wind=0.45),
    FOG:    WeatherParams(clouds=0.55, darkness=0.1, fog=1.0, wind=0.05),
    RAIN:   WeatherParams(clouds=0.9, darkness=0.55, rain=0.65, wind=0.55),
    STORM:  WeatherParams(clouds=1.0, darkness=0.85, rain=1.0, wind=1.0, lightning=1.0),
    SNOW:   WeatherParams(clouds=0.88, darkness=0.35, rain=0.75, snow=1.0, wind=0.3),
}

# likely successions (weights)
NEXT = {
    CLEAR:  {CLEAR: 2, CLOUDY: 4, FOG: 1},
    CLOUDY: {CLEAR: 3, CLOUDY: 1, RAIN: 3, FOG: 1, SNOW: 1},
    FOG:    {CLEAR: 3, CLOUDY: 2},
    RAIN:   {CLOUDY: 3, RAIN: 1, STORM: 2, CLEAR: 1},
    STORM:  {RAIN: 3, CLOUDY: 2},
    SNOW:   {CLOUDY: 3, SNOW: 1, CLEAR: 1},
}


def approach(value, target, rate, dt):
    """Move ``value`` towards ``target`` exponentially (``rate`` per second)."""
    return target + (value - target) * math.exp(-rate * dt)


class Weather:
    """Current weather and its smoothly varying parameters."""

    def __init__(self, kind=CLEAR, rng=None):
        self.rng = rng or random.Random()
        self.kind = kind
        self.params = replace(TARGETS[kind])
        self.hours_left = self.draw_duration(kind)
        self.wetness = 0.0       # wet ground after rain, dries in the sun
        self.snow_cover = 0.0    # snow layer on the ground, melts when it stops snowing
        self.wind_angle = self.rng.uniform(0, 2 * math.pi)  # direction the wind blows towards

    def draw_duration(self, kind):
        low, high = WEATHER_DURATION_HOURS[kind]
        return self.rng.uniform(low, high)

    def choose_next(self, hour=12.0):
        weights = dict(NEXT[self.kind])
        if 4.0 <= hour <= 9.0:  # morning mist
            weights[FOG] = weights.get(FOG, 0) + 2
        kinds = list(weights)
        return self.rng.choices(kinds, weights=[weights[k] for k in kinds])[0]

    def set_kind(self, kind):
        """Start a weather now (its look still takes a moment to settle)."""
        self.kind = kind
        self.hours_left = self.draw_duration(kind)

    def cycle(self):
        """Next weather in a fixed order (debug key)."""
        self.set_kind(KINDS[(KINDS.index(self.kind) + 1) % len(KINDS)])

    def update(self, dt, game_hours, hour=12.0):
        """Advance by ``dt`` real seconds, ``game_hours`` of game time."""
        self.hours_left -= game_hours
        if self.hours_left <= 0:
            self.set_kind(self.choose_next(hour))

        rate = 3.0 / WEATHER_TRANSITION_S  # ~95 % of the way in one transition time
        target = TARGETS[self.kind]
        self.params = WeatherParams(*(approach(v, t, rate, dt) for v, t in
                                      zip(self.params.as_tuple(), target.as_tuple())))

        # slowly veering wind
        self.wind_angle = (self.wind_angle + dt * 0.01 * (0.5 + self.params.wind)) % (2 * math.pi)

        p = self.params
        rain_only = p.rain * (1.0 - p.snow)
        wet_up, dry = WETNESS_RATES
        self.wetness = min(1.0, max(0.0, self.wetness + dt * (wet_up * rain_only - dry * (1.0 - rain_only))))
        fall, melt = SNOW_COVER_RATES
        snowing = p.rain * p.snow
        self.snow_cover = min(1.0, max(0.0, self.snow_cover + dt * (fall * snowing - melt * (1.0 - snowing))))

    @property
    def wind_direction(self):
        return math.cos(self.wind_angle), math.sin(self.wind_angle)

    @property
    def name(self):
        return NAMES[self.kind]
