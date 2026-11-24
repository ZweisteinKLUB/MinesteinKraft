import numpy as np
from settings import *
from terrain_gen import generate_terrain, get_height


def gen(cx, cy, cz):
    voxels = np.zeros(CHUNK_VOL, dtype=np.uint8)
    generate_terrain(voxels, cx, cy, cz)
    return voxels


def test_terrain_is_deterministic():
    pos = (2 * CHUNK_SIZE, 0, 2 * CHUNK_SIZE)
    assert np.array_equal(gen(*pos), gen(*pos))


def test_terrain_follows_height_map():
    cx, cz = 2 * CHUNK_SIZE, 2 * CHUNK_SIZE
    grid = gen(cx, 0, cz).reshape(CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)  # (y, z, x)
    heights = get_height(cx + np.arange(CHUNK_SIZE)[None, :], cz + np.arange(CHUNK_SIZE)[:, None])
    for z in range(0, CHUNK_SIZE, 7):
        for x in range(0, CHUNK_SIZE, 7):
            h = heights[z, x]
            if 0 < h <= CHUNK_SIZE:
                # surface voxel present (trees may add blocks above, never remove the surface)
                assert grid[h - 1, z, x] != 0


def test_only_known_voxel_ids():
    ids = set(np.unique(gen(CHUNK_SIZE, 0, CHUNK_SIZE)).tolist())
    assert ids <= {0, SAND, GRASS, DIRT, STONE, SNOW, LEAVES, WOOD}
