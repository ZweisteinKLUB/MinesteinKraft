"""Accelerated day / night cycle: time of day, sun, moon and the rotating starry sky.

World axes: +x is east, -x west, +z south, +y up. The sun rises in the east, culminates in
the south at ``90° - LATITUDE`` and sets in the west. The moon follows the same arc, late on
the sun by its phase: new moon next to the sun, full moon opposite (up all night).
"""
from settings import glm, math, DAY_LENGTH, LATITUDE, LUNAR_CYCLE_DAYS, START_HOUR

TAU = 2.0 * math.pi
_LAT = math.radians(LATITUDE)
# axis of the daily rotation of the sky (perpendicular to the plane of the sun's arc)
SKY_AXIS = glm.vec3(0.0, -math.sin(_LAT), math.cos(_LAT))


def arc_direction(angle):
    """Unit direction of a body at ``angle`` on the daily arc (0 rising east, pi/2 culminating)."""
    c, s = math.cos(angle), math.sin(angle)
    return glm.vec3(c, s * math.cos(_LAT), s * math.sin(_LAT))


def sun_angle(day_fraction):
    """Angle on the arc for a time of day in [0, 1): 6 h rises, 12 h culminates, 18 h sets."""
    return TAU * (day_fraction - 0.25)


class DayCycle:
    """Game clock. ``hours`` in [0, 24), ``day`` counts the days since the world was created."""

    def __init__(self, hours=START_HOUR, day=0, day_length=DAY_LENGTH):
        self.hours = float(hours) % 24.0
        self.day = int(day)
        self.day_length = day_length  # real seconds per game day

    # ------------------------------------------------------------------ clock
    def advance(self, seconds):
        """Move the clock by ``seconds`` of real time."""
        self.advance_hours(seconds * 24.0 / self.day_length)

    def advance_hours(self, hours):
        total = self.hours + hours
        days, self.hours = divmod(total, 24.0)
        self.day += int(days)

    @property
    def fraction(self):
        """Time of day in [0, 1) (0.5 = noon)."""
        return self.hours / 24.0

    @property
    def days(self):
        """Continuous time in days (for slow cycles: moon phase, star twinkle seeds)."""
        return self.day + self.fraction

    # ------------------------------------------------------------------ sky bodies
    @property
    def sun_direction(self):
        return arc_direction(sun_angle(self.fraction))

    @property
    def moon_phase(self):
        """0 = new moon, 0.5 = full moon."""
        return (self.days / LUNAR_CYCLE_DAYS) % 1.0

    @property
    def moon_illumination(self):
        """Lit fraction of the moon disk (0 new, 1 full)."""
        return 0.5 - 0.5 * math.cos(TAU * self.moon_phase)

    @property
    def moon_direction(self):
        return arc_direction(sun_angle(self.fraction) - TAU * self.moon_phase)

    @property
    def sky_rotation(self):
        """Rotation of the celestial sphere (stars) at this time: celestial -> world."""
        return glm.rotate(glm.mat4(), sun_angle(self.fraction) + TAU * self.days / 365.0, SKY_AXIS)

    def clock_text(self):
        h = int(self.hours)
        m = int((self.hours - h) * 60)
        return f'{h:02d}:{m:02d}'
