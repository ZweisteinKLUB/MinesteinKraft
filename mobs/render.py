from settings import *
from meshes.skinned_mesh import SkinnedMesh, bones_bytes


class MobRenderer:
    """Draws mobs with the skinned shader; one GPU mesh per model, shared by its mobs."""

    def __init__(self, app):
        self.app = app
        self.program = app.shader_program.mob
        self.meshes = {}

    def mesh_for(self, asset):
        mesh = self.meshes.get(asset.name)
        if mesh is None:
            mesh = self.meshes[asset.name] = SkinnedMesh(self.app.ctx, self.program, asset.model)
        return mesh

    def render(self, mob):
        if not mob.visible:
            return
        program = self.program
        program['m_model'].write(mob.model_matrix())
        program['u_bones'].write(bones_bytes(mob.skin_matrices()))
        if 'u_tint' in program:
            program['u_tint'].write(mob.tint)
        self.mesh_for(mob.asset).render()

    def release(self):
        for mesh in self.meshes.values():
            mesh.release()
        self.meshes.clear()
