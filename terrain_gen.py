"""Terrain generation, vectorized per chunk with NumPy.

Voxel arrays are flat, indexed as ``x + CHUNK_SIZE * z + CHUNK_AREA * y``,
which is a C-ordered array of shape (y, z, x).
"""
from noise import noise2, noise3, get_seed
from settings import *


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def base_relief(x, z):
    """Hills and mountains (float array), before any land / sea mask."""
    # amplitude
    a1 = float(CENTER_Y)
    a2, a4, a8 = a1 * 0.5, a1 * 0.25, a1 * 0.125
    a1 = np.where(noise2(0.1 * x, 0.1 * z) < 0, a1 / 1.07, a1)

    # frequency
    f1 = 0.005
    f2, f4, f8 = f1 * 2, f1 * 4, f1 * 8

    height = noise2(x * f1, z * f1) * a1 + a1
    height = height + noise2(x * f2, z * f2) * a2 - a2
    height = height + noise2(x * f4, z * f4) * a4 + a4
    height = height + noise2(x * f8, z * f8) * a8 + a8
    return np.maximum(height, 1)


def get_height(x, z, archipelago=True):
    """Terrain height (int array) for world columns x, z (arrays or scalars).

    A pure function of the coordinates and the world seed, so chunks generated
    at different times always match at their borders.
    """
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    relief = base_relief(x, z)

    # starting island, scaled to the base area: ~1 inside ISLAND_RADIUS, then sea
    dist = np.hypot(x - CENTER_XZ, z - CENTER_XZ)
    island = np.minimum(1 / ((dist / ISLAND_RADIUS) ** ISLAND_FALLOFF + 0.0001), 1)
    height = relief * island

    if archipelago:
        # beyond the starting island: more islands and land masses, varied sea floor.
        # Faded out near the start so the base area and its sea belt never change.
        clear = smoothstep(*START_CLEAR_RADIUS, dist)
        s = ARCHIPELAGO_SCALE
        continent = noise2(x / s, z / s) * 0.75 + noise2(x / (s * 0.35) + 100, z / (s * 0.35) - 100) * 0.25
        land = smoothstep(ARCHIPELAGO_THRESHOLD, ARCHIPELAGO_THRESHOLD + 0.2, continent) * clear
        sea_floor = 1 + 3 * (noise2(x / 90 + 300, z / 90 - 300) * 0.5 + 0.5) * clear
        height = np.maximum(np.maximum(height, relief * land), sea_floor)

    return np.maximum(height, 1).astype(np.int64)  # the sea floor is never empty


def get_index(x, y, z):
    return x + CHUNK_SIZE * z + CHUNK_AREA * y


def chunk_rng(cx, cy, cz):
    """Deterministic random generator for a chunk (world voxel origin cx, cy, cz) and the world seed."""
    seed = get_seed()
    return np.random.default_rng([seed & 0xFFFFFFFF, (seed >> 32) & 0xFFFFFFFF,
                                  cx & 0xFFFFFFFF, cy & 0xFFFFFFFF, cz & 0xFFFFFFFF])


def generate_terrain(voxels, cx, cy, cz):
    """Fill the flat ``voxels`` array of the chunk whose world origin is (cx, cy, cz)."""
    rng = chunk_rng(cx, cy, cz)
    r = np.arange(CHUNK_SIZE)

    # world coordinates, broadcastable to (y, z, x)
    wx = (cx + r)[None, None, :]
    wz = (cz + r)[None, :, None]
    wy = (cy + r)[:, None, None]

    height = get_height(wx[0], wz[0])[None]  # (1, z, x)

    grid = np.zeros((CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE), dtype=np.uint8)

    # underground: stone, minus caves
    below_top = wy < height - 1
    cave_floor = noise2(wx[0] * 0.1, wz[0] * 0.1)[None] * 3 + 3
    cave_zone = below_top & (cave_floor < wy) & (wy < height - 10)
    cave = np.zeros_like(cave_zone)
    if cave_zone.any():
        ys, zs, xs = np.nonzero(cave_zone)
        cave[ys, zs, xs] = noise3((cx + xs) * 0.09, (cy + ys) * 0.09, (cz + zs) * 0.09) > 0
    grid[below_top & ~cave] = STONE

    # surface layer: material depends on a jittered altitude
    top = wy == height - 1
    ys, zs, xs = np.nonzero(top)
    ry = (cy + ys) - rng.integers(0, 7, size=ys.size)
    surface = np.select(
        [ry >= SNOW_LVL, ry >= STONE_LVL, ry >= DIRT_LVL, ry >= GRASS_LVL],
        [SNOW, STONE, DIRT, GRASS],
        default=SAND,
    ).astype(np.uint8)
    grid[ys, zs, xs] = surface

    # trees on low grass
    is_candidate = (surface == GRASS) & ((cy + ys) < DIRT_LVL)
    is_candidate &= rng.random(ys.size) <= TREE_PROBABILITY
    for x, y, z in zip(xs[is_candidate], ys[is_candidate], zs[is_candidate]):
        place_tree(grid, int(x), int(y), int(z), rng)

    voxels[:] = grid.ravel()


def place_tree(grid, x, y, z, rng):
    """Place a tree whose trunk base is at local (x, y, z); grid is indexed (y, z, x)."""
    if y + TREE_HEIGHT >= CHUNK_SIZE:
        return
    if x - TREE_H_WIDTH < 0 or x + TREE_H_WIDTH >= CHUNK_SIZE:
        return
    if z - TREE_H_WIDTH < 0 or z + TREE_H_WIDTH >= CHUNK_SIZE:
        return

    # dirt under the tree
    grid[y, z, x] = DIRT

    # leaves (only in empty space, so they never carve the terrain)
    m = 0
    for n, iy in enumerate(range(TREE_H_HEIGHT, TREE_HEIGHT - 1)):
        k = iy % 2
        jitter = int(rng.integers(0, 2))
        for ix in range(-TREE_H_WIDTH + m, TREE_H_WIDTH - m * jitter):
            for iz in range(-TREE_H_WIDTH + m * jitter, TREE_H_WIDTH - m):
                if (ix + iz) % 4:
                    ly, lz, lx = y + iy, z + iz + k, x + ix + k
                    if grid[ly, lz, lx] == 0:
                        grid[ly, lz, lx] = LEAVES
        m += 1 if n > 0 else 0

    # tree trunk
    grid[y + 1:y + TREE_HEIGHT - 2, z, x] = WOOD

    # top
    grid[y + TREE_HEIGHT - 2, z, x] = LEAVES
