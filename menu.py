"""Start menu: pick an existing world or create a new one.

MenuModel holds the state and logic (testable without a window);
MenuScreen draws it with pygame.font through the UI overlay and runs its loop.
"""
import hashlib
import random
import time
from dataclasses import dataclass, field

import pygame as pg

from settings import GENERATOR_VERSION
from storage import WorldStore, WorldFormatError, list_worlds

TITLE = 'MinesteinKraft'
MAX_NAME_LENGTH = 32
MAX_SEED_LENGTH = 24


def new_world_seed():
    return random.SystemRandom().getrandbits(48)


def parse_seed(text):
    """Empty -> random; digits -> that number; any other text -> stable number from the text."""
    text = text.strip()
    if not text:
        return new_world_seed()
    if text.lstrip('-').isdigit():
        return abs(int(text)) % (1 << 63)
    return int.from_bytes(hashlib.sha256(text.encode('utf-8')).digest()[:6], 'big')


def default_world_name(existing_names):
    n = 1
    while f'Monde {n}' in existing_names:
        n += 1
    return f'Monde {n}'


def format_date(timestamp):
    return time.strftime('%d/%m/%Y %H:%M', time.localtime(timestamp)) if timestamp else ''


@dataclass
class MenuItem:
    kind: str          # 'world', 'broken', 'new', 'quit'
    label: str
    detail: str = ''
    info: object = None


@dataclass
class MenuModel:
    worlds: list
    items: list = field(default_factory=list)
    selected: int = 0
    mode: str = 'list'     # 'list' or 'new'
    name: str = ''
    seed: str = ''
    field_index: int = 0   # 0: name, 1: seed (new world form)
    message: str = ''

    def __post_init__(self):
        for w in self.worlds:
            if w.error:
                self.items.append(MenuItem('broken', w.name, 'illisible : ' + w.error, w))
            else:
                detail = f'joué le {format_date(w.last_played)}  -  {w.chunk_count} chunks'
                self.items.append(MenuItem('world', w.name, detail, w))
        self.items.append(MenuItem('new', '+ Nouveau monde'))
        self.items.append(MenuItem('quit', 'Quitter'))

    # ------------------------------------------------------------------ list
    def move(self, step):
        self.selected = (self.selected + step) % len(self.items)
        self.message = ''

    def activate(self, index=None):
        """Returns ('open', WorldInfo), ('quit',) or None (form opened / message shown)."""
        if index is not None:
            self.selected = index
        item = self.items[self.selected]
        if item.kind == 'world':
            return 'open', item.info
        if item.kind == 'quit':
            return ('quit',)
        if item.kind == 'broken':
            self.message = f'« {item.label} » ne peut pas être ouvert (fichier conservé tel quel).'
            return None
        self.open_new_form()
        return None

    # ------------------------------------------------------------------ new world form
    def open_new_form(self):
        self.mode = 'new'
        self.name = default_world_name({w.name for w in self.worlds})
        self.seed = ''
        self.field_index = 0
        self.message = ''

    def cancel(self):
        """Esc: leave the form, or quit from the list."""
        if self.mode == 'new':
            self.mode = 'list'
            self.message = ''
            return None
        return ('quit',)

    def switch_field(self):
        self.field_index = 1 - self.field_index

    def type_text(self, text):
        if self.field_index == 0:
            self.name = (self.name + text)[:MAX_NAME_LENGTH]
        else:
            self.seed = (self.seed + text)[:MAX_SEED_LENGTH]

    def backspace(self):
        if self.field_index == 0:
            self.name = self.name[:-1]
        else:
            self.seed = self.seed[:-1]

    def submit(self):
        """Returns ('create', name, seed) or None with a message."""
        name = self.name.strip()
        if not name:
            self.message = 'Donne un nom au monde.'
            return None
        return 'create', name, parse_seed(self.seed)


# ---------------------------------------------------------------------- rendering
BG_TOP = (70, 140, 200)
BG_BOTTOM = (20, 50, 90)
PANEL = (0, 0, 0, 110)
HIGHLIGHT = (255, 255, 255, 60)
TEXT = (255, 255, 255)
DIM = (190, 205, 220)
ERROR = (255, 150, 140)


class MenuScreen:
    """Runs the start menu in the game window; returns an open WorldStore or None (quit)."""

    def __init__(self, app, worlds_dir):
        self.app = app
        self.worlds_dir = worlds_dir
        self.model = MenuModel(list_worlds(worlds_dir))
        self.rects = []  # (rect, item index) of the visible rows, for the mouse
        self.fonts = {}

    # ------------------------------------------------------------------ helpers
    def font(self, size):
        size = max(10, int(size))
        if size not in self.fonts:
            self.fonts[size] = pg.font.Font(None, size)
        return self.fonts[size]

    @staticmethod
    def background(size):
        w, h = size
        surface = pg.Surface(size, pg.SRCALPHA)
        for y in range(h):
            t = y / max(1, h - 1)
            color = [int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)]
            pg.draw.line(surface, color, (0, y), (w, y))
        return surface

    @staticmethod
    def rect(surface, color, rect, width=0, radius=0):
        """Rounded rectangle blended over the surface (pygame.draw would overwrite the alpha)."""
        layer = pg.Surface(rect.size, pg.SRCALPHA)
        pg.draw.rect(layer, color, layer.get_rect(), width=width, border_radius=radius)
        surface.blit(layer, rect.topleft)

    def text(self, surface, string, size, color, center=None, topleft=None):
        image = self.font(size).render(string, True, color)
        rect = image.get_rect(center=center) if center else image.get_rect(topleft=topleft)
        surface.blit(image, rect)
        return rect

    # ------------------------------------------------------------------ drawing
    def draw(self):
        w, h = self.app.window_size
        surface = self.background((w, h))
        m = self.model
        self.text(surface, TITLE, h * 0.11, TEXT, center=(w // 2, int(h * 0.13)))

        panel = pg.Rect(0, 0, min(int(w * 0.8), 760), int(h * 0.62))
        panel.center = (w // 2, int(h * 0.56))
        self.rect(surface, PANEL, panel, radius=12)

        if m.mode == 'list':
            self.draw_list(surface, panel, h)
            hint = 'Flèches / souris : choisir   Entrée / clic : valider   Échap : quitter'
        else:
            self.draw_form(surface, panel, h)
            hint = 'Tab : changer de champ   Entrée : créer   Échap : retour'
        if m.message:
            self.text(surface, m.message, h * 0.032, ERROR, center=(w // 2, panel.bottom + int(h * 0.04)))
        self.text(surface, hint, h * 0.028, DIM, center=(w // 2, int(h * 0.96)))
        return surface

    def draw_list(self, surface, panel, h):
        m = self.model
        row_h = int(h * 0.085)
        visible = max(1, (panel.height - 20) // row_h)
        first = min(max(0, m.selected - visible // 2), max(0, len(m.items) - visible))
        self.rects = []
        for row, index in enumerate(range(first, min(len(m.items), first + visible))):
            item = m.items[index]
            rect = pg.Rect(panel.x + 12, panel.y + 10 + row * row_h, panel.width - 24, row_h - 6)
            if index == m.selected:
                self.rect(surface, HIGHLIGHT, rect, radius=8)
            color = ERROR if item.kind == 'broken' else TEXT
            if item.detail:
                self.text(surface, item.label, h * 0.042, color, topleft=(rect.x + 16, rect.y + 4))
                self.text(surface, item.detail, h * 0.028, DIM, topleft=(rect.x + 16, rect.y + int(row_h * 0.52)))
            else:
                self.text(surface, item.label, h * 0.042, color, topleft=(rect.x + 16, rect.y + int(row_h * 0.22)))
            self.rects.append((rect, index))

    def draw_form(self, surface, panel, h):
        m = self.model
        self.text(surface, 'Nouveau monde', h * 0.05, TEXT, topleft=(panel.x + 24, panel.y + 18))
        fields = [('Nom', m.name, ''), ('Graine (facultatif)', m.seed, 'vide = aléatoire')]
        self.rects = []
        for i, (label, value, placeholder) in enumerate(fields):
            y = panel.y + int(h * 0.13) + i * int(h * 0.17)
            self.text(surface, label, h * 0.032, DIM, topleft=(panel.x + 24, y))
            box = pg.Rect(panel.x + 24, y + int(h * 0.045), panel.width - 48, int(h * 0.065))
            self.rect(surface, (255, 255, 255, 40 if i != m.field_index else 90), box, radius=6)
            if i == m.field_index:
                self.rect(surface, TEXT, box, width=2, radius=6)
            caret = '|' if i == m.field_index and (pg.time.get_ticks() // 500) % 2 == 0 else ''
            shown = value + caret if value or caret else placeholder
            self.text(surface, shown, h * 0.04, TEXT if value else DIM, topleft=(box.x + 12, box.y + int(h * 0.015)))
            self.rects.append((box, i))

    def show_loading(self, title, fraction=None):
        """Loading screen with an optional progress bar (also called from world generation)."""
        pg.event.pump()  # keep the window responsive
        w, h = self.app.window_size
        surface = self.background((w, h))
        self.text(surface, title, h * 0.05, TEXT, center=(w // 2, h // 2 - int(h * 0.05)))
        if fraction is not None:
            bar = pg.Rect(0, 0, int(w * 0.5), int(h * 0.03))
            bar.center = (w // 2, h // 2 + int(h * 0.03))
            self.rect(surface, (255, 255, 255, 60), bar, radius=6)
            done = bar.copy()
            done.width = int(bar.width * max(0.0, min(1.0, fraction)))
            if done.width > 0:
                self.rect(surface, TEXT, done, radius=6)
        self.present(surface)

    def present(self, surface):
        self.app.ctx.clear(0, 0, 0)
        self.app.ui.draw(surface)
        pg.display.flip()

    # ------------------------------------------------------------------ loop
    def run(self):
        pg.key.start_text_input()
        try:
            while True:
                for event in pg.event.get():
                    result = self.handle_event(event)
                    if result is not None:
                        return self.perform(result)
                self.present(self.draw())
                self.app.clock.tick(60)
        finally:
            pg.key.stop_text_input()

    def handle_event(self, event):
        m = self.model
        if event.type == pg.QUIT:
            return ('quit',)
        if event.type == pg.WINDOWSIZECHANGED:
            self.app.on_resize(event.x, event.y)
            return None
        if m.mode == 'list':
            if event.type == pg.KEYDOWN:
                if event.key in (pg.K_UP, pg.K_z, pg.K_w):
                    m.move(-1)
                elif event.key in (pg.K_DOWN, pg.K_s):
                    m.move(1)
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    return m.activate()
                elif event.key == pg.K_ESCAPE:
                    return m.cancel()
            elif event.type == pg.MOUSEMOTION:
                for rect, index in self.rects:
                    if rect.collidepoint(event.pos):
                        m.selected = index
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                for rect, index in self.rects:
                    if rect.collidepoint(event.pos):
                        return m.activate(index)
            elif event.type == pg.MOUSEWHEEL:
                m.move(-event.y)
        else:
            if event.type == pg.TEXTINPUT:
                m.type_text(event.text)
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_BACKSPACE:
                    m.backspace()
                elif event.key in (pg.K_TAB, pg.K_UP, pg.K_DOWN):
                    m.switch_field()
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    return m.submit()
                elif event.key == pg.K_ESCAPE:
                    return m.cancel()
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                for rect, index in self.rects:
                    if rect.collidepoint(event.pos):
                        m.field_index = index
        return None

    def perform(self, action):
        """Turn a menu action into an open WorldStore (None = quit)."""
        if action[0] == 'quit':
            return None
        if action[0] == 'open':
            try:
                return WorldStore.open(action[1].path)
            except WorldFormatError as error:
                self.model.message = str(error)
                return self.run()
        _, name, seed = action
        return WorldStore.create(self.worlds_dir, name, seed, GENERATOR_VERSION)
