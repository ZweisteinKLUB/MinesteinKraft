"""Scene effects drawn by the renderer: the sea surface, rain / snow and lightning bolts."""
import random
import numpy as np
import moderngl as mgl
from settings import glm, math, FOG_END, RAIN_DROPS


def water_grid(n):
    """Vertices in [-1, 1]^2 (n x n cells) and triangle indices of the sea grid."""
    t = np.linspace(-1.0, 1.0, n + 1, dtype='f4')
    gx, gz = np.meshgrid(t, t)
    vertices = np.stack([gx.ravel(), gz.ravel()], axis=1).astype('f4')
    i = np.arange(n)
    a = (i[:, None] * (n + 1) + i[None, :]).ravel()   # cell corners
    b, c, d = a + 1, a + n + 1, a + n + 2
    indices = np.stack([a, c, b, b, c, d], axis=1).astype('u4').ravel()
    return vertices, indices


class WaterSurface:
    """The sea: a grid following the camera, waves and shading done in shaders/water.*."""

    def __init__(self, ctx, program, cells):
        self.ctx = ctx
        self.program = program
        self.radius = FOG_END + 40.0
        vertices, indices = water_grid(cells)
        self.vbo = ctx.buffer(vertices.tobytes())
        self.ibo = ctx.buffer(indices.tobytes())
        self.vao = ctx.vertex_array(program, [(self.vbo, '2f', 'in_grid')], index_buffer=self.ibo,
                                    index_element_size=4)
        program['u_radius'] = self.radius

    def render(self, camera_pos, ssr):
        self.program['u_center'] = (float(math.floor(camera_pos.x)), float(math.floor(camera_pos.z)))
        if 'u_ssr' in self.program:
            self.program['u_ssr'] = 1 if ssr else 0
        self.vao.render()

    def release(self):
        for obj in (self.vao, self.vbo, self.ibo):
            obj.release()


class Precipitation:
    """Rain drops, snow flakes and splashes: positions computed on the GPU from the instance id."""

    def __init__(self, ctx, program, count=RAIN_DROPS):
        self.ctx = ctx
        self.program = program
        self.count = count
        self.vao = ctx.vertex_array(program, [])

    def render(self, rain, underwater):
        if rain < 0.01 or underwater:
            return
        ctx = self.ctx
        ctx.disable(mgl.CULL_FACE)
        ctx.depth_mask = False
        ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA
        self.program['u_mode'] = 0
        self.vao.render(mgl.TRIANGLES, vertices=6, instances=self.count)
        self.program['u_mode'] = 1
        self.vao.render(mgl.TRIANGLES, vertices=6, instances=self.count // 6)
        ctx.depth_mask = True
        ctx.enable(mgl.CULL_FACE)

    def release(self):
        self.vao.release()


def bolt_segments(seed, ground, top_y):
    """Jagged polyline of a lightning bolt from the clouds down to ``ground``, plus branches.

    Returns a list of (points, width, intensity) with points as glm.vec3.
    """
    rng = random.Random(seed)
    start = glm.vec3(ground.x + rng.uniform(-60, 60), top_y, ground.z + rng.uniform(-60, 60))
    points = [start, glm.vec3(ground)]
    for level in range(7):  # midpoint displacement
        spread = glm.distance(start, ground) * 0.11 / (1.5 ** level)
        refined = [points[0]]
        for a, b in zip(points, points[1:]):
            m = (a + b) * 0.5 + glm.vec3(rng.uniform(-spread, spread), rng.uniform(-spread, spread) * 0.3,
                                         rng.uniform(-spread, spread))
            refined += [m, b]
        points = refined
    bolts = [(points, 0.6, 1.0)]
    for _ in range(rng.randint(2, 5)):  # branches from the upper part
        i = rng.randrange(len(points) // 8, len(points) // 2)
        p = glm.vec3(points[i])
        direction = glm.normalize(points[i + 1] - points[i] + glm.vec3(rng.uniform(-1, 1), 0, rng.uniform(-1, 1)))
        branch = [p]
        for _ in range(rng.randint(8, 20)):
            direction = glm.normalize(direction + glm.vec3(rng.uniform(-0.6, 0.6), rng.uniform(-0.3, 0.2),
                                                           rng.uniform(-0.6, 0.6)))
            direction.y = min(direction.y, -0.2)
            p = p + direction * rng.uniform(6, 14)
            branch.append(p)
        bolts.append((branch, 0.3, 0.45))
    return bolts


def ribbon_vertices(bolts):
    """Two vertices per point (each side of the ribbon), as triangles."""
    data = []
    for points, width, intensity in bolts:
        for a, b in zip(points, points[1:]):
            d = glm.normalize(b - a)
            quad = [(a, -1), (a, 1), (b, 1), (a, -1), (b, 1), (b, -1)]
            for p, side in quad:
                data.append((p.x, p.y, p.z, d.x, d.y, d.z, side, width, intensity))
    return np.array(data, dtype='f4')


class Lightning:
    """Bolts of the current strikes (geometry built once per strike)."""

    def __init__(self, ctx, program):
        self.ctx = ctx
        self.program = program
        self.cache = {}  # strike seed -> (vbo, vao)

    def render(self, strikes, ground_of, top_y):
        """``ground_of(strike)``: height where the bolt hits."""
        live = set()
        for strike in strikes:
            if not strike.visible:
                continue
            live.add(strike.seed)
            if strike.seed not in self.cache:
                ground = glm.vec3(strike.x, ground_of(strike), strike.z)
                vbo = self.ctx.buffer(ribbon_vertices(bolt_segments(strike.seed, ground, top_y)).tobytes())
                vao = self.ctx.vertex_array(self.program, [(vbo, '3f 3f 1f 1f 1f', 'in_position', 'in_direction',
                                                            'in_side', 'in_width', 'in_intensity')])
                self.cache[strike.seed] = (vbo, vao)
            flicker = min(1.0, strike.flash()) * 0.8 + 0.2
            self.program['u_brightness'] = flicker
            self.ctx.disable(mgl.CULL_FACE)
            self.ctx.blend_func = mgl.ONE, mgl.ONE
            self.ctx.depth_mask = False
            self.cache[strike.seed][1].render()
            self.ctx.depth_mask = True
            self.ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA
            self.ctx.enable(mgl.CULL_FACE)
        for seed in [s for s in self.cache if s not in live]:
            vbo, vao = self.cache.pop(seed)
            vao.release()
            vbo.release()

    def release(self):
        for vbo, vao in self.cache.values():
            vao.release()
            vbo.release()
        self.cache.clear()
