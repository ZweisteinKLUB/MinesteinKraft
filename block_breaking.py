"""Progressive block breaking and procedural crack textures (no OpenGL here)."""
import math
import numpy as np
from settings import BREAK_TIME, DEFAULT_BREAK_TIME, CRACK_STAGES, CRACK_TEXTURE_SIZE, SEED


class BlockBreaker:
    """Accumulates breaking time on the targeted block while the button is held."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.target = None
        self.progress = 0.0

    @property
    def stage(self):
        """Crack stage 0..CRACK_STAGES-1, or -1 when nothing is being broken."""
        if self.target is None:
            return -1
        return min(int(self.progress * CRACK_STAGES), CRACK_STAGES - 1)

    def update(self, target, voxel_id, holding, dt):
        """Advance by ``dt`` seconds. Returns True when the target block breaks."""
        if not holding or not voxel_id or target is None:
            self.reset()
            return False
        target = tuple(int(v) for v in target)
        if target != self.target:  # aiming at another block: start over
            self.target = target
            self.progress = 0.0
        self.progress += dt / BREAK_TIME.get(int(voxel_id), DEFAULT_BREAK_TIME)
        if self.progress >= 1.0:
            self.reset()
            return True
        return False


def make_crack_stages(size=CRACK_TEXTURE_SIZE, stages=CRACK_STAGES, seed=SEED):
    """RGBA crack images, shape (stages, size, size, 4), uint8.

    Cracks grow from the center as random walks that branch; every pixel gets
    a "reveal time" and stage s shows the pixels revealed before (s + 1) / stages,
    so each stage contains the previous one.
    """
    rng = np.random.default_rng(seed)
    reveal = np.full((size, size), np.inf)
    c = (size - 1) / 2
    walkers = [(c, c, a + rng.normal(0, 0.3), 0.0, size * 0.55)
               for a in np.linspace(0, 2 * math.pi, 4, endpoint=False) + rng.uniform(0, math.pi)]
    while walkers:
        x, y, angle, t, length = walkers.pop()
        for _ in range(int(length)):
            angle += rng.normal(0, 0.45)
            x += math.cos(angle)
            y += math.sin(angle)
            ix, iy = int(round(x)), int(round(y))
            if not (0 <= ix < size and 0 <= iy < size):
                break
            t += 1.0
            reveal[iy, ix] = min(reveal[iy, ix], t)
            if rng.random() < 0.18 and length > 3:
                side = rng.choice((-1, 1))
                walkers.append((x, y, angle + side * rng.uniform(0.6, 1.2), t, length * 0.5))
    finite = np.isfinite(reveal)
    reveal[finite] /= reveal[finite].max()

    images = np.zeros((stages, size, size, 4), dtype=np.uint8)
    for s in range(stages):
        visible = reveal <= (s + 1) / stages
        images[s][visible] = (30, 25, 20, 210)
    return images
