from settings import *
from meshes.cloud_mesh import CloudMesh, CLOUD_CELLS


class Clouds:
    """Cloud layer around the player, rebuilt when the player moves far from its center."""

    def __init__(self, app):
        self.app = app
        self.mesh = CloudMesh(app, self.origin_for_player())

    def origin_for_player(self):
        pos = self.app.player.position
        return (int(math.floor(pos.x / CLOUD_SCALE)) - CLOUD_CELLS // 2,
                int(math.floor(pos.z / CLOUD_SCALE)) - CLOUD_CELLS // 2)

    def update(self):
        ox, oz = self.mesh.origin
        nx, nz = self.origin_for_player()
        if max(abs(nx - ox), abs(nz - oz)) > CLOUD_CELLS // 4:
            self.mesh.release()
            self.mesh = CloudMesh(self.app, (nx, nz))
        program = self.mesh.program
        program['u_time'] = self.app.time
        if 'u_origin' in program:
            program['u_origin'] = tuple(float(v) for v in self.mesh.origin)

    def render(self):
        self.mesh.render()
