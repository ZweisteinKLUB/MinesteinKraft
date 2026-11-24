from settings import *
from paths import resource_path


class ShaderProgram:
    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx
        self.player = app.player
        #--------- shaders -------- #
        self.chunk = self.get_program(shader_name='chunk')
        self.voxel_marker = self.get_program(shader_name='voxel_marker')
        self.water = self.get_program('water')
        self.clouds = self.get_program('clouds')
        #-------------------------- #
        self.set_uniforms_on_init()

    @staticmethod
    def set_uniform(program, name, value):
        """Set a uniform only if the driver kept it (unused uniforms may be optimized out)."""
        if name not in program:
            return
        if isinstance(value, (glm.vec3, glm.mat4)):
            program[name].write(value)
        else:
            program[name].value = value

    def set_projection(self, m_proj):
        for program in (self.chunk, self.voxel_marker, self.water, self.clouds):
            self.set_uniform(program, 'm_proj', m_proj)

    def set_uniforms_on_init(self):
        su = self.set_uniform
        self.set_projection(self.player.m_proj)

        # chunk
        su(self.chunk, 'm_model', glm.mat4())
        su(self.chunk, 'u_texture_array_0', 1)
        su(self.chunk, 'bg_color', BG_COLOR)
        su(self.chunk, 'water_line', WATER_LINE)

        # marker
        su(self.voxel_marker, 'm_model', glm.mat4())
        su(self.voxel_marker, 'u_texture_0', 0)

        # water
        su(self.water, 'u_texture_0', 2)
        su(self.water, 'water_area', WATER_AREA)
        su(self.water, 'water_line', WATER_LINE)

        # clouds
        su(self.clouds, 'center', CENTER_XZ)
        su(self.clouds, 'bg_color', BG_COLOR)
        su(self.clouds, 'cloud_scale', CLOUD_SCALE)

    def update(self):
        for program in (self.chunk, self.voxel_marker, self.water, self.clouds):
            self.set_uniform(program, 'm_view', self.player.m_view)

    def get_program(self, shader_name):
        return load_program(self.ctx, shader_name)


def load_program(ctx, shader_name):
    vertex_shader = resource_path('shaders', f'{shader_name}.vert').read_text(encoding='utf-8')
    fragment_shader = resource_path('shaders', f'{shader_name}.frag').read_text(encoding='utf-8')
    return ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)
