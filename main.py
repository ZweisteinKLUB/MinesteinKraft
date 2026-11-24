from settings import *
import moderngl as mgl
import pygame as pg
import sys
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
    def __init__(self):
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
        self.player.set_aspect_ratio(width / height)
        self.shader_program.set_projection(self.player.m_proj)

    # ------------------------------------------------------------------ mouse
    def set_mouse_capture(self, captured):
        self.mouse_captured = captured
        pg.mouse.set_relative_mode(captured)  # hides the cursor and grabs the mouse
        pg.mouse.get_rel()  # discard motion accumulated while released

    # ------------------------------------------------------------------ game loop
    def on_init(self):
        self.texture = Textures(self)
        w, h = self.window_size
        self.player = Player(self, aspect_ratio=w / h)
        self.shader_program = ShaderProgram(self)
        self.scene = Scene(self)
        self.player.spawn()  # stand on the ground once the world exists

    def update(self):
        self.player.update()
        self.shader_program.update()
        self.scene.update()

        self.delta_time = self.clock.tick(FPS)
        self.time = pg.time.get_ticks() * 0.001

        pg.display.set_caption(f'MinesteinKraft - {self.clock.get_fps() :.0f} FPS')

    def render(self):
        self.ctx.clear(color=BG_COLOR)
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
        pg.quit()
        sys.exit()


def main():
    app = VoxelEngine()
    app.run()


if __name__ == '__main__':
    main()
