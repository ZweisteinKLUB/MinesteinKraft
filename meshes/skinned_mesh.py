import numpy as np
from meshes.base_mesh import BaseMesh

MAX_BONES = 32  # keep in sync with shaders/mob.vert


class SkinnedMesh(BaseMesh):
    """GPU copy of a model's skinned triangles (shared by every mob using the model)."""

    def __init__(self, ctx, program, model):
        super().__init__()
        if len(model.joints) > MAX_BONES:
            raise ValueError(f'{len(model.joints)} joints, the mob shader supports {MAX_BONES}')
        self.ctx = ctx
        self.program = program
        self.model = model
        self.vbo_format = '3f 3f 4f 4f 4f'
        self.attrs = ('in_position', 'in_normal', 'in_color', 'in_joints', 'in_weights')
        self.vao = self.get_vao()

    def get_vertex_data(self):
        return vertex_data(self.model)


def vertex_data(model):
    m = model
    color = np.hstack([m.colors, m.emissive[:, None]])
    return np.ascontiguousarray(
        np.hstack([m.positions, m.normals, color, m.joint_ids, m.weights]).astype('f4'))


_IDENTITY_BONES = np.tile(np.eye(4, dtype='f4'), (MAX_BONES, 1, 1))


def bones_bytes(matrices):
    """(J, 4, 4) math-order joint matrices -> bytes for the u_bones[MAX_BONES] uniform."""
    bones = _IDENTITY_BONES.copy()
    bones[:len(matrices)] = matrices
    return np.ascontiguousarray(bones.transpose(0, 2, 1)).tobytes()  # GLSL is column-major
