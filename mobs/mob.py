"""Mobs: animated creatures with a collision box (the player is one too, seen from outside)."""
import math

import numpy as np

from settings import *
import physics
from models import load_asset
from models.animation import Animator, rotation_matrix


def wrap_angle(a):
    """Angle in [-pi, pi)."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def turn_towards(current, target, max_step):
    """Rotate ``current`` towards ``target`` by at most ``max_step`` radians (shortest way)."""
    diff = wrap_angle(target - current)
    if abs(diff) <= max_step:
        return target
    return current + math.copysign(max_step, diff)


def locomotion_blend(speed, walk_speed, run_speed, walk_top=None, run_from=None):
    """(walk weight, run weight, playback rate) for a ground speed.

    Pure walk up to ``walk_top``, pure run from ``run_from``, cross-faded between;
    the rate makes the feet cover exactly ``speed`` (no sliding).
    """
    walk_top = walk_speed * 1.6 if walk_top is None else walk_top
    run_from = run_speed * 0.9 if run_from is None else run_from
    w_run = min(max((speed - walk_top) / max(run_from - walk_top, 1e-6), 0.0), 1.0)
    w_walk = 1.0 - w_run
    nominal = w_walk * walk_speed + w_run * run_speed
    return w_walk, w_run, speed / nominal


def yaw_to_model_angle(yaw):
    """Model rotation around Y for a game yaw (models face +Z, the game's forward is (cos, 0, sin))."""
    return math.pi / 2 - yaw


class Mob:
    """Body state, physics and animation shared by every creature.

    Subclasses choose the animation (``animate``) and, for NPCs, the behaviour.
    """
    asset_name = None
    width = 0.6
    height = 1.8
    step_height = STEP_HEIGHT

    def init_mob(self, app, feet, yaw=0.0):
        self.app = app
        self.asset = load_asset(self.asset_name)
        self.animator = Animator(self.asset.skeleton, self.asset.clips, fade=ANIM_FADE)
        self.feet = glm.vec3(feet)
        self.velocity = glm.vec3(0)
        self.on_ground = False
        self.body_yaw = yaw            # direction the body faces (radians, game convention)
        self.air_time = 0.0
        self.tint = glm.vec3(0)
        self.look_extra = {}           # node index -> 3x3 model-space rotation (head aiming)
        self.visible = True

    # ------------------------------------------------------------------ state
    @property
    def world(self):
        return self.app.scene.world

    @property
    def water_depth(self):
        return WATER_LINE - self.feet.y

    @property
    def horizontal_speed(self):
        return math.hypot(self.velocity.x, self.velocity.z)

    @property
    def center(self):
        return self.feet + glm.vec3(0, self.height * 0.5, 0)

    # ------------------------------------------------------------------ physics (NPCs)
    def physics_step(self, wish, dt, jump=False, swim_up=False):
        """Walk / swim with gravity and collisions. ``wish``: desired horizontal velocity."""
        in_water = self.feet.y < WATER_LINE
        vy = self.velocity.y
        if in_water:
            vy = physics.water_vertical_velocity(vy, dt, 1 if swim_up else 0, WATER_GRAVITY, WATER_DRAG,
                                                 SWIM_UP_ACCEL, DIVE_ACCEL)
        else:
            vy -= GRAVITY * min(dt, physics.MAX_DT)
            if jump and self.on_ground:
                vy = math.sqrt(2 * GRAVITY * JUMP_HEIGHT)
        velocity = (wish.x, max(vy, -MAX_FALL_SPEED), wish.z)
        feet, vel, self.on_ground = physics.step(
            tuple(self.feet), velocity, dt, self.world.block_height, self.width, self.height,
            self.step_height, self.on_ground, step_anywhere=in_water)
        self.feet = glm.vec3(feet)
        self.velocity = glm.vec3(vel)
        self.air_time = 0.0 if self.on_ground else self.air_time + dt

    def blocked_ahead(self, direction, distance=0.15):
        """Is a block right in front of the box in ``direction`` (horizontal unit vector)?"""
        probe = self.feet + direction * distance
        probe.y += self.step_height + 0.01  # what the auto step cannot climb
        return physics.collides(tuple(probe), self.width, self.height - self.step_height - 0.01,
                                self.world.block_height)

    # ------------------------------------------------------------------ animation / rendering
    def animate(self, dt):
        """Choose the animation state; called every frame before ``update_animation``."""

    def update_animation(self, dt):
        self.animate(dt)
        self.animator.update(dt)

    def model_matrix(self):
        m = glm.translate(glm.mat4(), self.feet)
        return glm.rotate(m, yaw_to_model_angle(self.body_yaw), glm.vec3(0, 1, 0))

    def skin_matrices(self):
        return self.animator.skin_matrices(self.look_extra or None)

    def aim_head(self, yaw_offset, pitch, nodes_weights):
        """Turn the head by ``yaw_offset`` (relative to the body) and ``pitch`` (up > 0).

        nodes_weights: [(node name, share)] split of the rotation along the neck.
        """
        sk = self.asset.skeleton
        extra = {}
        for name, share in nodes_weights:
            rot = rotation_matrix((0, 1, 0), -yaw_offset * share) @ rotation_matrix((1, 0, 0), -pitch * share)
            extra[sk.index(name)] = rot
        self.look_extra = extra
