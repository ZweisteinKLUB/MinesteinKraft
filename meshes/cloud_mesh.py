from settings import *
from meshes.base_mesh import BaseMesh
from noise import noise2


CLOUD_CELLS = WORLD_W * CHUNK_SIZE  # cloud grid size (cells of CLOUD_SCALE blocks)


class CloudMesh(BaseMesh):
    def __init__(self, app, origin=(0, 0)):
        super().__init__()
        self.app = app
        self.origin = origin

        self.ctx = self.app.ctx
        self.program = self.app.shader_program.clouds
        self.vbo_format = '3u2'
        self.attrs = ('in_position',)
        self.vao = self.get_vao()

    def get_vertex_data(self):
        return build_cloud_mesh(gen_clouds(*self.origin))


def gen_clouds(origin_x=0, origin_z=0, cells=CLOUD_CELLS):
    """Cloud coverage, shape (cells, cells) indexed [z, x], for absolute cells from the origin.

    Sampling the noise at absolute cell coordinates keeps the clouds in place when the
    mesh is rebuilt around a new origin.
    """
    x = (origin_x + np.arange(cells))[None, :]
    z = (origin_z + np.arange(cells))[:, None]
    return noise2(0.13 * x, 0.13 * z) >= 0.2


def build_cloud_mesh(cloud_data):
    """One quad per horizontal run of cloud cells, rows merged along x."""
    depth, width = cloud_data.shape
    # run boundaries: +1 where a run starts, -1 where it ends (one past its last cell)
    padded = np.zeros((depth, width + 2), dtype=np.int8)
    padded[:, 1:-1] = cloud_data
    edges = np.diff(padded, axis=1)
    z_start, x_start = np.nonzero(edges == 1)
    _, x_end = np.nonzero(edges == -1)  # same row order as starts

    y = np.full_like(x_start, CLOUD_HEIGHT)
    v0 = np.stack([x_start, y, z_start], axis=1)
    v1 = np.stack([x_end, y, z_start + 1], axis=1)
    v2 = np.stack([x_end, y, z_start], axis=1)
    v3 = np.stack([x_start, y, z_start + 1], axis=1)

    mesh = np.stack([v0, v1, v2, v0, v3, v1], axis=1)  # (n_quads, 6, 3)
    return mesh.astype('uint16').ravel()
