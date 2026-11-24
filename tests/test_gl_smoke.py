"""Compile every shader and upload textures on a real OpenGL 3.3 context.

Skipped when no OpenGL 3.3 context can be created (e.g. CI without GPU).
"""
import pytest
import moderngl

from shader_program import load_program
from textures import load_texture


@pytest.fixture(scope='module')
def ctx():
    errors = []
    for kwargs in ({}, {'backend': 'egl'}):
        try:
            ctx = moderngl.create_standalone_context(require=330, **kwargs)
        except Exception as error:  # no display / no GPU / old GL
            errors.append(error)
            continue
        yield ctx
        ctx.release()
        return
    pytest.skip(f'no OpenGL 3.3 context available: {errors}')


@pytest.mark.parametrize('name', ['chunk', 'voxel_marker', 'water', 'clouds'])
def test_shader_compiles(ctx, name):
    program = load_program(ctx, name)
    assert 'm_proj' in program and 'm_view' in program


def test_textures_load(ctx):
    for name, is_array in (('frame.png', False), ('water.png', False), ('tex_array_0.png', True)):
        load_texture(ctx, name, is_array)
