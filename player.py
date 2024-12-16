import pygame as pg
from camera import Camera
from settings import *


class Player(Camera):
    def __init__(self, app, position=PLAYER_POS, yaw=-90, pitch=0):
        self.app = app
        super().__init__(position, yaw, pitch)
        self.fall = False
        
    def update(self):
        self.keyboard_control()
        self.mouse_control()
        super().update()
    
    def handle_event(self, event):
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
    
    def is_on_ground (self):
        # start point
        x1, y1, z1 = self.app.player.position
        current_voxel_pos = glm.ivec3(x1, y1, z1)   
        result = self.app.scene.world.voxel_handler.get_voxel_id(voxel_world_pos=current_voxel_pos)
        return False
        
    def keyboard_control(self):
        key_state = pg.key.get_pressed()
        vel = PLAYER_SPEED * self.app.delta_time
        if key_state[pg.K_RSHIFT]:
            vel *=10
        if key_state[pg.K_UP]:
            self.move_forward(vel)
        if key_state[pg.K_DOWN]:
            self.move_back(vel)
        if key_state [pg.K_RIGHT]:
            self.move_right(vel)
        if key_state [pg.K_LEFT]:
            self.move_left(vel)
        if key_state [pg.K_KP_0]:
            self.move_up(vel)
        if key_state [pg.K_RCTRL]:
            self.move_down(vel)
    
    def keyboard_event(self, event):
        # One pulse key handling
        key_event = event.key
        if key_event == pg.K_SPACE:
            self.fly = not self.fly