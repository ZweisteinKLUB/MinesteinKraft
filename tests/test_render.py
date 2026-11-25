import numpy as np
import pytest
from settings import glm, CHUNK_SIZE, CHUNK_VOL, WORLD_H
from world import column_heights_of
from shader_program import preprocess
from render.effects import water_grid, bolt_segments, ribbon_vertices
from render.shadows import cascade_matrices
from render.textures import make_noise_data, tileable_noise
from render.env_buffer import ENV_SIZE, MATRICES, VECTORS


def test_column_heights():
    low, high = np.zeros(CHUNK_VOL, dtype='u1'), np.zeros(CHUNK_VOL, dtype='u1')
    grid_low = low.reshape(CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)    # [y, z, x]
    grid_high = high.reshape(CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)
    grid_low[:10, 3, 5] = 4          # column (x=5, z=3): ground up to y=9
    grid_low[20, 3, 5] = 6           # a leaf above an air gap
    grid_high[4, 7, 1] = 7           # column (x=1, z=7): block at y = 32 + 4
    heights = column_heights_of([low, high] + [None] * (WORLD_H - 2))
    assert heights.dtype == np.uint8 and heights.shape == (CHUNK_SIZE, CHUNK_SIZE)
    assert heights[3, 5] == 21       # top of the highest block, even above a gap
    assert heights[7, 1] == CHUNK_SIZE + 5
    assert heights[0, 0] == 0


def test_water_grid():
    n = 8
    vertices, indices = water_grid(n)
    assert vertices.shape == ((n + 1) ** 2, 2)
    assert indices.size == n * n * 6 and indices.max() == (n + 1) ** 2 - 1
    assert vertices.min() == -1.0 and vertices.max() == 1.0
    # every triangle has a positive area (none degenerate)
    tri = vertices[indices.reshape(-1, 3)]
    a, b = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    area = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    assert np.all(np.abs(area) > 0)


def test_lightning_bolt_goes_from_the_clouds_to_the_ground():
    ground = glm.vec3(100, 6, -40)
    bolts = bolt_segments(42, ground, 230.0)
    main, width, intensity = bolts[0]
    assert main[0].y == pytest.approx(230.0)
    assert glm.distance(main[-1], ground) < 1e-4
    assert len(main) == 2 ** 7 + 1 and len(bolts) >= 3
    again = bolt_segments(42, ground, 230.0)
    assert all(glm.distance(a, b) < 1e-6 for a, b in zip(main, again[0][0]))
    vertices = ribbon_vertices(bolts)
    assert vertices.shape[1] == 9 and len(vertices) % 6 == 0


def test_shadow_cascade_is_centered_and_snapped():
    light = glm.normalize(glm.vec3(0.3, 0.8, 0.5))
    size, radius = 1024, 32.0
    texel = 2 * radius / size
    center = glm.vec3(100.3, 20.0, -55.7)
    view, proj = cascade_matrices(light, center, radius, size)
    clip = proj * view * glm.vec4(center, 1.0)
    assert abs(clip.x) * radius <= texel and abs(clip.y) * radius <= texel  # within a texel of the middle
    # a fixed point of the world stays on the same texel grid when the camera moves: no shimmering
    point = glm.vec4(90.0, 12.0, -50.0, 1.0)

    def texel_coords(c):
        v, pr = cascade_matrices(light, c, radius, size)
        clip = pr * v * point
        return glm.vec2(clip.x, clip.y) * (size / 2)

    base = texel_coords(center)
    for offset in (glm.vec3(0.013, 0, 0), glm.vec3(0.3, 0.1, -0.7), glm.vec3(5.0, 0, 3.0)):
        shift = texel_coords(center + offset) - base
        assert abs(shift.x - round(shift.x)) < 1e-2 and abs(shift.y - round(shift.y)) < 1e-2


def test_preprocess_expands_includes_once():
    source = '#version 330 core\n#include "env.glsl"\n#include "sky.glsl"\n#include "env.glsl"\nvoid main() {}\n'
    out = preprocess(source)
    assert '#include' not in out
    assert out.count('uniform Env') == 1
    assert 'vec3 sky_radiance' in out


def test_env_block_size():
    assert ENV_SIZE == (16 * len(MATRICES) + 4 * len(VECTORS)) * 4 == 640


def test_noise_is_uniform_and_tileable():
    rng = np.random.default_rng(0)
    n = tileable_noise(64, 6.0, rng)
    assert n.min() == 0.0 and n.max() == 1.0
    assert abs(np.median(n) - 0.5) < 0.01
    inner = np.abs(np.diff(n, axis=1)).mean()
    seam = np.abs(n[:, 0] - n[:, -1]).mean()  # wraps around like any neighbour
    assert seam < 2.5 * inner
    data = make_noise_data(size=32)
    assert data.shape == (32, 32, 4) and data.dtype == np.uint8
