"""The sky state of a world: clock, weather, lightning, and the lighting they give.

Saved in the world database (meta table): time of day, day count and weather.
"""
import random
from dataclasses import dataclass
from settings import (glm, math, LIGHTNING_INTERVAL, LIGHTNING_DISTANCE, CLOUD_SPEED, CLOUD_ALTITUDE,
                      TIME_SKIP_HOURS, START_HOUR)
from atmosphere.daycycle import DayCycle
from atmosphere.weather import Weather, KINDS, CLEAR
from atmosphere.lighting import compute_lighting

FLASH_PULSES = ((0.0, 1.0), (0.09, 0.55), (0.22, 0.85), (0.38, 0.3))  # (start s, strength)
FLASH_DECAY = 18.0      # 1/s
BOLT_LIFETIME = 0.55    # seconds the bolt stays visible


@dataclass
class Strike:
    """A lightning strike: where it hits (relative to the player when it struck) and when."""
    x: float
    z: float
    seed: int
    age: float = 0.0

    def flash(self):
        """Light of the flash at this age (flickering pulses)."""
        return sum(strength * math.exp(-FLASH_DECAY * (self.age - start))
                   for start, strength in FLASH_PULSES if self.age >= start)

    @property
    def visible(self):
        return self.age < BOLT_LIFETIME


class Environment:
    def __init__(self, store=None, rng=None):
        self.rng = rng or random.Random()
        self.store = store
        hours, day, kind = START_HOUR, 0, CLEAR
        if store is not None:
            hours = float(store.get_meta('time_hours', hours))
            day = int(store.get_meta('day', day))
            saved = store.get_meta('weather', kind)
            kind = saved if saved in KINDS else CLEAR
        self.clock = DayCycle(hours, day)
        self.weather = Weather(kind, rng=self.rng)
        self.time = 0.0                 # real seconds since start (shader animations)
        self.cloud_offset = glm.vec2(self.rng.uniform(0, 5000), self.rng.uniform(0, 5000))
        self.strikes: list[Strike] = []
        self.next_strike = self.draw_strike_delay()
        self.lighting = None
        self.update(0.0)

    # ------------------------------------------------------------------ update
    def draw_strike_delay(self):
        return self.rng.uniform(*LIGHTNING_INTERVAL)

    def update(self, dt, player_pos=None):
        hours_before = self.clock.hours
        self.clock.advance(dt)
        game_hours = (self.clock.hours - hours_before) % 24.0
        self.time += dt
        self.weather.update(dt, game_hours, self.clock.hours)

        p = self.weather.params
        wx, wz = self.weather.wind_direction
        self.cloud_offset += glm.vec2(wx, wz) * (CLOUD_SPEED * (0.3 + p.wind) * dt)

        self.update_lightning(dt, player_pos)
        self.lighting = compute_lighting(self.clock.sun_direction, self.clock.moon_direction,
                                         self.clock.moon_illumination, p, self.flash)

    def update_lightning(self, dt, player_pos):
        for strike in self.strikes:
            strike.age += dt
        self.strikes = [s for s in self.strikes if s.age < 1.5]
        chance = self.weather.params.lightning
        if chance < 0.3:
            return
        self.next_strike -= dt * chance
        if self.next_strike <= 0:
            self.next_strike = self.draw_strike_delay()
            self.strike(player_pos)

    def strike(self, player_pos=None):
        """Lightning now, at a random distance around the player."""
        angle = self.rng.uniform(0, 2 * math.pi)
        dist = self.rng.uniform(*LIGHTNING_DISTANCE)
        px, pz = (player_pos.x, player_pos.z) if player_pos is not None else (0.0, 0.0)
        self.strikes.append(Strike(px + math.cos(angle) * dist, pz + math.sin(angle) * dist,
                                   self.rng.randrange(1 << 30)))

    @property
    def flash(self):
        return min(1.5, sum(s.flash() for s in self.strikes))

    # ------------------------------------------------------------------ controls
    def skip_time(self, hours=TIME_SKIP_HOURS):
        self.clock.advance_hours(hours)

    def next_weather(self):
        self.weather.cycle()

    # ------------------------------------------------------------------ queries
    @property
    def cloud_altitude(self):
        return CLOUD_ALTITUDE

    def status_text(self):
        return f'Jour {self.clock.day + 1}  {self.clock.clock_text()}  {self.weather.name}'

    # ------------------------------------------------------------------ saving
    def save(self):
        if self.store is None:
            return
        self.store.set_meta('time_hours', repr(self.clock.hours))
        self.store.set_meta('day', str(self.clock.day))
        self.store.set_meta('weather', self.weather.kind)
