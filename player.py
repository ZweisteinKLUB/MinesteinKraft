import pygame as pg
from camera import Camera
from settings import *
import physics

# Movement keys: ZQSD (AZERTY), WASD (QWERTY) and arrows all work.
KEYS_FORWARD = (pg.K_z, pg.K_w, pg.K_UP)
KEYS_BACK = (pg.K_s, pg.K_DOWN)
KEYS_LEFT = (pg.K_q, pg.K_a, pg.K_LEFT)
KEYS_RIGHT = (pg.K_d, pg.K_RIGHT)
KEYS_JUMP_UP = (pg.K_SPACE,)   # jump when walking, up when flying
KEYS_DOWN = (pg.K_LSHIFT,)     # down when flying
KEYS_SPRINT = (pg.K_LCTRL,)
KEY_TOGGLE_FLY = pg.K_f

JUMP_SPEED = math.sqrt(2 * GRAVITY * JUMP_HEIGHT)


class Player(Camera):
    def __init__(self, app, position=PLAYER_POS, yaw=-90, pitch=0, aspect_ratio=16 / 9):
        self.app = app
        super().__init__(position, yaw, pitch, aspect_ratio)
        # feet: center of the bottom of the player box; camera position = eyes
        self.feet = glm.vec3(position) - glm.vec3(0, PLAYER_EYE_HEIGHT, 0)
        self.velocity = glm.vec3(0)
        self.on_ground = False

    # ------------------------------------------------------------------ setup
    def spawn(self, x=CENTER_XZ, z=CENTER_XZ):
        """Place the player standing on the ground of column (x, z)."""
        world = self.app.scene.world
        ground = world.surface_height(int(math.floor(x)), int(math.floor(z)))
        self.feet = glm.vec3(x + 0.5, ground + physics.EPS, z + 0.5)
        self.velocity = glm.vec3(0)
        self.on_ground = True
        self.sync_camera()

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
        super().update()

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
            if sprint:
                speed *= PLAYER_SPRINT_FACTOR
            move = wish + glm.vec3(0, vertical, 0)
            velocity = glm.normalize(move) * speed if glm.length(move) > 0 else glm.vec3(0)
            step_height = 0.0
        else:
            if sprint:
                speed *= WALK_SPRINT_FACTOR
            wish.y = 0
            horizontal = glm.normalize(wish) * speed if glm.length(wish) > 0 else glm.vec3(0)
            vy = self.velocity.y - GRAVITY * min(dt, physics.MAX_DT)
            if vertical > 0 and self.on_ground:
                vy = JUMP_SPEED
            velocity = glm.vec3(horizontal.x, max(vy, -MAX_FALL_SPEED), horizontal.z)
            step_height = STEP_HEIGHT

        feet, vel, self.on_ground = physics.step(
            tuple(self.feet), tuple(velocity), dt, self.app.scene.world.block_height,
            PLAYER_WIDTH, PLAYER_HEIGHT, step_height, self.on_ground,
        )
        self.feet = glm.vec3(feet)
        self.velocity = glm.vec3(vel)
        self.sync_camera()

    def keyboard_event(self, event):
        # One pulse key handling
        if event.key == KEY_TOGGLE_FLY:
            self.fly = not self.fly
            self.velocity = glm.vec3(0)  # leaving fly mode: start falling from rest
