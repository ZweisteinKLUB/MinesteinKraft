from settings import *
from world_objects.chunk import Chunk
from voxel_handler import VoxelHandler

WORLD_SIZE_Y = WORLD_H * CHUNK_SIZE      # fixed world height (blocks)
BASE_SIZE_X = WORLD_W * CHUNK_SIZE       # size of the initial area (blocks)
BASE_SIZE_Z = WORLD_D * CHUNK_SIZE


def chunk_key(wx, wy, wz):
    """Key of the chunk containing integer world coordinates (floor division)."""
    return wx // CHUNK_SIZE, wy // CHUNK_SIZE, wz // CHUNK_SIZE


def block_height_in(get_voxels, wx, wy, wz):
    """Collision height (0..1) of the block at integer world coordinates.

    ``get_voxels(key)`` returns a chunk voxel array or None when the chunk is not
    loaded: it is then solid (a wall until it is generated). Below y = 0 is solid
    bedrock, above the world height is open sky.
    """
    if wy < 0:
        return 1.0
    if wy >= WORLD_SIZE_Y:
        return 0.0
    cx, cy, cz = chunk_key(wx, wy, wz)
    voxels = get_voxels((cx, cy, cz))
    if voxels is None:
        return 1.0
    lx, ly, lz = wx - cx * CHUNK_SIZE, wy - cy * CHUNK_SIZE, wz - cz * CHUNK_SIZE
    return 1.0 if voxels[lx + CHUNK_SIZE * lz + CHUNK_AREA * ly] else 0.0  # full cubes for now


def surface_height_in(get_voxels, wx, wz):
    """Y just above the highest non-empty block of a loaded column (0 if none)."""
    for cy in range(WORLD_H - 1, -1, -1):
        voxels = get_voxels((wx // CHUNK_SIZE, cy, wz // CHUNK_SIZE))
        if voxels is None:
            continue
        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE
        column = voxels.reshape(CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)[:, lz, lx]
        filled = np.nonzero(column)[0]
        if filled.size:
            return cy * CHUNK_SIZE + int(filled[-1]) + 1
    return 0


class World:
    def __init__(self, app):
        self.app = app
        self.chunks: dict[tuple, Chunk] = {}
        self.build_chunks()
        self.build_chunk_mesh()
        self.voxel_handler = VoxelHandler(self)

    # ------------------------------------------------------------------ queries
    def get_chunk(self, key):
        return self.chunks.get(key)

    def get_voxels(self, key):
        chunk = self.chunks.get(key)
        return None if chunk is None else chunk.voxels

    def block_height(self, wx, wy, wz):
        return block_height_in(self.get_voxels, wx, wy, wz)

    def surface_height(self, wx, wz):
        return surface_height_in(self.get_voxels, wx, wz)

    # ------------------------------------------------------------------ chunks
    def build_chunks(self):
        for x in range(WORLD_W):
            for y in range(WORLD_H):
                for z in range(WORLD_D):
                    chunk = Chunk(self, position=(x, y, z))
                    chunk.voxels = chunk.build_voxels()
                    self.chunks[chunk.position] = chunk

    def build_chunk_mesh(self):
        for chunk in self.chunks.values():
            chunk.build_mesh()

    def update(self):
        self.voxel_handler.update()

    def render(self):
        for chunk in self.chunks.values():
            chunk.render()
