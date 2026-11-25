from settings import *
from frustum import Frustum


class Camera:
    def __init__(self, position, yaw, pitch, aspect_ratio=16 / 9):
        self.position = glm.vec3(position)
        self.yaw =glm.radians(yaw)
        self.pitch = glm.radians(pitch)
        
        self.up = glm.vec3(0, 1, 0)
        self.upward = glm.vec3(0, 1, 0)
        self.right = glm.vec3(1, 0, 0)
        self.forward = glm.vec3(0, 0, -1)
        self.look = glm.vec3(0, 0, -1)
        
        self.aspect_ratio = aspect_ratio
        self.m_proj = glm.perspective(V_FOV, aspect_ratio, NEAR, FAR)
        self.m_view = glm.mat4()

        # render camera: equals position / look in first person, moved away in third person
        self.view_position = glm.vec3(self.position)
        self.view_dir = glm.vec3(self.look)
        self.view_up = glm.vec3(self.up)
        
        self.frustum = Frustum(self)
        
        self.fly = False
    
    def set_aspect_ratio(self, aspect_ratio):
        self.aspect_ratio = aspect_ratio
        self.m_proj = glm.perspective(V_FOV, aspect_ratio, NEAR, FAR)
        self.frustum.set_aspect_ratio(aspect_ratio)

    def update(self):
        self.update_vectors()
        self.update_view()
        self.update_view_matrix()

    def update_view(self):
        """Place the render camera (first person: at the eyes, looking where the player aims)."""
        self.view_position = glm.vec3(self.position)
        self.view_dir = glm.vec3(self.look)
        self.view_up = glm.vec3(self.up)

    def update_view_matrix(self):
        self.m_view = glm.lookAt(self.view_position, self.view_position + self.view_dir, self.view_up)
        
    def update_vectors(self):
        #look vectors
        self.look.x = glm.cos(self.yaw) * glm.cos(self.pitch)
        self.look.y = glm.sin(self.pitch)
        self.look.z = glm.sin(self.yaw) * glm.cos(self.pitch)
        self.right = glm.normalize(glm.cross(self.look, glm.vec3(0, 1, 0)))
        self.up = glm.normalize(glm.cross(self.right, self.look))
        
        #move vectors
        if self.fly :
            self.forward = glm.normalize(self.look)
        else:
            self.forward.x = glm.cos(self.yaw)
            self.forward.y = 0.0
            self.forward.z = glm.sin(self.yaw)
    
    def rotate_pitch(self, delta_y):
        self.pitch -= delta_y
        self.pitch = glm.clamp(self.pitch, -PITCH_MAX, PITCH_MAX)
    
    def rotate_yaw(self, delta_x):
        self.yaw += delta_x
        
    def move_left(self, velocity):
        self.position -= self.right * velocity
        
    def move_right(self, velocity):
        self.position += self.right * velocity
    
    def move_up(self, velocity):
        self.position += self.upward * velocity
    
    def move_down(self, velocity):
        self.position -= self.upward * velocity
    
    def move_forward(self, velocity):
        self.position += self.forward * velocity
    
    def move_back(self, velocity):
        self.position -= self.forward * velocity