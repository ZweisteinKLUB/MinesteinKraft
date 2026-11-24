"""2D overlay: a pygame Surface drawn over the whole window (menus, loading screens)."""
import moderngl as mgl
import pygame as pg
from shader_program import load_program

UI_TEXTURE_UNIT = 4


class UIOverlay:
    def __init__(self, ctx):
        self.ctx = ctx
        self.program = load_program(ctx, 'ui')
        self.program['u_ui'] = UI_TEXTURE_UNIT
        self.vao = ctx.vertex_array(self.program, [])
        self.texture = None

    def draw(self, surface):
        size = surface.get_size()
        if self.texture is None or self.texture.size != size:
            if self.texture is not None:
                self.texture.release()
            self.texture = self.ctx.texture(size, 4)
            self.texture.filter = (mgl.NEAREST, mgl.NEAREST)
        self.texture.write(pg.image.tobytes(surface, 'RGBA', True))
        self.texture.use(location=UI_TEXTURE_UNIT)
        self.ctx.disable(mgl.DEPTH_TEST | mgl.CULL_FACE)
        self.vao.render(mode=mgl.TRIANGLE_STRIP, vertices=4)
        self.ctx.enable(mgl.DEPTH_TEST | mgl.CULL_FACE)

    def release(self):
        if self.texture is not None:
            self.texture.release()
        self.vao.release()
