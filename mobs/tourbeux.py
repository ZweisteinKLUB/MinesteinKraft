"""The Tourbeux: hostile brute of peat and mossy stone that walks on its knuckles.

It wanders slowly on land, charges the player it sees, rears up and slams its
fists to knock the player back. It fears water: it never walks into it, so
swimming away is a way to escape. No damage for now (knockback only).
"""
import math
import random

from settings import *
from mobs.mob import Mob, turn_towards, locomotion_blend, wrap_angle

WANDER, CHASE, ATTACK = 'wander', 'chase', 'attack'
SIGHT_CHECK_INTERVAL = 0.25


class Tourbeux(Mob):
    asset_name = 'tourbeux'
    width = 0.9
    height = 1.5
    step_height = STEP_HEIGHT
    model_offset = -0.2   # its head reaches forward: center the body on the collision box
    eye_height = 1.2

    def __init__(self, app, feet, yaw=0.0, rng=None):
        self.init_mob(app, feet, yaw)
        self.rng = rng or random.Random()
        self.state = WANDER
        self.wander_target = None
        self.wait = self.rng.uniform(0.5, 2.5)
        self.cooldown = 0.0
        self.attack_time = 0.0
        self.struck = False
        self.last_seen = -1e9   # time the player was last seen
        self.clock = 0.0
        self.sight_timer = 0.0
        self.sees_player = False
        self.blocked_time = 0.0
        self.last_land = glm.vec3(self.feet)
        self.wish = glm.vec3(0)

    # ------------------------------------------------------------------ senses
    @property
    def player(self):
        return self.app.player

    def to_player(self):
        d = self.player.feet - self.feet
        return glm.vec3(d.x, 0.0, d.z), d.y

    def line_of_sight(self, target):
        """No block between the eyes and ``target`` (sampled every 0.25 block)."""
        eyes = self.feet + glm.vec3(0, self.eye_height, 0)
        delta = target - eyes
        dist = glm.length(delta)
        if dist == 0:
            return True
        step = delta / dist * 0.25
        p = glm.vec3(eyes)
        block_height = self.world.block_height
        for _ in range(int(dist / 0.25)):
            p += step
            x, y, z = math.floor(p.x), math.floor(p.y), math.floor(p.z)
            h = block_height(x, y, z)
            if h > 0 and p.y < y + h:
                return False
        return True

    def player_in_reach(self, dist, dy):
        """Can the player be chased: on land or wading, not flying out of reach."""
        p = self.player
        return dist <= TOURBEUX_GIVE_UP_RANGE and -3.0 < dy < 3.0 and p.water_depth < SWIM_DEPTH

    def is_water(self, x, z):
        """Is the column at (x, z) open water (its top below the water line)?"""
        top = self.world.surface_height(math.floor(x), math.floor(z))
        return top <= WATER_LINE

    def water_ahead(self, direction, distance=0.9):
        probe = self.feet + direction * distance
        return self.is_water(probe.x, probe.z)

    # ------------------------------------------------------------------ behaviour
    def update(self, dt):
        self.clock += dt
        self.cooldown = max(0.0, self.cooldown - dt)
        flat, dy = self.to_player()
        dist = glm.length(flat)

        self.sight_timer -= dt
        if self.sight_timer <= 0:
            self.sight_timer = SIGHT_CHECK_INTERVAL
            p = self.player
            self.sees_player = (dist <= TOURBEUX_DETECT_RANGE and self.player_in_reach(dist, dy)
                                and self.line_of_sight(p.feet + glm.vec3(0, PLAYER_EYE_HEIGHT * 0.8, 0)))
            if self.sees_player:
                self.last_seen = self.clock

        wish = glm.vec3(0)
        jump = False
        face = None

        if self.state == ATTACK:
            self.attack_time += dt
            face = flat
            duration = self.animator.clips['attack'].duration
            if not self.struck and self.attack_time >= TOURBEUX_IMPACT * duration:
                self.struck = True
                self.strike(flat, dist, dy)
            if self.attack_time >= duration:
                self.state = CHASE
                self.cooldown = TOURBEUX_ATTACK_COOLDOWN
        else:
            chasing = (self.clock - self.last_seen <= TOURBEUX_MEMORY) and self.player_in_reach(dist, dy)
            self.state = CHASE if chasing else WANDER
            if self.state == CHASE:
                face = flat
                if dist <= TOURBEUX_ATTACK_RANGE:
                    if self.cooldown <= 0 and abs(dy) < 1.5:
                        self.start_attack()
                elif dist > 0:
                    direction = flat / dist
                    if not self.water_ahead(direction):
                        wish = direction * TOURBEUX_CHARGE_SPEED
                    # else: stops at the shore and waits, facing the player
            else:
                wish = self.wander(dt)

        in_water = self.feet.y < WATER_LINE
        if in_water:   # fell or was pushed in: get back to the last land position
            back = self.last_land - self.feet
            back.y = 0
            if glm.length(back) > 0.1:
                wish = glm.normalize(back) * TOURBEUX_WANDER_SPEED * 1.5
        elif self.on_ground:
            self.last_land = glm.vec3(self.feet)

        if glm.length(wish) > 0:
            direction = glm.normalize(wish)
            if self.on_ground and self.blocked_ahead(direction):
                jump = True
            face = face if face is not None and glm.length(face) > 0 else wish
        self.wish = wish
        self.physics_step(wish, dt, jump=jump, swim_up=in_water)
        if face is not None and glm.length(face) > 1e-6:
            self.body_yaw = turn_towards(self.body_yaw, math.atan2(face.z, face.x), 6.0 * dt)

    def wander(self, dt):
        if self.wait > 0:
            self.wait -= dt
            return glm.vec3(0)
        if self.wander_target is None:
            angle = self.rng.uniform(0, 2 * math.pi)
            r = self.rng.uniform(3.0, 8.0)
            target = self.feet + glm.vec3(math.cos(angle) * r, 0, math.sin(angle) * r)
            if self.is_water(target.x, target.z):
                self.wait = self.rng.uniform(0.5, 1.5)
                return glm.vec3(0)
            self.wander_target = target
            self.blocked_time = 0.0
        to = self.wander_target - self.feet
        to.y = 0
        d = glm.length(to)
        direction = to / d if d > 0 else glm.vec3(0)
        if d < 0.5 or self.blocked_time > 2.0 or (d > 0 and self.water_ahead(direction)):
            self.wander_target = None
            self.wait = self.rng.uniform(2.0, 5.0)
            return glm.vec3(0)
        if self.horizontal_speed < 0.2 * TOURBEUX_WANDER_SPEED:
            self.blocked_time += dt
        return direction * TOURBEUX_WANDER_SPEED

    def start_attack(self):
        self.state = ATTACK
        self.attack_time = 0.0
        self.struck = False
        self.animator.play_once('attack', fade=0.1)

    def strike(self, flat, dist, dy):
        """Impact of the fists: knock the player back if still in reach."""
        if dist <= TOURBEUX_ATTACK_RANGE + 0.6 and abs(dy) < 1.8:
            direction = flat / dist if dist > 1e-6 else glm.vec3(math.cos(self.body_yaw), 0, math.sin(self.body_yaw))
            self.player.push(direction * TOURBEUX_KNOCKBACK, TOURBEUX_KNOCKBACK_UP)
            return True
        return False

    # ------------------------------------------------------------------ animation
    def animate(self, dt):
        speed = self.horizontal_speed
        if speed < 0.15:
            self.animator.set_state('idle', fade=0.3)
        else:
            w_walk, w_charge, rate = locomotion_blend(
                speed, TOURBEUX_WALK_ANIM_SPEED, TOURBEUX_CHARGE_ANIM_SPEED,
                walk_top=TOURBEUX_WANDER_SPEED * 1.3, run_from=TOURBEUX_CHARGE_SPEED * 0.8)
            self.animator.set_blend('move', {'walk': w_walk, 'charge': w_charge}, rate=rate)
        # head turned towards the player when chasing
        if self.state != WANDER:
            flat, dy = self.to_player()
            yaw_to = math.atan2(flat.z, flat.x) if glm.length(flat) > 1e-6 else self.body_yaw
            yaw_offset = max(-0.8, min(0.8, wrap_angle(yaw_to - self.body_yaw)))
            self.aim_head(yaw_offset, 0.0, (('neck', 0.5), ('head', 0.5)))
        else:
            self.look_extra = {}
