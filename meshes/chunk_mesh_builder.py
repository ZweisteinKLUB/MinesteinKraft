"""Chunk mesh construction, vectorized with NumPy.

Each visible face produces 6 vertices (2 triangles), each vertex packed in one
uint32: x: 6bit  y: 6bit  z: 6bit  voxel_id: 8bit  face_id: 3bit  ao_id: 2bit  flip_id: 1bit.
The order of the 6 vertices inside a face matters: chunk.vert derives the UVs
from gl_VertexID % 6.
"""
from settings import *

# Voxel grids are C-ordered (y, z, x): index = x + CHUNK_SIZE * z + CHUNK_AREA * y.
# Offsets below are written (dx, dy, dz).

# AO neighbour offsets (a..h) in the plane of a face, relative to the neighbour voxel
_AO_PLANES = {
    'Y': [(0, 0, -1), (-1, 0, -1), (-1, 0, 0), (-1, 0, 1), (0, 0, 1), (1, 0, 1), (1, 0, 0), (1, 0, -1)],
    'X': [(0, 0, -1), (0, -1, -1), (0, -1, 0), (0, -1, 1), (0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 1, -1)],
    'Z': [(-1, 0, 0), (-1, -1, 0), (0, -1, 0), (1, -1, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (-1, 1, 0)],
}

# face_id, neighbour offset, AO plane, corners v0..v3, vertex order (no flip), vertex order (flip)
_FACES = [
    (0, (0, 1, 0), 'Y', [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)], (0, 3, 2, 0, 2, 1), (1, 0, 3, 1, 3, 2)),  # top
    (1, (0, -1, 0), 'Y', [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], (0, 2, 3, 0, 1, 2), (1, 3, 0, 1, 2, 3)),  # bottom
    (2, (1, 0, 0), 'X', [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)], (0, 1, 2, 0, 2, 3), (3, 0, 1, 3, 1, 2)),  # right
    (3, (-1, 0, 0), 'X', [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], (0, 2, 1, 0, 3, 2), (3, 1, 0, 3, 2, 1)),  # left
    (4, (0, 0, -1), 'Z', [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)], (0, 1, 2, 0, 2, 3), (3, 0, 1, 3, 1, 2)),  # back
    (5, (0, 0, 1), 'Z', [(0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)], (0, 2, 1, 0, 3, 2), (3, 1, 0, 3, 2, 1)),  # front
]


def pack_data(x, y, z, voxel_id, face_id, ao_id, flip_id):
    """Pack vertex attributes (scalars or arrays) into uint32."""
    u = np.uint32
    return (
        (np.asarray(x, dtype=u) << u(26)) |
        (np.asarray(y, dtype=u) << u(20)) |
        (np.asarray(z, dtype=u) << u(14)) |
        (np.asarray(voxel_id, dtype=u) << u(6)) |
        (np.asarray(face_id, dtype=u) << u(3)) |
        (np.asarray(ao_id, dtype=u) << u(1)) |
        np.asarray(flip_id, dtype=u)
    )


def get_chunk_index(world_voxel_pos):
    """Index of the chunk containing a world voxel position, or -1 outside the world."""
    wx, wy, wz = (int(v) for v in world_voxel_pos)
    cx, cy, cz = wx // CHUNK_SIZE, wy // CHUNK_SIZE, wz // CHUNK_SIZE
    if not (0 <= cx < WORLD_W and 0 <= cy < WORLD_H and 0 <= cz < WORLD_D):
        return -1
    return cx + WORLD_W * cz + WORLD_AREA * cy


def get_padded_voxels(chunk_voxels, chunk_pos, world_voxels):
    """(y, z, x) grid of the chunk with a 1-voxel border taken from neighbour chunks.

    Outside the world the border is solid, so no face is generated at the world edges.
    """
    s = CHUNK_SIZE
    padded = np.ones((s + 2, s + 2, s + 2), dtype=np.uint8)
    cx, cy, cz = (int(c) for c in chunk_pos)

    # per axis offset -> (source slice in neighbour, destination slice in padded)
    spans = {-1: (slice(s - 1, s), slice(0, 1)), 0: (slice(0, s), slice(1, s + 1)), 1: (slice(0, 1), slice(s + 1, s + 2))}

    for oy in (-1, 0, 1):
        ny = cy + oy
        if not 0 <= ny < WORLD_H:
            continue
        for oz in (-1, 0, 1):
            nz = cz + oz
            if not 0 <= nz < WORLD_D:
                continue
            for ox in (-1, 0, 1):
                nx = cx + ox
                if not 0 <= nx < WORLD_W:
                    continue
                if ox == oy == oz == 0:
                    source = chunk_voxels
                else:
                    source = world_voxels[nx + WORLD_W * nz + WORLD_AREA * ny]
                source = source.reshape(s, s, s)
                (sy, dy), (sz, dz), (sx, dx) = spans[oy], spans[oz], spans[ox]
                padded[dy, dz, dx] = source[sy, sz, sx]
    return padded


def build_chunk_mesh(chunk_voxels, format_size, chunk_pos, world_voxels):
    s = CHUNK_SIZE
    padded = get_padded_voxels(chunk_voxels, chunk_pos, world_voxels)
    void = padded == 0

    def shifted(grid, dx, dy, dz):
        """View of ``grid`` aligned on the chunk voxels, shifted by (dx, dy, dz)."""
        return grid[1 + dy:1 + dy + s, 1 + dz:1 + dz + s, 1 + dx:1 + dx + s]

    solid = shifted(padded, 0, 0, 0)
    parts = []

    for face_id, (nx, ny, nz), plane, corners, order, order_flip in _FACES:
        visible = (solid != 0) & shifted(void, nx, ny, nz)
        ys, zs, xs = np.nonzero(visible)
        if ys.size == 0:
            continue

        # ambient occlusion: count void cells around the neighbour voxel in the face plane
        a, b, c, d, e, f, g, h = (
            shifted(void, nx + ox, ny + oy, nz + oz)[ys, zs, xs].astype(np.uint8)
            for ox, oy, oz in _AO_PLANES[plane]
        )
        ao = (a + b + c, g + h + a, e + f + g, c + d + e)
        flip = (ao[1] + ao[3]) > (ao[0] + ao[2])

        voxel_id = solid[ys, zs, xs]
        verts = np.stack([
            pack_data(xs + vx, ys + vy, zs + vz, voxel_id, face_id, ao[k], flip)
            for k, (vx, vy, vz) in enumerate(corners)
        ], axis=1)  # (n_faces, 4)

        tris = np.where(flip[:, None], verts[:, list(order_flip)], verts[:, list(order)])
        parts.append(tris.ravel())

    if not parts:
        return np.empty(0, dtype=np.uint32)
    return np.concatenate(parts).astype(np.uint32, copy=False)
