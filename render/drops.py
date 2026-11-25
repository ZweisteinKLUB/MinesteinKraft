"""Draws the drops (world_objects/drops.py): small spinning, bobbing textured cubes, instanced."""
import math
import numpy as np
from world_objects.drops import DROP_SIZE, MAX_DROPS

# faces in the order of chunk.frag: +y, -y, +x, -x, -z, +z  -> (normal, u axis, v axis)
_FACES = (
    ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
    ((0, -1, 0), (1, 0, 0), (0, 0, -1)),
    ((1, 0, 0), (0, 0, -1), (0, -1, 0)),
    ((-1, 0, 0), (0, 0, 1), (0, -1, 0)),
    ((0, 0, -1), (-1, 0, 0), (0, -1, 0)),
    ((0, 0, 1), (1, 0, 0), (0, -1, 0)),
)
BOB_HEIGHT = 0.06


def cube_vertices():
    """(36, 9) float32: position, normal, uv, face id. Texture v grows downwards on the sides
    (the top of the side texture is at the top of the cube)."""
    rows = []
    for face, (n, u, v) in enumerate(_FACES):
        n, u, v = np.array(n, float), np.array(u, float), np.array(v, float)
        corners = []
        for a, b in ((0, 0), (1, 0), (1, 1), (0, 1)):
            p = n * 0.5 + u * (a - 0.5) + v * (b - 0.5)
            corners.append((p, (a, b)))
        # counter-clockwise seen from outside: check against the normal
        p0, p1, p2 = (c[0] for c in corners[:3])
        order = (0, 1, 2, 0, 2, 3) if np.dot(np.cross(p1 - p0, p2 - p0), n) > 0 else (0, 2, 1, 0, 3, 2)
        for i in order:
            p, t = corners[i]
            rows.append([*p, *n, *t, face])
    return np.array(rows, dtype='f4')


def instance_data(drops):
    """(len, 6) float32: center xyz, rotation, size, block id."""
    data = np.empty((len(drops), 6), dtype='f4')
    for i, d in enumerate(drops):
        bob = BOB_HEIGHT * (1.0 + math.sin(d.age * 2.6 + d.spin * 3.0)) if not d.attracted else 0.0
        data[i] = (d.feet.x, d.feet.y + DROP_SIZE * 0.5 + bob, d.feet.z, d.spin, DROP_SIZE, d.item)
    return data


class DropRenderer:
    def __init__(self, ctx, program):
        self.ctx = ctx
        self.program = program
        self.vbo = ctx.buffer(cube_vertices().tobytes())
        self.instances = ctx.buffer(reserve=MAX_DROPS * 6 * 4, dynamic=True)
        self.vao = ctx.vertex_array(program, [
            (self.vbo, '3f 3f 2f 1f', 'in_position', 'in_normal', 'in_uv', 'in_face'),
            (self.instances, '4f 2f/i', 'in_place', 'in_item'),
        ], skip_errors=True)
        self.count = 0

    def update(self, drops):
        """Upload this frame's drops (once per frame, before the shadow and scene passes)."""
        drops = drops[-MAX_DROPS:]
        self.count = len(drops)
        if self.count:
            self.instances.write(instance_data(drops).tobytes())

    def render(self):
        if self.count:
            self.vao.render(instances=self.count)

    def release(self):
        self.vao.release()
        self.vbo.release()
        self.instances.release()
