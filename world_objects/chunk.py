from settings import *
from meshes.chunk_mesh import ChunkMesh
from terrain_gen import generate_terrain


def generate_chunk_voxels(key):
    """Voxels of a new chunk from the world generator (pure function of key + seed)."""
    voxels = np.zeros(CHUNK_VOL, dtype='uint8')
    cx, cy, cz = (int(c) * CHUNK_SIZE for c in key)
    generate_terrain(voxels, cx, cy, cz)
    return voxels


class Chunk:
    def __init__(self, world, position, voxels):
        self.app = world.app
        self.world = world
        self.position = tuple(position)
        self.voxels: np.ndarray = voxels
        self.mesh: ChunkMesh = None  # built when the neighbours are available
        self.is_empty = not np.any(voxels)
        self.m_model = self.get_model_matrix()

        self.center = (glm.vec3(self.position) + 0.5) * CHUNK_SIZE
        self.is_on_frustum = self.app.player.frustum.is_on_frustum

    def get_model_matrix(self):
        return glm.translate(glm.mat4(), glm.vec3(self.position) * CHUNK_SIZE)

    def set_uniform(self):
        self.mesh.program['m_model'].write(self.m_model)

    def build_mesh(self):
        if self.mesh is None:
            self.mesh = ChunkMesh(self)
        else:
            self.mesh.rebuild()

    def release(self):
        if self.mesh is not None:
            self.mesh.release()
            self.mesh = None

    def render(self):
        if self.mesh is not None and not self.is_empty and self.is_on_frustum(self):
            self.set_uniform()
            self.mesh.render()
