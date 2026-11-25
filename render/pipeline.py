"""The frame: shadow maps, HDR scene (blocks, mobs, sky, sea, weather), post-processing."""
import moderngl as mgl
from settings import glm, GRAPHICS_PRESETS, CLOUD_ALTITUDE, WATER_LINE, CHUNK_SIZE
from shader_program import (ENV_BINDING, UNIT_SHADOW, UNIT_SCENE_COLOR, UNIT_SCENE_DEPTH, UNIT_HEIGHTMAP,
                            UNIT_NOISE)
from atmosphere.lighting import luminance, smoothstep
from render.env_buffer import EnvBuffer
from render.textures import HeightMap, create_noise_texture
from render.shadows import ShadowMaps
from render.effects import WaterSurface, Precipitation, Lightning
from render.postprocess import PostProcess
from render.drops import DropRenderer


class Renderer:
    def __init__(self, app, quality):
        self.app = app
        self.ctx = ctx = app.ctx
        self.quality = quality
        preset = GRAPHICS_PRESETS[quality]
        sp = app.shader_program
        self.env_buffer = EnvBuffer(ctx)
        self.noise = create_noise_texture(ctx)
        self.heightmap = HeightMap(ctx)
        self.shadows = ShadowMaps(ctx, preset['shadow_size'], preset['cascades'])
        self.water = WaterSurface(ctx, sp.water, preset['water_grid'])
        self.precipitation = Precipitation(ctx, sp.precipitation)
        self.lightning = Lightning(ctx, sp.lightning)
        self.drops = DropRenderer(ctx, sp.item)
        self.sky_vao = ctx.vertex_array(sp.sky, [])
        self.ssr = preset['ssr']
        self.size = tuple(app.window_size)
        self.post = PostProcess(ctx, sp, self.size, bloom=preset['bloom'], godrays=preset['godrays'])
        self.targets = []
        self.create_targets()

    # ------------------------------------------------------------------ targets
    def create_targets(self):
        for obj in self.targets:
            obj.release()
        ctx, size = self.ctx, self.size
        self.hdr = ctx.texture(size, 4, dtype='f2')
        self.depth = ctx.depth_texture(size)
        self.scene_fbo = ctx.framebuffer([self.hdr], self.depth)
        # copy of the opaque scene, read by the water (refraction, reflections)
        self.copy_color = ctx.texture(size, 4, dtype='f2')
        self.copy_depth = ctx.depth_texture(size)
        self.copy_fbo = ctx.framebuffer([self.copy_color], self.copy_depth)
        for texture in (self.hdr, self.copy_color):
            texture.filter = (mgl.LINEAR, mgl.LINEAR)
            texture.repeat_x = texture.repeat_y = False
        for texture in (self.depth, self.copy_depth):
            texture.filter = (mgl.NEAREST, mgl.NEAREST)
            texture.repeat_x = texture.repeat_y = False
        self.targets = [self.scene_fbo, self.copy_fbo, self.hdr, self.depth, self.copy_color, self.copy_depth]

    def resize(self, size):
        self.size = tuple(size)
        self.create_targets()
        self.post.resize(self.size)

    # ------------------------------------------------------------------ helpers
    def bind_textures(self):
        self.env_buffer.bind(ENV_BINDING)
        self.shadows.use(UNIT_SHADOW)
        self.noise.use(location=UNIT_NOISE)
        self.heightmap.texture.use(location=UNIT_HEIGHTMAP)

    def light_shafts(self, env, camera):
        """(screen uv, strength, tint) of the light shafts of the sun, or None."""
        lit = env.lighting
        sun = env.clock.sun_direction
        moon = env.clock.moon_direction
        body, strength = (sun, 1.0) if sun.y > -0.04 else (moon, 0.35 * env.clock.moon_illumination)
        if body.y < -0.04:
            return None
        clip = camera.m_proj * camera.m_view * glm.vec4(camera.view_position + body * 1000.0, 1.0)
        if clip.w <= 0.0:
            return None
        uv = glm.vec2(clip.x, clip.y) / clip.w * 0.5 + 0.5
        off = max(abs(uv.x - 0.5), abs(uv.y - 0.5))
        strength *= 1.0 - smoothstep(0.5, 1.1, off)
        strength *= 1.0 - smoothstep(0.7, 1.0, env.weather.params.clouds)
        if camera.camera_underwater or strength <= 0.0:
            return None
        return uv, strength * 0.9, (1.0, 0.95, 0.85)

    def strike_ground(self, world, strike):
        x, z = int(strike.x), int(strike.z)
        if world.column_loaded(x // CHUNK_SIZE, z // CHUNK_SIZE):
            return max(float(world.surface_height(x, z)), WATER_LINE)
        return WATER_LINE

    # ------------------------------------------------------------------ frame
    def render(self):
        app, ctx = self.app, self.ctx
        scene, player, env = app.scene, app.player, app.environment
        world, sp = scene.world, app.shader_program

        self.heightmap.update(world)
        lit = env.lighting
        self.shadows.update(lit.light_dir, luminance(lit.light_color), player.view_position)
        bolt = None
        if env.strikes:
            s = env.strikes[-1]
            bolt = (s.x, self.strike_ground(world, s), s.z)
        self.env_buffer.fill(env, player, self.shadows, self.size, bolt)
        self.bind_textures()

        # shadow maps
        mobs = [player] + [m for m in scene.mobs.mobs]
        self.drops.update(scene.drops.drops)
        self.shadows.render((sp.chunk, sp.mob, sp.item), world, mobs, scene.mob_renderer, extra=(self.drops.render,))

        # opaque scene in HDR
        sp.set_projection(player.m_proj)
        sp.update()
        self.scene_fbo.use()
        ctx.clear(0.0, 0.0, 0.0, 1.0, depth=1.0)
        world.render()
        scene.cracks.render()
        for mob in mobs:
            scene.mob_renderer.render(mob)
        self.drops.render()

        # sky behind everything (only where nothing was drawn)
        ctx.depth_func = '<='
        ctx.depth_mask = False
        ctx.disable(mgl.CULL_FACE)
        self.sky_vao.render(mgl.TRIANGLES, vertices=3)
        ctx.enable(mgl.CULL_FACE)
        ctx.depth_mask = True
        ctx.depth_func = '<'

        # the sea, refracting and reflecting a copy of the opaque scene
        ctx.copy_framebuffer(self.copy_fbo, self.scene_fbo)
        self.copy_color.use(location=UNIT_SCENE_COLOR)
        self.copy_depth.use(location=UNIT_SCENE_DEPTH)
        self.scene_fbo.use()
        ctx.disable(mgl.CULL_FACE | mgl.BLEND)
        self.water.render(player.view_position, self.ssr)
        ctx.enable(mgl.CULL_FACE | mgl.BLEND)

        # weather effects, selection
        self.precipitation.render(env.weather.params.rain, player.camera_underwater)
        self.lightning.render(env.strikes, lambda strike: self.strike_ground(world, strike), CLOUD_ALTITUDE * 0.55)
        scene.voxel_marker.render()

        self.post.render(self.hdr, self.depth, ctx.screen, self.light_shafts(env, player))

    def release(self):
        for obj in self.targets:
            obj.release()
        for obj in (self.env_buffer, self.noise, self.heightmap, self.shadows, self.water,
                    self.precipitation, self.lightning, self.drops, self.sky_vao, self.post):
            obj.release()
