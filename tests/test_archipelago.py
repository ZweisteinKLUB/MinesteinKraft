import numpy as np
import pytest
import noise
from settings import *
from terrain_gen import get_height, generate_terrain


@pytest.fixture(autouse=True)
def restore_seed():
    yield
    noise.set_seed(SEED)


def chunk(cx, cy, cz):
    voxels = np.zeros(CHUNK_VOL, dtype=np.uint8)
    generate_terrain(voxels, cx * CHUNK_SIZE, cy * CHUNK_SIZE, cz * CHUNK_SIZE)
    return voxels


def test_seed_selects_the_world_deterministically():
    noise.set_seed(1)
    a = chunk(7, 0, -3)
    noise.set_seed(2)
    b = chunk(7, 0, -3)
    noise.set_seed(1)
    assert np.array_equal(a, chunk(7, 0, -3))
    assert not np.array_equal(a, b)


def test_base_area_unchanged_by_archipelago():
    for seed in (SEED, 1, 987654321):
        noise.set_seed(seed)
        x = np.arange(0, WORLD_W * CHUNK_SIZE)[None, :]
        z = np.arange(0, WORLD_D * CHUNK_SIZE)[:, None]
        assert np.array_equal(get_height(x, z), get_height(x, z, archipelago=False))


@pytest.mark.parametrize('seed', [1, 2, 16, 4242])
def test_archipelago_has_land_and_sea_far_away(seed):
    noise.set_seed(seed)
    xs = np.arange(-1500, 1500, 25)
    x, z = np.meshgrid(xs, xs)
    far = np.hypot(x - CENTER_XZ, z - CENTER_XZ) > 300
    land = get_height(x, z)[far] > WATER_LINE
    assert 0.08 < land.mean() < 0.6


def test_heights_continuous_across_chunk_borders():
    noise.set_seed(3)
    x = np.arange(20 * CHUNK_SIZE, 30 * CHUNK_SIZE)
    for z0 in range(-800, 800, 97):
        h = get_height(x, z0)
        jumps = np.abs(np.diff(h))
        border = jumps[CHUNK_SIZE - 1::CHUNK_SIZE]  # between x = 32k - 1 and 32k
        assert border.max() <= max(jumps.max(), 0)  # no step specific to borders


def test_chunks_generated_separately_match_at_borders():
    """Two neighbour chunks generated independently: border columns follow the height map."""
    noise.set_seed(5)
    a = chunk(30, 0, 4).reshape(CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)
    b = chunk(31, 0, 4).reshape(CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)
    z = 4 * CHUNK_SIZE + np.arange(CHUNK_SIZE)
    ha = get_height(31 * CHUNK_SIZE - 1, z)
    hb = get_height(31 * CHUNK_SIZE, z)
    for i in range(CHUNK_SIZE):
        for grid, h in ((a[:, i, -1], ha[i]), (b[:, i, 0], hb[i])):
            if 0 < h <= CHUNK_SIZE:
                assert grid[h - 1] != 0  # surface present exactly where the height map says
