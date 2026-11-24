import numpy as np
import pytest
from settings import *
from meshes.chunk_mesh_builder import build_chunk_mesh, get_chunk_index, pack_data


def empty_world():
    return np.zeros((WORLD_VOL, CHUNK_VOL), dtype=np.uint8)


def chunk_index(x, y, z):
    return x + WORLD_W * z + WORLD_AREA * y


def voxel_index(x, y, z):
    return x + CHUNK_SIZE * z + CHUNK_AREA * y


def mesh_of(world, pos):
    return build_chunk_mesh(world[chunk_index(*pos)], 1, pos, world)


def unpack(v):
    v = np.asarray(v, dtype=np.uint32)
    return dict(x=v >> 26, y=(v >> 20) & 63, z=(v >> 14) & 63, voxel_id=(v >> 6) & 255,
                face_id=(v >> 3) & 7, ao_id=(v >> 1) & 3, flip_id=v & 1)


def test_pack_roundtrip():
    d = unpack(pack_data(32, 17, 5, 200, 5, 3, 1))
    assert (d['x'], d['y'], d['z'], d['voxel_id'], d['face_id'], d['ao_id'], d['flip_id']) == (32, 17, 5, 200, 5, 3, 1)


def test_single_voxel_has_six_faces():
    world = empty_world()
    world[chunk_index(1, 0, 1)][voxel_index(5, 5, 5)] = STONE
    mesh = mesh_of(world, (1, 0, 1))
    assert mesh.dtype == np.uint32 and len(mesh) == 36
    d = unpack(mesh)
    assert sorted(set(d['face_id'].tolist())) == [0, 1, 2, 3, 4, 5]
    assert set(d['voxel_id'].tolist()) == {STONE}
    assert set(d['ao_id'].tolist()) == {3}  # nothing around: no occlusion


def test_adjacent_voxels_hide_shared_faces():
    world = empty_world()
    c = world[chunk_index(1, 0, 1)]
    c[voxel_index(5, 5, 5)] = STONE
    c[voxel_index(6, 5, 5)] = STONE
    assert len(mesh_of(world, (1, 0, 1))) == 60


def test_faces_hidden_across_chunk_border():
    world = empty_world()
    world[chunk_index(1, 0, 1)][voxel_index(CHUNK_SIZE - 1, 5, 5)] = STONE
    world[chunk_index(2, 0, 1)][voxel_index(0, 5, 5)] = STONE
    assert len(mesh_of(world, (1, 0, 1))) == 30
    assert len(mesh_of(world, (2, 0, 1))) == 30


@pytest.mark.parametrize('pos', [(0, 0, 0), (1, 0, 0), (0, 0, 1)])
def test_z0_and_x0_chunks_are_meshed(pos):
    # regression: `0 < cz` used to hide the whole z == 0 row of chunks
    world = empty_world()
    world[chunk_index(*pos)][voxel_index(5, 5, 5)] = STONE
    assert len(mesh_of(world, pos)) == 36


def test_no_faces_on_world_border():
    world = empty_world()
    world[chunk_index(0, 0, 0)][voxel_index(0, 5, 5)] = STONE
    mesh = mesh_of(world, (0, 0, 0))
    assert len(mesh) == 30
    assert 3 not in set(unpack(mesh)['face_id'].tolist())  # left face at x == -1 culled


def test_ambient_occlusion_on_top_face():
    world = empty_world()
    c = world[chunk_index(1, 0, 1)]
    c[voxel_index(5, 5, 5)] = STONE
    c[voxel_index(4, 6, 5)] = STONE  # block above-left of the top face
    d = unpack(mesh_of(world, (1, 0, 1)))
    top = (d['face_id'] == 0) & (d['y'] == 6) & (d['x'] >= 5)
    ao = {(int(x), int(z)): int(a) for x, z, a in zip(d['x'][top], d['z'][top], d['ao_id'][top])}
    # corners on the x == 5 edge touch the occluder
    assert ao[(5, 5)] < 3 and ao[(5, 6)] < 3
    assert ao[(6, 5)] == 3 and ao[(6, 6)] == 3


def test_empty_chunk_gives_empty_mesh():
    assert len(mesh_of(empty_world(), (0, 0, 0))) == 0


def test_get_chunk_index():
    assert get_chunk_index((0, 0, 0)) == 0
    assert get_chunk_index((CHUNK_SIZE, 0, CHUNK_SIZE)) == chunk_index(1, 0, 1)
    assert get_chunk_index((-1, 0, 0)) == -1
    assert get_chunk_index((0, 0, WORLD_D * CHUNK_SIZE)) == -1
