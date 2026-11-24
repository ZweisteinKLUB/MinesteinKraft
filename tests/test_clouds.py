import numpy as np
from settings import CLOUD_HEIGHT
from meshes.cloud_mesh import build_cloud_mesh, gen_clouds


def test_runs_are_merged():
    data = np.zeros((3, 8), dtype=bool)
    data[0, 1:4] = True      # one run of 3
    data[2, [0, 7]] = True   # two runs of 1
    mesh = build_cloud_mesh(data).reshape(-1, 6, 3)
    assert mesh.dtype == np.uint16 and len(mesh) == 3
    first = mesh[0]
    assert tuple(first[0]) == (1, CLOUD_HEIGHT, 0)   # v0
    assert tuple(first[1]) == (4, CLOUD_HEIGHT, 1)   # v1


def test_real_clouds_cover_the_cells():
    data = gen_clouds()
    mesh = build_cloud_mesh(data).reshape(-1, 6, 3).astype(int)
    area = ((mesh[:, 1, 0] - mesh[:, 0, 0]) * (mesh[:, 1, 2] - mesh[:, 0, 2])).sum()
    assert area == data.sum()
