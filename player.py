import random
import pygame as pg
from camera import Camera
from settings import *
import physics
from mobs.mob import Mob, wrap_angle, turn_towards, locomotion_blend

# Movement keys: ZQSD (AZERTY), WASD (QWERTY) and arrows all work.
KEYS_FORWARD = (pg.K_z, pg.K_w, pg.K_UP)
KEYS_BACK = (pg.K_s, pg.K_DOWN)
KEYS_LEFT = (pg.K_q, pg.K_a, pg.K_LEFT)
KEYS_RIGHT = (pg.K_d, pg.K_RIGHT)
KEYS_JUMP_UP = (pg.K_SPACE,)   # jump when walking, up when flying
KEYS_DOWN = (pg.K_LSHIFT,)     # down when flying
KEYS_SPRINT = (pg.K_LCTRL,)
KEY_TOGGLE_FLY = pg.K_f
KEY_TOGGLE_VIEW = pg.K_F5

VIEW_FIRST_PERSON, VIEW_BEHIND, VIEW_FRONT = range(3)
VIEW_NAMES = ('first person', 'third person (behind)', 'third person (front)')
KNOCKBACK_DECAY = 5.0   # 1/s

JUMP_SPEED = math.sqrt(2 * GRAVITY * JUMP_HEIGHT)


class Player(Camera, Mob):
    """The player: a camera at the eyes of a human mob (visible in third person view)."""
    asset_name = 'player'
    width = PLAYER_WIDTH
    height = PLAYER_HEIGHT

    def __init__(self, app, position=PLAYER_POS, yaw=-90, pitch=0, aspect_ratio=16 / 9):
        super().__init__(position, yaw, pitch, aspect_ratio)
        # feet: center of the bottom of the player box; position = eyes (aim, interactions)
        self.init_mob(app, glm.vec3(position) - glm.vec3(0, PLAYER_EYE_HEIGHT, 0), self.yaw)
        self.was_in_water = False
        self.view_mode = VIEW_FIRST_PERSON
        self.knockback = glm.vec3(0)  # horizontal push (blocks/s) from hits, fades out
        self.shake = 0.0              # seconds of camera shake left

    # ------------------------------------------------------------------ setup
    def spawn(self, x=CENTER_XZ, z=CENTER_XZ):
        """Place the player standing on the ground of column (x, z)."""
        world = self.app.scene.world
        ground = world.surface_height(int(math.floor(x)), int(math.floor(z)))
        self.feet = glm.vec3(x + 0.5, ground + physics.EPS, z + 0.5)
        self.velocity = glm.vec3(0)
        self.on_ground = True
        self.body_yaw = self.yaw
        self.sync_camera()

    def restore(self, state):
        """Put the player back where the world was saved."""
        self.feet = glm.vec3(state['x'], state['y'], state['z'])
        self.yaw, self.pitch, self.fly = state['yaw'], state['pitch'], state['fly']
        self.velocity = glm.vec3(0)
        self.on_ground = False
        self.body_yaw = self.yaw
        self.sync_camera()
        self.update_vectors()

    def sync_camera(self):
        self.position = self.feet + glm.vec3(0, PLAYER_EYE_HEIGHT, 0)

    def intersects_block(self, x, y, z):
        """Does the player box overlap the unit block at integer (x, y, z)?"""
        hw = PLAYER_WIDTH * 0.5
        fx, fy, fz = self.feet
        return (fx - hw < x + 1 and fx + hw > x and
                fy < y + 1 and fy + PLAYER_HEIGHT > y and
                fz - hw < z + 1 and fz + hw > z)

    # ------------------------------------------------------------------ update
    def update(self):
        if self.app.mouse_captured:
            self.mouse_control()
        self.update_vectors()  # movement directions follow the new view first
        self.physics_update()
        self.update_animation(self.app.delta_time * 0.001)
        super().update()  # camera: view vectors, render camera (update_view), view matrix

    def handle_event(self, event):
        if not self.app.mouse_captured:
            return
        # left button: hold to break (cracks appear), click to place; right: switch mode
        voxel_handler = self.app.scene.world.voxel_handler
        if event.type == pg.MOUSEBUTTONDOWN:
            if event.button == 1:
                if voxel_handler.interaction_mode:
                    voxel_handler.set_voxel()
                else:
                    voxel_handler.breaking = True
            if event.button == 3:
                voxel_handler.switch_mode()
        if event.type == pg.MOUSEBUTTONUP and event.button == 1:
            voxel_handler.breaking = False
        if event.type == pg.KEYDOWN:
            self.keyboard_event(event)

    def mouse_control(self):
        mouse_dx, mouse_dy = pg.mouse.get_rel()
        if mouse_dx:
            self.rotate_yaw(delta_x=mouse_dx * MOUSE_SENSITIVITY)
        if mouse_dy:
            self.rotate_pitch(delta_y=mouse_dy * MOUSE_SENSITIVITY)

    def read_input(self):
        """Return (wish direction, vertical input, sprint) from the keyboard."""
        if not self.app.mouse_captured:
            return glm.vec3(0), 0, False
        key_state = pg.key.get_pressed()

        def pressed(keys):
            return any(key_state[k] for k in keys)

        wish = glm.vec3(0)
        if pressed(KEYS_FORWARD):
            wish += self.forward
        if pressed(KEYS_BACK):
            wish -= self.forward
        if pressed(KEYS_RIGHT):
            wish += self.right
        if pressed(KEYS_LEFT):
            wish -= self.right
        vertical = int(pressed(KEYS_JUMP_UP)) - int(pressed(KEYS_DOWN))
        return wish, vertical, pressed(KEYS_SPRINT)

    def physics_update(self):
        dt = self.app.delta_time * 0.001  # ms -> s
        wish, vertical, sprint = self.read_input()
        speed = PLAYER_SPEED * 1000  # blocks / s

        if self.fly:
            # no gravity, collisions on, no auto step
            speed = FLY_SPEED
            if sprint:
                speed *= PLAYER_SPRINT_FACTOR
            move = wish + glm.vec3(0, vertical, 0)
            velocity = glm.normalize(move) * speed if glm.length(move) > 0 else glm.vec3(0)
            step_height = 0.0
        else:
            if sprint:
                speed *= WALK_SPRINT_FACTOR
            wish.y = 0
            in_water = self.feet.y < WATER_LINE
            if in_water:
                speed *= WATER_SPEED_FACTOR
            horizontal = glm.normalize(wish) * speed if glm.length(wish) > 0 else glm.vec3(0)

            if in_water:
                if not self.was_in_water and self.velocity.y < 0:
                    self.velocity.y *= WATER_ENTRY_DAMPING  # splash: plunging brakes hard
                # buoyancy + drag; Space swims up, Left Shift dives
                vy = physics.water_vertical_velocity(
                    self.velocity.y, dt, vertical, WATER_GRAVITY, WATER_DRAG, SWIM_UP_ACCEL, DIVE_ACCEL)
                if vertical > 0 and self.feet.y > WATER_LINE - 1.0 and self.touching_wall(horizontal):
                    vy = max(vy, WATER_CLIMB_SPEED)  # hoist out onto the bank
            else:
                vy = self.velocity.y - GRAVITY * min(dt, physics.MAX_DT)
                if vertical > 0 and self.on_ground:
                    vy = JUMP_SPEED
            horizontal += self.knockback
            velocity = glm.vec3(horizontal.x, max(vy, -MAX_FALL_SPEED), horizontal.z)
            step_height = STEP_HEIGHT
        self.knockback *= math.exp(-KNOCKBACK_DECAY * min(dt, physics.MAX_DT))

        self.was_in_water = not self.fly and self.feet.y < WATER_LINE
        feet, vel, self.on_ground = physics.step(
            tuple(self.feet), tuple(velocity), dt, self.app.scene.world.block_height,
            PLAYER_WIDTH, PLAYER_HEIGHT, step_height, self.on_ground,
            step_anywhere=not self.fly and self.feet.y < WATER_LINE,
        )
        self.feet = glm.vec3(feet)
        self.velocity = glm.vec3(vel)
        self.sync_camera()

    @property
    def in_water(self):
        return self.feet.y < WATER_LINE

    @property
    def head_underwater(self):
        return self.position.y < WATER_LINE

    def touching_wall(self, horizontal):
        """Is there a block right in front of the player in the moving direction?"""
        if glm.length(horizontal) == 0:
            return False
        probe = self.feet + glm.normalize(horizontal) * 0.1
        return physics.collides(tuple(probe), PLAYER_WIDTH, PLAYER_HEIGHT, self.app.scene.world.block_height)

    def keyboard_event(self, event):
        # One pulse key handling
        if event.key == KEY_TOGGLE_FLY:
            self.fly = not self.fly
            self.velocity = glm.vec3(0)  # leaving fly mode: start falling from rest
        elif event.key == KEY_TOGGLE_VIEW:
            self.view_mode = (self.view_mode + 1) % len(VIEW_NAMES)

    # ------------------------------------------------------------------ hits
    def push(self, horizontal, up=0.0):
        """Knock the player back (a mob hit): horizontal push + small hop, camera shake."""
        self.knockback += glm.vec3(horizontal.x, 0.0, horizontal.z)
        if not self.fly and up > 0:
            self.velocity.y = max(self.velocity.y, up)
            self.on_ground = False
        self.shake = 0.25

    # ------------------------------------------------------------------ body animation
    @property
    def swimming(self):
        return not self.fly and self.water_depth > SWIM_DEPTH

    def animate(self, dt):
        speed = self.horizontal_speed
        moving = speed > 0.3
        self.air_time = 0.0 if self.on_ground else self.air_time + dt

        # body: faces the moving direction, else turns to the view when it looks too far aside
        target = self.body_yaw
        if moving:
            target = math.atan2(self.velocity.z, self.velocity.x)
        elif abs(wrap_angle(self.yaw - self.body_yaw)) > math.radians(50) or self.view_mode == VIEW_FIRST_PERSON:
            target = self.yaw
        self.body_yaw = turn_towards(self.body_yaw, target, BODY_TURN_SPEED * dt)

        anim = self.animator
        head_pitch_share = 1.0
        if self.fly:
            anim.set_state('fly' if moving else 'fly_idle')
            head_pitch_share = 0.5
        elif self.swimming:
            if moving:
                anim.set_state('swim', rate=max(0.7, speed / SWIM_ANIM_SPEED))
            else:
                anim.set_state('swim_idle')
            head_pitch_share = 0.4
        elif not self.on_ground and (self.velocity.y > 2.0 or self.air_time > 0.2) and self.water_depth <= 0:
            if self.velocity.y > 0:
                anim.set_state('jump', loop=False, fade=0.1)
            else:
                anim.set_state('fall', fade=0.3)
        elif not moving:
            anim.set_state('idle', fade=0.25)
        else:
            w_walk, w_run, rate = locomotion_blend(speed, WALK_ANIM_SPEED, RUN_ANIM_SPEED,
                                                   walk_top=PLAYER_SPEED * 1000 * 1.1,
                                                   run_from=PLAYER_SPEED * 1000 * WALK_SPRINT_FACTOR * 0.9)
            anim.set_blend('move', {'walk': w_walk, 'run': w_run}, rate=rate)

        yaw_offset = max(-HEAD_MAX_YAW, min(HEAD_MAX_YAW, wrap_angle(self.yaw - self.body_yaw)))
        pitch = max(-HEAD_MAX_PITCH, min(HEAD_MAX_PITCH, self.pitch)) * head_pitch_share
        self.aim_head(yaw_offset, pitch, (('neck', 0.4), ('head', 0.6)))

    # ------------------------------------------------------------------ view
    def update_view(self):
        if self.view_mode == VIEW_FIRST_PERSON:
            super().update_view()
            self.visible = False
        else:
            self.visible = True
            back = -self.look if self.view_mode == VIEW_BEHIND else glm.vec3(self.look)
            side, rise = CAMERA_SHOULDER
            view_dir = -back
            right = glm.normalize(glm.cross(view_dir, glm.vec3(0, 1, 0)))
            offset = back * CAMERA_DISTANCE + right * side + glm.vec3(0, rise, 0)
            length = glm.length(offset)
            distance = self.camera_clearance(self.position, offset / length, length)
            self.view_position = self.position + offset * (distance / length)
            self.view_dir = view_dir
            self.view_up = glm.normalize(glm.cross(right, self.view_dir))
        if self.shake > 0:
            self.shake = max(0.0, self.shake - self.app.delta_time * 0.001)
            amount = 0.12 * self.shake
            self.view_position += glm.vec3(random.uniform(-amount, amount), random.uniform(-amount, amount),
                                           random.uniform(-amount, amount))

    def camera_clearance(self, origin, direction, max_distance):
        """How far the camera can go from ``origin`` along ``direction`` before entering a block."""
        block_height = self.app.scene.world.block_height
        step = 0.05
        t = 0.0
        while t < max_distance + CAMERA_MARGIN:
            t += step
            p = origin + direction * t
            x, y, z = math.floor(p.x), math.floor(p.y), math.floor(p.z)
            h = block_height(x, y, z)
            if h > 0 and p.y < y + h:
                return max(0.0, min(max_distance, t - CAMERA_MARGIN))
        return max_distance

    @property
    def camera_underwater(self):
        """Is the render camera below the water line (underwater ambiance)?"""
        return self.view_position.y < WATER_LINE
