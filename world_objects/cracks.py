from settings import *
from meshes.cube_mesh import CubeMesh


class Cracks:
    """Crack overlay drawn on the block being broken."""

    def __init__(self, voxel_handler):
        self.app = voxel_handler.app
        self.handler = voxel_handler
        self.mesh = CubeMesh(self.app, program=self.app.shader_program.crack)

    def render(self):
        breaker = self.handler.breaker
        if breaker.stage < 0:
            return
        program = self.mesh.program
        program['stage'] = float(breaker.stage)
        program['m_model'].write(glm.translate(glm.mat4(), glm.vec3(breaker.target)))
        self.mesh.render()
