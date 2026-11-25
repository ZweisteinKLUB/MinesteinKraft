"""Items lying in the world: a broken block leaves a small copy of itself that falls, rests on
the ground (floats in the sea) and is picked up when the player walks close to it.

Pure Python (no OpenGL): render/drops.py draws them.
"""
import json
import math
import random

from settings import glm, GRAVITY, WATER_LINE
import physics

DROP_SIZE = 0.25          # blocks
PICKUP_DELAY = 0.5        # s before a new drop can be picked up (it is seen popping out)
PICKUP_RADIUS = 2.2       # blocks from the player's body (feet to head): attracted
COLLECT_RADIUS = 0.45     # close enough: in the inventory
ATTRACT_SPEED = 9.0       # blocks/s
DROP_LIFETIME = 900.0     # s before a forgotten drop disappears
MAX_DROPS = 400
MAX_FALL_SPEED = 30.0
WATER_RISE = 1.2          # blocks/s: items float up to the surface


class Drop:
    def __init__(self, item, feet, velocity=None, count=1, age=0.0, spin=0.0):
        self.item = item
        self.count = count
        self.feet = glm.vec3(feet)  # center of the bottom of its box
        self.velocity = glm.vec3(velocity) if velocity is not None else glm.vec3(0)
        self.age = age
        self.spin = spin            # rotation around y (radians)
        self.on_ground = False
        self.attracted = False

    @property
    def center(self):
        return self.feet + glm.vec3(0, DROP_SIZE * 0.5, 0)

    def physics(self, dt, block_height):
        v = self.velocity
        in_water = self.feet.y + DROP_SIZE * 0.5 < WATER_LINE + 0.01
        if in_water:
            # buoyant: rises to the surface, strongly braked
            v.y += (WATER_RISE - v.y) * min(1.0, 3.0 * dt)
            damp = math.exp(-3.0 * dt)
            v.x *= damp
            v.z *= damp
        else:
            v.y = max(v.y - GRAVITY * dt, -MAX_FALL_SPEED)
            damp = math.exp(-(10.0 if self.on_ground else 0.5) * dt)
            v.x *= damp
            v.z *= damp
        if self.on_ground and not in_water and abs(v.x) + abs(v.z) < 1e-3:
            # resting: nothing to do while the block below is still there
            below = block_height(math.floor(self.feet.x), math.floor(self.feet.y - 0.01), math.floor(self.feet.z))
            if below > 0 and not block_height(math.floor(self.feet.x), math.floor(self.feet.y + 0.01),
                                              math.floor(self.feet.z)):
                v.y = 0.0
                return
        if physics.collides(tuple(self.feet), DROP_SIZE, DROP_SIZE, block_height):
            # a block was placed over it: pushed up out of it
            self.feet.y = math.floor(self.feet.y) + 1.0 + physics.EPS
            self.velocity = glm.vec3(0)
            return
        feet, vel, self.on_ground = physics.step(tuple(self.feet), tuple(v), dt, block_height,
                                                 DROP_SIZE, DROP_SIZE, on_ground=self.on_ground)
        self.feet, self.velocity = glm.vec3(feet), glm.vec3(vel)
        if in_water and self.feet.y + DROP_SIZE * 0.5 > WATER_LINE:
            # floating at the surface
            self.feet.y = WATER_LINE - DROP_SIZE * 0.5
            self.velocity.y = 0.0


class DropManager:
    """The drops of the world: spawned by broken blocks, picked up into the inventory."""

    def __init__(self, block_height, rng=None):
        self.block_height = block_height  # world collision callback (see physics.py)
        self.rng = rng or random.Random()
        self.drops = []

    def __len__(self):
        return len(self.drops)

    def spawn(self, item, block_pos, count=1):
        """A broken block at integer ``block_pos`` leaves an item popping out of its middle."""
        r = self.rng
        x, y, z = block_pos
        feet = glm.vec3(x + 0.5, y + 0.5 - DROP_SIZE * 0.5, z + 0.5)
        velocity = glm.vec3(r.uniform(-1.2, 1.2), r.uniform(3.5, 5.0), r.uniform(-1.2, 1.2))
        self.add(Drop(item, feet, velocity, count, spin=r.uniform(0, math.tau)))

    def throw(self, item, count, eye, look):
        """Items thrown by the player (out of the backpack screen)."""
        feet = glm.vec3(eye) + glm.vec3(look) * 0.6 - glm.vec3(0, 0.3, 0)
        velocity = glm.vec3(look) * 5.0 + glm.vec3(0, 2.0, 0)
        drop = Drop(item, feet, velocity, count, spin=self.rng.uniform(0, math.tau))
        drop.age = -1.5  # not picked up again at once
        self.add(drop)

    def add(self, drop):
        self.drops.append(drop)
        if len(self.drops) > MAX_DROPS:
            del self.drops[0]  # the oldest goes

    def update(self, dt, player_feet=None, inventory=None, player_height=1.8):
        """Move the drops; those near the player (body from ``player_feet`` up ``player_height``)
        fly to it and go in ``inventory``. Returns the number of items picked up."""
        picked = 0
        kept = []
        for d in self.drops:
            d.age += dt
            d.spin = (d.spin + dt * 1.6) % math.tau
            if d.age > DROP_LIFETIME:
                continue
            if player_feet is not None and inventory is not None and d.age > PICKUP_DELAY:
                c = d.center
                body = glm.vec3(player_feet)
                body.y = min(max(c.y, body.y), body.y + player_height)  # closest point of the body
                to_player = body - c
                dist = glm.length(to_player)
                if dist < COLLECT_RADIUS:
                    left = inventory.add(d.item, d.count)
                    picked += d.count - left
                    if left == 0:
                        continue
                    d.count = left
                    d.attracted = False
                elif dist < PICKUP_RADIUS and inventory.can_add(d.item):
                    d.attracted = True
                    step = min(dist, ATTRACT_SPEED * dt)
                    d.feet += to_player / max(dist, 1e-6) * step
                    d.velocity = glm.vec3(0)
                    kept.append(d)
                    continue
                else:
                    d.attracted = False
            d.physics(dt, self.block_height)
            kept.append(d)
        self.drops = kept
        return picked

    # ------------------------------------------------------------------ save
    def to_json(self):
        return json.dumps([[d.item, d.count, round(d.feet.x, 3), round(d.feet.y, 3), round(d.feet.z, 3),
                            round(d.age, 1)] for d in self.drops])

    def load_json(self, text):
        self.drops = []
        if not text:
            return
        try:
            for item, count, x, y, z, age in json.loads(text):
                self.drops.append(Drop(int(item), (x, y, z), count=int(count), age=float(age),
                                       spin=self.rng.uniform(0, math.tau)))
        except (ValueError, TypeError):
            self.drops = []
