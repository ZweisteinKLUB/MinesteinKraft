"""HDR post-processing: bloom, light shafts, tone mapping and anti-aliasing."""
import moderngl as mgl
from shader_program import UNIT_POST

BLOOM_LEVELS = 6
BLOOM_STRENGTH = 0.07
BLOOM_THRESHOLD = 0.9


class PostProcess:
    def __init__(self, ctx, programs, size, bloom=True, godrays=True):
        self.ctx = ctx
        self.p = programs
        self.bloom_enabled = bloom
        self.godrays_enabled = godrays
        self.vaos = {}  # one empty vertex array per program
        self.targets = []
        self.resize(size)

    def fullscreen(self, program):
        vao = self.vaos.get(id(program))
        if vao is None:
            vao = self.vaos[id(program)] = self.ctx.vertex_array(program, [])
        vao.render(mgl.TRIANGLES, vertices=3)

    def color_target(self, size, components=4, dtype='f2'):
        texture = self.ctx.texture(size, components, dtype=dtype)
        texture.filter = (mgl.LINEAR, mgl.LINEAR)
        texture.repeat_x = texture.repeat_y = False
        fbo = self.ctx.framebuffer([texture])
        self.targets += [fbo, texture]
        return texture, fbo

    def resize(self, size):
        for obj in self.targets:
            obj.release()
        self.targets = []
        self.size = size
        w, h = size
        self.bloom = []
        bw, bh = max(1, w // 2), max(1, h // 2)
        for _ in range(BLOOM_LEVELS):
            self.bloom.append(self.color_target((bw, bh), 3))
            bw, bh = max(1, bw // 2), max(1, bh // 2)
        self.shafts = self.color_target((max(1, w // 2), max(1, h // 2)), 3)
        self.ldr = self.color_target(size, 4, 'f1')

    # ------------------------------------------------------------------ passes
    def render_bloom(self, hdr):
        ctx = self.ctx
        ctx.disable(mgl.BLEND)
        down = self.p.bloom_down
        source, source_size = hdr, hdr.size
        for i, (texture, fbo) in enumerate(self.bloom):
            fbo.use()
            source.use(location=UNIT_POST[0])
            down['u_source'] = UNIT_POST[0]
            down['u_texel'] = (1.0 / source_size[0], 1.0 / source_size[1])
            down['u_first'] = 1 if i == 0 else 0
            if 'u_threshold' in down:
                down['u_threshold'] = BLOOM_THRESHOLD
            self.fullscreen(down)
            source, source_size = texture, texture.size
        up = self.p.bloom_up
        ctx.enable(mgl.BLEND)
        ctx.blend_func = mgl.ONE, mgl.ONE
        for i in range(BLOOM_LEVELS - 1, 0, -1):
            texture = self.bloom[i][0]
            self.bloom[i - 1][1].use()
            texture.use(location=UNIT_POST[0])
            up['u_source'] = UNIT_POST[0]
            up['u_texel'] = (1.0 / texture.size[0], 1.0 / texture.size[1])
            up['u_radius'] = 1.0
            self.fullscreen(up)
        ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA

    def render_shafts(self, hdr, depth, light_uv, time):
        ctx = self.ctx
        ctx.disable(mgl.BLEND)
        texture, fbo = self.shafts
        fbo.use()
        g = self.p.godrays
        hdr.use(location=UNIT_POST[0])
        depth.use(location=UNIT_POST[1])
        g['u_hdr'] = UNIT_POST[0]
        g['u_depth'] = UNIT_POST[1]
        g['u_light_uv'] = tuple(light_uv)
        if 'u_jitter' in g:
            g['u_jitter'] = time % 100.0
        self.fullscreen(g)

    def render(self, hdr, depth, screen, shafts=None):
        """Bloom and shafts from ``hdr`` / ``depth``, then the final image on ``screen``.

        ``shafts``: None, or (light screen uv, strength, tint rgb) for the light shafts.
        """
        ctx = self.ctx
        ctx.disable(mgl.DEPTH_TEST | mgl.CULL_FACE)
        if self.bloom_enabled:
            self.render_bloom(hdr)
        else:
            self.bloom[0][1].clear()
        strength, tint = 0.0, (0.0, 0.0, 0.0)
        if self.godrays_enabled and shafts is not None and shafts[1] > 1e-3:
            light_uv, strength, tint = shafts
            self.render_shafts(hdr, depth, light_uv, 0.0)
        ctx.disable(mgl.BLEND)

        c = self.p.composite
        texture, fbo = self.ldr
        fbo.use()
        hdr.use(location=UNIT_POST[0])
        self.bloom[0][0].use(location=UNIT_POST[1])
        self.shafts[0].use(location=UNIT_POST[2])
        c['u_hdr'] = UNIT_POST[0]
        c['u_bloom'] = UNIT_POST[1]
        c['u_godrays'] = UNIT_POST[2]
        c['u_bloom_strength'] = BLOOM_STRENGTH if self.bloom_enabled else 0.0
        c['u_godray_strength'] = strength
        c['u_godray_tint'] = tuple(tint)
        self.fullscreen(c)

        screen.use()
        f = self.p.fxaa
        texture.use(location=UNIT_POST[0])
        f['u_ldr'] = UNIT_POST[0]
        f['u_texel'] = (1.0 / self.size[0], 1.0 / self.size[1])
        self.fullscreen(f)

        ctx.enable(mgl.DEPTH_TEST | mgl.CULL_FACE | mgl.BLEND)

    def release(self):
        for obj in self.targets:
            obj.release()
        for vao in self.vaos.values():
            vao.release()
