"""Procedural textures of the renderer: tileable noise and the column height map."""
import numpy as np
import moderngl as mgl
from settings import CHUNK_SIZE, HEIGHTMAP_SIZE

NOISE_SIZE = 256


def tileable_noise(size, cutoff, rng):
    """Smooth periodic noise in [0, 1] with a uniform distribution (white noise low-passed by FFT)."""
    white = rng.standard_normal((size, size))
    f = np.fft.fftfreq(size) * size
    fx, fy = np.meshgrid(f, f)
    spectrum = np.fft.fft2(white) * np.exp(-(fx * fx + fy * fy) / (2.0 * cutoff * cutoff))
    smooth = np.real(np.fft.ifft2(spectrum))
    ranks = smooth.ravel().argsort().argsort()  # equalize: every value is equally likely
    return (ranks / (ranks.size - 1)).reshape(size, size)


def make_noise_data(seed=1234, size=NOISE_SIZE):
    """RGBA8 noise: r coarse, g medium, b fine, a fine (other draw)."""
    rng = np.random.default_rng(seed)
    channels = [tileable_noise(size, c, rng) for c in (6.0, 12.0, 24.0, 24.0)]
    return (np.stack(channels, axis=-1) * 255.0 + 0.5).astype('u1')


def create_noise_texture(ctx):
    data = make_noise_data()
    texture = ctx.texture((NOISE_SIZE, NOISE_SIZE), 4, data.tobytes())
    texture.repeat_x = texture.repeat_y = True
    texture.build_mipmaps()
    texture.filter = (mgl.LINEAR_MIPMAP_LINEAR, mgl.LINEAR)
    return texture


class HeightMap:
    """Top of the highest block of every loaded column, wrapped in a square texture.

    The shaders read it for sky occlusion (dark caves), rain / snow shelters and
    shallow water. Texel (x mod size, z mod size) holds column (x, z).
    """

    def __init__(self, ctx, size=HEIGHTMAP_SIZE):
        self.size = size
        self.texture = ctx.texture((size, size), 1, dtype='f1')
        self.texture.filter = (mgl.NEAREST, mgl.NEAREST)
        self.texture.repeat_x = self.texture.repeat_y = True

    def write_column(self, cx, cz, heights):
        """``heights``: (CHUNK_SIZE, CHUNK_SIZE) uint8 array indexed [z, x] for chunk column (cx, cz)."""
        x = (cx * CHUNK_SIZE) % self.size
        z = (cz * CHUNK_SIZE) % self.size
        self.texture.write(np.ascontiguousarray(heights, dtype='u1').tobytes(),
                           viewport=(x, z, CHUNK_SIZE, CHUNK_SIZE))

    def update(self, world):
        """Upload the columns the world changed since the last call."""
        for cx, cz in world.take_changed_columns():
            heights = world.column_heights(cx, cz)
            if heights is not None:
                self.write_column(cx, cz, heights)

    def release(self):
        self.texture.release()
