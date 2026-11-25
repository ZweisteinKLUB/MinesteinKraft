"""Spawns hostile mobs on land around the player and removes the ones left far behind."""
import math
import random

from settings import *
import physics
from mobs.tourbeux import Tourbeux

SPAWN_GROUND = (GRASS, DIRT, SAND, STONE, SNOW)  # blocks a mob may appear on (not trees)
SPAWN_TRIES = 8


class MobManager:
    def __init__(self, app, rng=None, enabled=True):
        self.app = app
        self.rng = rng or random.Random()
        self.mobs = []
        self.enabled = enabled
        self.spawn_timer = SPAWN_INTERVAL

    @property
    def world(self):
        return self.app.scene.world

    def hostiles(self):
        return [m for m in self.mobs if isinstance(m, Tourbeux)]

    # ------------------------------------------------------------------ spawning
    def spawn_spot(self, x, z, width=Tourbeux.width, height=Tourbeux.height):
        """Feet position to stand on land at column (x, z), or None (water, tree, unloaded, no room)."""
        x, z = math.floor(x), math.floor(z)
        if not self.world.column_loaded(x // CHUNK_SIZE, z // CHUNK_SIZE):
            return None
        top = self.world.surface_height(x, z)
        if top <= WATER_LINE + 0.5:
            return None
        if self.world.voxel_at(x, top - 1, z) not in SPAWN_GROUND:
            return None
        feet = (x + 0.5, top + physics.EPS, z + 0.5)
        if physics.collides(feet, width, height, self.world.block_height):
            return None
        return glm.vec3(feet)

    def spawn_at(self, feet, yaw=None):
        mob = Tourbeux(self.app, feet, self.rng.uniform(-math.pi, math.pi) if yaw is None else yaw, rng=self.rng)
        mob.on_ground = True
        self.mobs.append(mob)
        return mob

    def try_spawn(self):
        center = self.app.player.feet
        lo, hi = SPAWN_DISTANCE
        for _ in range(SPAWN_TRIES):
            angle = self.rng.uniform(0, 2 * math.pi)
            r = self.rng.uniform(lo, hi)
            feet = self.spawn_spot(center.x + math.cos(angle) * r, center.z + math.sin(angle) * r)
            if feet is not None:
                return self.spawn_at(feet)
        return None

    # ------------------------------------------------------------------ update / render
    def despawn(self):
        center = self.app.player.feet
        kept = []
        for mob in self.mobs:
            far = math.hypot(mob.feet.x - center.x, mob.feet.z - center.z) > DESPAWN_DISTANCE
            unloaded = not self.world.column_loaded(math.floor(mob.feet.x) // CHUNK_SIZE,
                                                    math.floor(mob.feet.z) // CHUNK_SIZE)
            if not (far or unloaded):
                kept.append(mob)
        self.mobs = kept

    def update(self, dt):
        dt = min(dt, 0.1)
        self.despawn()
        if self.enabled:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn_timer = SPAWN_INTERVAL
                if len(self.hostiles()) < MAX_HOSTILES:
                    self.try_spawn()
        for mob in self.mobs:
            mob.update(dt)
            mob.update_animation(dt)

    def render(self, renderer):
        frustum = self.app.player.frustum
        for mob in self.mobs:
            if frustum.is_on_frustum(mob):
                renderer.render(mob)
