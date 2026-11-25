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


@pytest.mark.parametrize('name', ['chunk', 'voxel_marker', 'water', 'clouds', 'crack', 'ui', 'mob'])
def test_shader_compiles(ctx, name):
    program = load_program(ctx, name)
    if name != 'ui':
        assert 'm_proj' in program and 'm_view' in program


def test_textures_load(ctx):
    for name, is_array in (('frame.png', False), ('water.png', False), ('tex_array_0.png', True)):
        load_texture(ctx, name, is_array)


def test_skinned_mesh_renders(ctx):
    import numpy as np
    from meshes.skinned_mesh import SkinnedMesh, bones_bytes
    from models.gltf import parse_glb_bytes, model_from_gltf
    from tests.test_gltf import two_bone_glb
    model = model_from_gltf(*parse_glb_bytes(two_bone_glb()))
    program = load_program(ctx, 'mob')
    mesh = SkinnedMesh(ctx, program, model)
    program['u_bones'].write(bones_bytes(np.tile(np.eye(4, dtype='f4'), (2, 1, 1))))
    fbo = ctx.simple_framebuffer((8, 8))
    fbo.use()
    mesh.render()
    mesh.release()
