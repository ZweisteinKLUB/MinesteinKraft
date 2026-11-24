import numpy as np
from settings import *
from world import block_height_in, surface_height_in, chunk_key, WORLD_SIZE_Y


def world_with(*blocks):
    """get_voxels function over a 2x2-column loaded area with the given blocks."""
    chunks = {(cx, cy, cz): np.zeros(CHUNK_VOL, dtype=np.uint8)
              for cx in range(2) for cy in range(WORLD_H) for cz in range(2)}
    for wx, wy, wz in blocks:
        lx, ly, lz = wx % CHUNK_SIZE, wy % CHUNK_SIZE, wz % CHUNK_SIZE
        chunks[chunk_key(wx, wy, wz)][lx + CHUNK_SIZE * lz + CHUNK_AREA * ly] = STONE
    return chunks.get


def test_blocks_inside_loaded_chunks():
    get = world_with((40, 33, 50))
    assert block_height_in(get, 40, 33, 50) == 1.0
    assert block_height_in(get, 40, 34, 50) == 0.0


def test_unloaded_chunks_are_walls_floor_and_sky():
    get = world_with()
    for pos in [(-1, 10, 5), (5, 10, -1), (2 * CHUNK_SIZE, 10, 5), (5, 10, 2 * CHUNK_SIZE)]:
        assert block_height_in(get, *pos) == 1.0          # not loaded yet: wall
    assert block_height_in(get, 5, 10, 5) == 0.0
    assert block_height_in(get, 5, -1, 5) == 1.0           # bedrock
    assert block_height_in(get, 5, WORLD_SIZE_Y, 5) == 0.0  # open sky


def test_surface_height():
    get = world_with((10, 3, 10), (10, 40, 10))
    assert surface_height_in(get, 10, 10) == 41
    assert surface_height_in(get, 11, 10) == 0
    assert surface_height_in(get, -5, 10) == 0  # not loaded
