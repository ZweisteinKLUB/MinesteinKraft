import re
from settings import *
from paths import resource_path

# texture units shared by every program (see textures.py and render/)
UNIT_FRAME = 0
UNIT_BLOCKS = 1
UNIT_CRACKS = 3
UNIT_UI = 4
UNIT_SHADOW = (5, 6)
UNIT_SCENE_COLOR = 7
UNIT_SCENE_DEPTH = 8
UNIT_HEIGHTMAP = 9
UNIT_NOISE = 10
UNIT_POST = (11, 12, 13, 14)   # free for the post-processing passes

ENV_BINDING = 0  # uniform block binding of the shared sky / camera state

SAMPLER_UNITS = {
    'u_texture_0': UNIT_FRAME,
    'u_texture_array_0': UNIT_BLOCKS,
    'u_cracks': UNIT_CRACKS,
    'u_shadow0': UNIT_SHADOW[0],
    'u_shadow1': UNIT_SHADOW[1],
    'u_scene_color': UNIT_SCENE_COLOR,
    'u_scene_depth': UNIT_SCENE_DEPTH,
    'u_heightmap': UNIT_HEIGHTMAP,
    'u_noise': UNIT_NOISE,
}

INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"\s*$', re.MULTILINE)


class ShaderProgram:
    """Every program of the game, with the shared uniforms set once."""

    # scene programs drawn with the camera (m_proj / m_view)
    SCENE = ('chunk', 'voxel_marker', 'water', 'crack', 'mob', 'precipitation', 'lightning')

    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx
        self.player = app.player
        for name in self.SCENE:
            setattr(self, name, load_program(self.ctx, name))
        self.sky = load_program(self.ctx, 'sky', 'fullscreen')
        self.bloom_down = load_program(self.ctx, 'bloom_down', 'fullscreen')
        self.bloom_up = load_program(self.ctx, 'bloom_up', 'fullscreen')
        self.godrays = load_program(self.ctx, 'godrays', 'fullscreen')
        self.composite = load_program(self.ctx, 'composite', 'fullscreen')
        self.fxaa = load_program(self.ctx, 'fxaa', 'fullscreen')
        self.programs = tuple(getattr(self, name) for name in self.SCENE)
        self.set_uniforms_on_init()

    @staticmethod
    def set_uniform(program, name, value):
        """Set a uniform only if the driver kept it (unused uniforms may be optimized out)."""
        if name not in program:
            return
        if isinstance(value, (glm.vec2, glm.vec3, glm.vec4, glm.mat4)):
            program[name].write(value)
        else:
            program[name].value = value

    def set_projection(self, m_proj):
        for program in self.programs:
            self.set_uniform(program, 'm_proj', m_proj)

    def set_view(self, m_view):
        for program in self.programs:
            self.set_uniform(program, 'm_view', m_view)

    def set_uniforms_on_init(self):
        su = self.set_uniform
        self.set_projection(self.player.m_proj)
        su(self.chunk, 'm_model', glm.mat4())
        su(self.voxel_marker, 'm_model', glm.mat4())
        su(self.mob, 'u_tint', glm.vec3(0))
        for program in (self.chunk, self.mob):
            su(program, 'u_shadow_pass', 0)
        su(self.water, 'u_near', NEAR)
        su(self.water, 'u_far', FAR)

    def update(self):
        self.set_view(self.player.m_view)

    def get_program(self, shader_name):
        return load_program(self.ctx, shader_name)


def preprocess(source, seen=None):
    """Expand ``#include "file.glsl"`` lines with the files of shaders/include (once each)."""
    seen = set() if seen is None else seen

    def expand(match):
        name = match.group(1)
        if name in seen:
            return ''
        seen.add(name)
        text = resource_path('shaders', 'include', name).read_text(encoding='utf-8')
        return preprocess(text, seen)

    return INCLUDE.sub(expand, source)


def bind_shared(program):
    """Bind the shared uniform block and texture units of a program."""
    if 'Env' in program:
        program['Env'].binding = ENV_BINDING
    for name, unit in SAMPLER_UNITS.items():
        if name in program:
            program[name].value = unit


def load_program(ctx, shader_name, vertex_name=None):
    """Program from shaders/<vertex_name or shader_name>.vert and shaders/<shader_name>.frag."""
    vertex_shader = resource_path('shaders', f'{vertex_name or shader_name}.vert').read_text(encoding='utf-8')
    fragment_shader = resource_path('shaders', f'{shader_name}.frag').read_text(encoding='utf-8')
    program = ctx.program(vertex_shader=preprocess(vertex_shader), fragment_shader=preprocess(fragment_shader))
    bind_shared(program)
    return program
