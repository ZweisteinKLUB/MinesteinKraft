from settings import *
import moderngl as mgl
import pygame as pg
import sys
import argparse
from pathlib import Path
import noise
import paths
from menu import MenuScreen
from ui import UIOverlay
from shader_program import ShaderProgram
from scene import Scene
from player import Player
from textures import Textures

GL_ERROR_HELP = (
    "MinesteinKraft needs OpenGL {major}.{minor} (core profile).\n\n"
    "Update your graphics driver. Virtual machines, remote desktops and WSL "
    "often provide an older OpenGL version.\n\nDetails: {error}"
)


def fit_window_size(preferred, desktop, ratio=WIN_SCREEN_RATIO):
    """Shrink ``preferred`` (keeping its aspect ratio) so it fits in ``ratio`` of ``desktop``."""
    w, h = preferred
    scale = min(1.0, desktop[0] * ratio / w, desktop[1] * ratio / h)
    return max(320, int(w * scale)), max(180, int(h * scale))


def show_fatal_error(message):
    print(message, file=sys.stderr)
    try:
        pg.display.message_box('MinesteinKraft', message, message_type='error')
    except Exception:
        pass


class VoxelEngine:
    def __init__(self, store=None, worlds_dir=None):
        """Open ``store`` directly, or show the world selection menu first."""
        pg.init()
        self.window_size = self.create_window()
        self.ctx = self.create_context()

        self.ctx.enable(flags=mgl.DEPTH_TEST | mgl.CULL_FACE | mgl.BLEND)
        self.ctx.gc_mode = 'auto'

        self.clock = pg.time.Clock()
        self.delta_time = 0
        self.time = 0

        self.mouse_captured = False
        self.is_running = True
        self.ui = UIOverlay(self.ctx)
        self.screens = MenuScreen(self, worlds_dir or paths.worlds_dir())
        if store is None:
            store = self.screens.run()  # start menu: pick or create a world
            if store is None:
                self.is_running = False
                self.store = None
                return
        self.store = store
        self.screens.show_loading(f'Chargement de « {store.name} »…')
        self.on_init()
        self.set_mouse_capture(True)

    # ------------------------------------------------------------------ window / GL
    @staticmethod
    def set_gl_attributes(samples):
        pg.display.gl_set_attribute(pg.GL_CONTEXT_MAJOR_VERSION, MAJOR_VER)
        pg.display.gl_set_attribute(pg.GL_CONTEXT_MINOR_VERSION, MINOR_VER)
        pg.display.gl_set_attribute(pg.GL_CONTEXT_PROFILE_MASK, pg.GL_CONTEXT_PROFILE_CORE)
        if sys.platform == 'darwin':
            # macOS only provides 3.2+ core contexts when forward-compatible
            pg.display.gl_set_attribute(pg.GL_CONTEXT_FLAGS, pg.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG)
        pg.display.gl_set_attribute(pg.GL_DEPTH_SIZE, DEPTH_SIZE)
        pg.display.gl_set_attribute(pg.GL_MULTISAMPLEBUFFERS, 1 if samples else 0)
        pg.display.gl_set_attribute(pg.GL_MULTISAMPLESAMPLES, samples)

    def create_window(self):
        desktops = pg.display.get_desktop_sizes()
        size = fit_window_size(WIN_RES, desktops[0]) if desktops else WIN_RES
        flags = pg.OPENGL | pg.DOUBLEBUF | pg.RESIZABLE

        last_error = None
        for samples in dict.fromkeys((NUM_SAMPLES, 0)):  # retry without MSAA
            self.set_gl_attributes(samples)
            try:
                pg.display.set_mode(size, flags=flags)
                return pg.display.get_window_size()
            except pg.error as error:
                last_error = error
        show_fatal_error(GL_ERROR_HELP.format(major=MAJOR_VER, minor=MINOR_VER, error=last_error))
        pg.quit()
        sys.exit(1)

    def create_context(self):
        try:
            return mgl.create_context(require=MAJOR_VER * 100 + MINOR_VER * 10)
        except Exception as error:
            show_fatal_error(GL_ERROR_HELP.format(major=MAJOR_VER, minor=MINOR_VER, error=error))
            pg.quit()
            sys.exit(1)

    def on_resize(self, width, height):
        if width <= 0 or height <= 0:  # minimized
            return
        self.window_size = (width, height)
        self.ctx.viewport = (0, 0, width, height)
        if not hasattr(self, 'player'):  # still in the menu
            return
        self.player.set_aspect_ratio(width / height)
        self.shader_program.set_projection(self.player.m_proj)

    # ------------------------------------------------------------------ mouse
    def set_mouse_capture(self, captured):
        self.mouse_captured = captured
        if not captured and hasattr(self, 'scene'):
            self.scene.world.voxel_handler.breaking = False
        pg.mouse.set_relative_mode(captured)  # hides the cursor and grabs the mouse
        pg.mouse.get_rel()  # discard motion accumulated while released

    # ------------------------------------------------------------------ game loop
    def on_init(self):
        noise.set_seed(self.store.seed)  # the world's own generator seed
        if self.store.generator_version != GENERATOR_VERSION:
            print(f'warning: world made with generator v{self.store.generator_version}, '
                  f'current is v{GENERATOR_VERSION}: new chunks may not match', file=sys.stderr)
        self.texture = Textures(self)
        w, h = self.window_size
        self.player = Player(self, aspect_ratio=w / h)
        self.shader_program = ShaderProgram(self)
        self.scene = Scene(self)
        world = self.scene.world

        if self.store.chunk_count() == 0:
            # first launch of this world: build and save the island
            world.generate_base_area(lambda f: self.screens.show_loading('Génération du monde…', f))

        saved = self.store.load_player()
        if saved:
            world.load_area(saved['x'], saved['z'], radius=2)
            self.player.restore(saved)
        else:
            world.load_area(CENTER_XZ, CENTER_XZ, radius=2)
            self.player.spawn()  # stand on the ground of the island
        world.save()

    def save_and_close(self):
        world = self.scene.world
        world.save()
        self.store.touch()
        world.release()
        self.store.close()

    def update(self):
        self.player.update()
        self.shader_program.update()
        self.scene.update()

        self.delta_time = self.clock.tick(FPS)
        self.time = pg.time.get_ticks() * 0.001

        pg.display.set_caption(f'MinesteinKraft - {self.clock.get_fps() :.0f} FPS')

    def render(self):
        self.ctx.clear(color=WATER_FOG_COLOR if self.player.head_underwater else BG_COLOR)
        self.scene.render()
        pg.display.flip()

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.is_running = False
            elif event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                # first Esc releases the mouse, a second one quits
                if self.mouse_captured:
                    self.set_mouse_capture(False)
                else:
                    self.is_running = False
            elif event.type == pg.WINDOWFOCUSLOST:
                self.set_mouse_capture(False)
            elif event.type == pg.MOUSEBUTTONDOWN and not self.mouse_captured:
                self.set_mouse_capture(True)  # this click only recaptures the mouse
            elif event.type == pg.WINDOWSIZECHANGED:
                self.on_resize(event.x, event.y)
            else:
                self.player.handle_event(event=event)

    def run(self):
        while self.is_running:
            self.handle_events()
            self.update()
            self.render()
        if self.store is not None:
            self.save_and_close()
        pg.quit()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='MinesteinKraft voxel game')
    parser.add_argument('--world-dir', type=Path, default=None,
                        help='folder holding the saves (default: per-user data folder)')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    app = VoxelEngine(worlds_dir=paths.worlds_dir(args.world_dir))
    app.run()
    sys.exit()


if __name__ == '__main__':
    main()
