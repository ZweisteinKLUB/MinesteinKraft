from types import SimpleNamespace
import numpy as np
from settings import *  # provides glm
from voxel_handler import VoxelHandler


def make_handler():
    chunks = [SimpleNamespace(voxels=np.zeros(CHUNK_VOL, dtype=np.uint8)) for _ in range(WORLD_VOL)]
    world = SimpleNamespace(app=None, chunks=chunks)
    return VoxelHandler(world), chunks


def test_get_voxel_id_inside_world():
    handler, chunks = make_handler()
    idx = 2 + WORLD_W * 3 + WORLD_AREA * 1
    chunks[idx].voxels[5 + CHUNK_SIZE * 6 + CHUNK_AREA * 7] = STONE
    voxel_id, voxel_index, local, chunk = handler.get_voxel_id(glm.ivec3(2 * CHUNK_SIZE + 5, CHUNK_SIZE + 7, 3 * CHUNK_SIZE + 6))
    assert voxel_id == STONE and chunk is chunks[idx]
    assert tuple(local) == (5, 7, 6)


def test_get_voxel_id_negative_and_outside():
    handler, _ = make_handler()
    # -1 // 32 == -1 (outside); truncation would wrongly give chunk 0
    for pos in [(-1, 5, 5), (5, -1, 5), (5, 5, -1), (WORLD_W * CHUNK_SIZE, 0, 0)]:
        assert handler.get_voxel_id(glm.ivec3(*pos))[3] is None
