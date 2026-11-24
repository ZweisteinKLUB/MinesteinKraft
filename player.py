import pygame as pg
from camera import Camera
from settings import *

# Movement keys: ZQSD (AZERTY), WASD (QWERTY) and arrows all work.
KEYS_FORWARD = (pg.K_z, pg.K_w, pg.K_UP)
KEYS_BACK = (pg.K_s, pg.K_DOWN)
KEYS_LEFT = (pg.K_q, pg.K_a, pg.K_LEFT)
KEYS_RIGHT = (pg.K_d, pg.K_RIGHT)
KEYS_UP = (pg.K_SPACE,)
KEYS_DOWN = (pg.K_LSHIFT,)
KEYS_SPRINT = (pg.K_LCTRL,)
KEY_TOGGLE_FLY = pg.K_f


class Player(Camera):
    def __init__(self, app, position=PLAYER_POS, yaw=-90, pitch=0, aspect_ratio=16 / 9):
        self.app = app
        super().__init__(position, yaw, pitch, aspect_ratio)

    def update(self):
        if self.app.mouse_captured:
            self.keyboard_control()
            self.mouse_control()
        super().update()

    def handle_event(self, event):
        if not self.app.mouse_captured:
            return
        # adding and removing voxels with clicks
        if event.type == pg.MOUSEBUTTONDOWN:
            voxel_handler = self.app.scene.world.voxel_handler
            if event.button == 1:
                voxel_handler.set_voxel()
            if event.button == 3:
                voxel_handler.switch_mode()
        if event.type == pg.KEYDOWN:
            self.keyboard_event(event)

    def mouse_control(self):
        mouse_dx, mouse_dy = pg.mouse.get_rel()
        if mouse_dx:
            self.rotate_yaw(delta_x=mouse_dx * MOUSE_SENSITIVITY)
        if mouse_dy:
            self.rotate_pitch(delta_y=mouse_dy * MOUSE_SENSITIVITY)

    def keyboard_control(self):
        key_state = pg.key.get_pressed()

        def pressed(keys):
            return any(key_state[k] for k in keys)

        vel = PLAYER_SPEED * self.app.delta_time
        if pressed(KEYS_SPRINT):
            vel *= PLAYER_SPRINT_FACTOR
        if pressed(KEYS_FORWARD):
            self.move_forward(vel)
        if pressed(KEYS_BACK):
            self.move_back(vel)
        if pressed(KEYS_RIGHT):
            self.move_right(vel)
        if pressed(KEYS_LEFT):
            self.move_left(vel)
        if pressed(KEYS_UP):
            self.move_up(vel)
        if pressed(KEYS_DOWN):
            self.move_down(vel)

    def keyboard_event(self, event):
        # One pulse key handling
        if event.key == KEY_TOGGLE_FLY:
            self.fly = not self.fly
