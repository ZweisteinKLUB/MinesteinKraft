"""Heads-up display: the hotbar (5 slots at the bottom of the screen) and the backpack screen (I).

Drawn with pygame into a window-sized surface, uploaded to the GPU only when something changed
(ui.UIOverlay), then blended over the frame.
"""
import numpy as np
import pygame as pg

from settings import SAND, GRASS, DIRT, STONE, SNOW, LEAVES, WOOD
from paths import resource_path
from inventory import HOTBAR_SIZE, BACKPACK_SIZE
from ui import UIOverlay

ITEM_NAMES = {SAND: 'Sable', GRASS: 'Herbe', DIRT: 'Terre', STONE: 'Pierre', SNOW: 'Neige',
              LEAVES: 'Feuilles', WOOD: 'Bois'}
BACKPACK_COLUMNS = 5
NAME_SECONDS = 2.0   # the name of the selected block shows this long above the hotbar

SLOT_BG = (20, 24, 32, 150)
SLOT_BORDER = (255, 255, 255, 70)
SELECTED = (255, 255, 255, 235)
HOVER = (255, 255, 255, 45)
PANEL = (18, 22, 30, 215)
SHADE = (0, 0, 0, 110)
TEXT = (255, 255, 255)
DIM = (190, 200, 215)


# ---------------------------------------------------------------------- block icons
def load_atlas():
    """The block textures as an (h, w, 4) uint8 array: one row of 3 squares per block id
    (bottom, side, top)."""
    surface = pg.image.load(str(resource_path('assets', 'tex_array_0.png')))
    rgb = pg.surfarray.array3d(surface).transpose(1, 0, 2)
    try:
        alpha = pg.surfarray.array_alpha(surface).T
    except (ValueError, pg.error):
        alpha = np.full(rgb.shape[:2], 255, np.uint8)
    return np.dstack([rgb, alpha]).astype(np.uint8)


def block_faces(atlas, block_id):
    """(top, side) square textures of a block."""
    tile = atlas.shape[1] // 3
    row = atlas[block_id * tile:(block_id + 1) * tile]
    return row[:, 2 * tile:3 * tile], row[:, tile:2 * tile]


def make_block_icon(atlas, block_id, size, supersample=3):
    """Isometric picture of a block: (size, size, 4) uint8 RGBA, transparent around the cube."""
    top, side = block_faces(atlas, block_id)
    n = size * supersample
    ys, xs = np.mgrid[0:n, 0:n]
    p = np.stack([(xs + 0.5) / n, (ys + 0.5) / n], axis=-1)  # [0, 1] picture coordinates
    out = np.zeros((n, n, 4), np.float32)
    m = 0.04  # margin
    s = 1 - 2 * m
    T, R, B, L = (np.array(v) * s + m for v in ((0.5, 0.0), (1.0, 0.25), (0.5, 0.5), (0.0, 0.25)))
    down = np.array((0.0, 0.5)) * s

    def paint(texture, origin, eu, ev, shade):
        # solve p = origin + u * eu + v * ev
        mat = np.linalg.inv(np.array([eu, ev]).T)
        uv = (p - origin) @ mat.T
        inside = np.all((uv >= 0) & (uv < 1), axis=-1)
        tile = texture.shape[0]
        tx = np.clip((uv[..., 0] * tile).astype(int), 0, tile - 1)
        ty = np.clip((uv[..., 1] * tile).astype(int), 0, tile - 1)
        color = texture[ty, tx].astype(np.float32)
        color[..., :3] *= shade
        out[inside] = color[inside]

    paint(top, T, R - T, L - T, 1.0)          # top: u towards the right corner, v the left one
    paint(side, L, B - L, down, 0.78)          # left side
    paint(side, B, R - B, down, 0.6)           # right side
    small = out.reshape(size, supersample, size, supersample, 4)
    # average with alpha weighting (clean edges)
    a = small[..., 3:4]
    rgb = (small[..., :3] * a).sum(axis=(1, 3)) / np.maximum(a.sum(axis=(1, 3)), 1e-6)
    alpha = a.mean(axis=(1, 3))
    return np.dstack([rgb, alpha]).clip(0, 255).astype(np.uint8)


def icon_surface(pixels):
    h, w = pixels.shape[:2]
    return pg.image.frombuffer(np.ascontiguousarray(pixels).tobytes(), (w, h), 'RGBA').copy()


# ---------------------------------------------------------------------- layout
def hotbar_rects(window_size):
    w, h = window_size
    size = int(max(40, min(84, h * 0.075)))
    gap = max(4, size // 10)
    total = HOTBAR_SIZE * size + (HOTBAR_SIZE - 1) * gap
    x0, y = (w - total) // 2, h - size - max(10, size // 4)
    return [pg.Rect(x0 + i * (size + gap), y, size, size) for i in range(HOTBAR_SIZE)]


def backpack_layout(window_size):
    """(panel rect, slot rects of the 20 backpack slots)."""
    w, h = window_size
    size = hotbar_rects(window_size)[0].width
    gap = max(4, size // 10)
    rows = BACKPACK_SIZE // BACKPACK_COLUMNS
    grid_w = BACKPACK_COLUMNS * size + (BACKPACK_COLUMNS - 1) * gap
    grid_h = rows * size + (rows - 1) * gap
    pad = size // 2
    title_h = int(size * 0.8)
    panel = pg.Rect(0, 0, grid_w + 2 * pad, grid_h + 2 * pad + title_h)
    hotbar_top = hotbar_rects(window_size)[0].top
    panel.midbottom = (w // 2, hotbar_top - pad)
    if panel.top < 8:
        panel.top = 8
    x0, y0 = panel.x + pad, panel.y + pad + title_h
    slots = [pg.Rect(x0 + (i % BACKPACK_COLUMNS) * (size + gap), y0 + (i // BACKPACK_COLUMNS) * (size + gap),
                     size, size) for i in range(BACKPACK_SIZE)]
    return panel, slots


def slot_rects(window_size):
    """Rects of all the slots (hotbar 0..4 then backpack 5..24)."""
    return hotbar_rects(window_size) + backpack_layout(window_size)[1]


def slot_at(window_size, pos, backpack_open):
    rects = slot_rects(window_size) if backpack_open else hotbar_rects(window_size)
    for i, rect in enumerate(rects):
        if rect.collidepoint(pos):
            return i
    return None


# ---------------------------------------------------------------------- drawing
class HUD:
    def __init__(self, ctx):
        self.overlay = UIOverlay(ctx)
        self.atlas = load_atlas()
        self.icons = {}
        self.fonts = {}
        self.surface = None
        self.key = None
        self.name_until = 0.0
        self.last_selected = None

    def font(self, size):
        size = max(10, int(size))
        if size not in self.fonts:
            self.fonts[size] = pg.font.Font(None, size)
        return self.fonts[size]

    def icon(self, item, size):
        key = (item, size)
        if key not in self.icons:
            self.icons[key] = icon_surface(make_block_icon(self.atlas, item, size))
        return self.icons[key]

    @staticmethod
    def rect(surface, color, rect, width=0, radius=0):
        layer = pg.Surface(rect.size, pg.SRCALPHA)
        pg.draw.rect(layer, color, layer.get_rect(), width=width, border_radius=radius)
        surface.blit(layer, rect.topleft)

    def text(self, surface, string, size, color, **anchor):
        font = self.font(size)
        shadow = font.render(string, True, (0, 0, 0))
        image = font.render(string, True, color)
        rect = image.get_rect(**anchor)
        surface.blit(shadow, rect.move(max(1, size // 16), max(1, size // 16)))
        surface.blit(image, rect)
        return rect

    def draw_stack(self, surface, stack, rect):
        """Icon of the stack, its count in the bottom-right corner when there are several."""
        icon = self.icon(stack.item, int(rect.width * 0.72))
        surface.blit(icon, icon.get_rect(center=rect.center))
        if stack.count > 1:
            self.text(surface, str(stack.count), rect.height * 0.42, TEXT,
                      bottomright=(rect.right - rect.width // 12, rect.bottom - rect.height // 20))

    def draw_slot(self, surface, inventory, index, rect, selected=False, hover=False):
        radius = rect.width // 8
        self.rect(surface, SLOT_BG, rect, radius=radius)
        if hover:
            self.rect(surface, HOVER, rect, radius=radius)
        stack = inventory.slots[index]
        if stack is not None:
            self.draw_stack(surface, stack, rect)
        if selected:
            self.rect(surface, SELECTED, rect.inflate(4, 4), width=3, radius=radius + 2)
        else:
            self.rect(surface, SLOT_BORDER, rect, width=1, radius=radius)

    def draw(self, size, inventory, backpack_open, mouse_pos, show_name):
        surface = pg.Surface(size, pg.SRCALPHA)
        hover = slot_at(size, mouse_pos, True) if backpack_open and mouse_pos else None
        if backpack_open:
            surface.fill(SHADE)
            panel, slots = backpack_layout(size)
            self.rect(surface, PANEL, panel, radius=12)
            pad = slots[0].x - panel.x
            self.text(surface, 'Sac à dos', slots[0].width * 0.5, TEXT,
                      midleft=(panel.x + pad, panel.y + pad // 2 + int(slots[0].width * 0.4)))
            for i, rect in enumerate(slots):
                index = HOTBAR_SIZE + i
                self.draw_slot(surface, inventory, index, rect, hover=hover == index)
            hint = 'Clic : prendre / poser    Maj + clic : transfert rapide    Clic hors des cases : jeter    I / Échap : fermer'
            self.text(surface, hint, max(14, slots[0].width * 0.3), DIM, midbottom=(size[0] // 2, panel.top - 6))
        hot = hotbar_rects(size)
        for i, rect in enumerate(hot):
            self.draw_slot(surface, inventory, i, rect, selected=i == inventory.selected, hover=hover == i)
        if show_name and not backpack_open:
            stack = inventory.selected_stack()
            if stack is not None:
                self.text(surface, ITEM_NAMES.get(stack.item, f'Bloc {stack.item}'), hot[0].height * 0.38, TEXT,
                          midbottom=(size[0] // 2, hot[0].top - 6))
        if backpack_open and hover is not None and inventory.held is None:
            stack = inventory.slots[hover]
            if stack is not None:
                rect = slot_rects(size)[hover]
                self.text(surface, ITEM_NAMES.get(stack.item, f'Bloc {stack.item}'), rect.height * 0.34, TEXT,
                          midbottom=(rect.centerx, rect.top - 2))
        if backpack_open and inventory.held is not None and mouse_pos:
            s = hot[0].width
            self.draw_stack(surface, inventory.held, pg.Rect(mouse_pos[0] - s // 2, mouse_pos[1] - s // 2, s, s))
        return surface

    def render(self, size, inventory, backpack_open, mouse_pos, now):
        """Draw over the current framebuffer; redrawn only when something visible changed."""
        if inventory.selected != self.last_selected:
            self.last_selected = inventory.selected
            self.name_until = now + NAME_SECONDS
        show_name = now < self.name_until
        key = (tuple(size), inventory.version, backpack_open, mouse_pos if backpack_open else None, show_name)
        if key != self.key:
            self.key = key
            self.surface = self.draw(size, inventory, backpack_open, mouse_pos, show_name)
            self.overlay.draw(self.surface)
        else:
            self.overlay.draw(None)

    def release(self):
        self.overlay.release()
