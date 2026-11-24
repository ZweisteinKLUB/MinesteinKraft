from settings import *
from world_objects.chunk import Chunk
from voxel_handler import VoxelHandler

WORLD_SIZE_X = WORLD_W * CHUNK_SIZE
WORLD_SIZE_Y = WORLD_H * CHUNK_SIZE
WORLD_SIZE_Z = WORLD_D * CHUNK_SIZE


def block_height_in(voxels, wx, wy, wz):
    """Collision height (0..1) of the block at integer world coordinates.

    Single entry point for collisions: outside the generated area there are
    invisible walls (x / z) and a solid floor below y = 0. To be adapted when
    chunks get generated on the fly.
    """
    if not (0 <= wx < WORLD_SIZE_X and 0 <= wz < WORLD_SIZE_Z):
        return 1.0  # invisible walls
    if wy < 0:
        return 1.0  # bedrock
    if wy >= WORLD_SIZE_Y:
        return 0.0  # open sky
    cx, cy, cz = wx // CHUNK_SIZE, wy // CHUNK_SIZE, wz // CHUNK_SIZE
    lx, ly, lz = wx - cx * CHUNK_SIZE, wy - cy * CHUNK_SIZE, wz - cz * CHUNK_SIZE
    voxel = voxels[cx + WORLD_W * cz + WORLD_AREA * cy, lx + CHUNK_SIZE * lz + CHUNK_AREA * ly]
    return 1.0 if voxel else 0.0  # every block is a full cube for now


def surface_height_in(voxels, wx, wz):
    """Y just above the highest non-empty block of the column (0 if none)."""
    for wy in range(WORLD_SIZE_Y - 1, -1, -1):
        if block_height_in(voxels, wx, wy, wz) > 0:
            return wy + 1
    return 0


class World:
    def __init__(self, app):
        self.app = app
        self.chunks = [None for _ in range(WORLD_VOL)]
        self.voxels = np.empty([WORLD_VOL, CHUNK_VOL], dtype='uint8')
        self.build_chunks()
        self.build_chunk_mesh()
        self.voxel_handler = VoxelHandler(self)

    def block_height(self, wx, wy, wz):
        return block_height_in(self.voxels, wx, wy, wz)

    def surface_height(self, wx, wz):
        return surface_height_in(self.voxels, wx, wz)

    def update(self):
        self.voxel_handler.update()

    def build_chunks(self):
        for x in range(WORLD_W):
            for y in range(WORLD_H):
                for z in range(WORLD_D):
                    chunk = Chunk(self, position=(x, y, z))

                    chunk_index = x + WORLD_W * z + WORLD_AREA * y
                    self.chunks[chunk_index] = chunk

                    # put the chunk voxels in a separate array
                    self.voxels[chunk_index] = chunk.build_voxels()

                    # get pointer to voxels
                    chunk.voxels = self.voxels[chunk_index]

    def build_chunk_mesh(self):
        for chunk in self.chunks:
            chunk.build_mesh()

    def render(self):
        for chunk in self.chunks:
            chunk.render()
