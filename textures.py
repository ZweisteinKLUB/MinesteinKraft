import pygame as pg
import moderngl as mgl
from paths import resource_path
from block_breaking import make_crack_stages


class Textures:
    def __init__(self, app):
        self.app = app
        self.ctx = app.ctx

        # load texture
        self.texture_0 = self.load('frame.png')
        self.texture_array_0 = self.load('tex_array_0.png', is_tex_array=True)

        self.cracks = load_crack_textures(self.ctx)

        #assign texture unit
        self.texture_0.use(location=0)
        self.texture_array_0.use(location=1)
        self.cracks.use(location=3)

    def load(self, file_name, is_tex_array=False):
        return load_texture(self.ctx, file_name, is_tex_array)


def load_texture(ctx, file_name, is_tex_array=False):
    # pg.image.load works without a display surface; no convert() needed
    texture = pg.image.load(str(resource_path('assets', file_name)))
    texture = pg.transform.flip(texture, flip_x=True, flip_y=False)

    if is_tex_array:
        num_layers = 3 * texture.get_height() // texture.get_width()  # 3 textures per layer
        texture = ctx.texture_array(
            size=(texture.get_width(), texture.get_height() // num_layers, num_layers),
            components=4,
            data=pg.image.tobytes(texture, 'RGBA')
        )
    else:
        texture = ctx.texture(
            size=texture.get_size(),
            components=4,
            data=pg.image.tobytes(texture, 'RGBA', False)
        )
    # clamp anisotropy to what the driver supports
    texture.anisotropy = min(16.0, float(ctx.info.get('GL_MAX_TEXTURE_MAX_ANISOTROPY') or 16.0))
    texture.build_mipmaps()
    texture.filter = (mgl.NEAREST, mgl.NEAREST)
    return texture


def load_crack_textures(ctx):
    """Procedural crack stages as a texture array (one layer per stage)."""
    images = make_crack_stages()
    stages, height, width, _ = images.shape
    texture = ctx.texture_array(size=(width, height, stages), components=4, data=images.tobytes())
    texture.filter = (mgl.NEAREST, mgl.NEAREST)
    return texture
