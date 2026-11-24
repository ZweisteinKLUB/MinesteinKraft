import numpy as np
from settings import *
from world import block_height_in, surface_height_in, WORLD_SIZE_X, WORLD_SIZE_Y, WORLD_SIZE_Z


def world_with(*blocks):
    voxels = np.zeros((WORLD_VOL, CHUNK_VOL), dtype=np.uint8)
    for wx, wy, wz in blocks:
        cx, cy, cz = wx // CHUNK_SIZE, wy // CHUNK_SIZE, wz // CHUNK_SIZE
        lx, ly, lz = wx % CHUNK_SIZE, wy % CHUNK_SIZE, wz % CHUNK_SIZE
        voxels[cx + WORLD_W * cz + WORLD_AREA * cy, lx + CHUNK_SIZE * lz + CHUNK_AREA * ly] = STONE
    return voxels


def test_blocks_inside_world():
    voxels = world_with((40, 33, 70))
    assert block_height_in(voxels, 40, 33, 70) == 1.0
    assert block_height_in(voxels, 40, 34, 70) == 0.0


def test_invisible_walls_and_floor():
    voxels = world_with()
    for pos in [(-1, 10, 5), (5, 10, -1), (WORLD_SIZE_X, 10, 5), (5, 10, WORLD_SIZE_Z), (-1, 500, 5)]:
        assert block_height_in(voxels, *pos) == 1.0
    assert block_height_in(voxels, 5, -1, 5) == 1.0       # solid floor
    assert block_height_in(voxels, 5, WORLD_SIZE_Y, 5) == 0.0  # open sky


def test_surface_height():
    voxels = world_with((10, 3, 10), (10, 40, 10))
    assert surface_height_in(voxels, 10, 10) == 41
    assert surface_height_in(voxels, 11, 10) == 0
