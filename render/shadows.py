"""Cascaded shadow maps of the sun (or the moon at night).

Each cascade is an orthographic depth map centered on the camera: a sharp one nearby and a
wider one further away. Their centers are snapped to whole texels in light space, so the
shadow edges do not shimmer when the camera moves.
"""
import moderngl as mgl
from settings import glm, CHUNK_SPHERE_RADIUS, SHADOW_CASCADE_RADIUS

LIGHT_DISTANCE = 320.0   # the light camera stands this far from the center, towards the light
DEPTH_RANGE = 640.0


def light_view(light_dir, center):
    up = glm.vec3(1, 0, 0) if abs(light_dir.z) > 0.95 else glm.vec3(0, 0, 1)
    return glm.lookAt(center + light_dir * LIGHT_DISTANCE, center, up)


def cascade_matrices(light_dir, center, radius, size):
    """(view, projection) of a cascade, its center snapped to the texel grid."""
    light_dir = glm.normalize(light_dir)
    rotation = light_view(light_dir, glm.vec3(0))  # light space without translation
    texel = 2.0 * radius / size
    p = rotation * glm.vec4(center, 1.0)
    p.x = round(p.x / texel) * texel
    p.y = round(p.y / texel) * texel
    snapped = glm.vec3(glm.inverse(rotation) * p)
    view = light_view(light_dir, snapped)
    proj = glm.ortho(-radius, radius, -radius, radius, 1.0, DEPTH_RANGE)
    return view, proj


class ShadowMaps:
    def __init__(self, ctx, size, cascades):
        self.ctx = ctx
        self.size = size
        self.cascades = cascades
        self.radii = SHADOW_CASCADE_RADIUS
        self.textures, self.fbos = [], []
        for _ in range(2):  # the shaders always declare two maps
            depth = ctx.depth_texture((size, size))
            depth.compare_func = '<='           # hardware filtered comparisons
            depth.filter = (mgl.LINEAR, mgl.LINEAR)
            depth.repeat_x = depth.repeat_y = False
            self.textures.append(depth)
            self.fbos.append(ctx.framebuffer(depth_attachment=depth))
        self.matrices = [glm.mat4(), glm.mat4()]
        self.views = [glm.mat4(), glm.mat4()]
        self.projs = [glm.mat4(), glm.mat4()]
        self.active = False

    def use(self, units):
        for texture, unit in zip(self.textures, units):
            texture.use(location=unit)

    def update(self, light_dir, light_strength, center):
        """Compute the cascades for this frame; no shadows when the light is too dim."""
        self.active = light_strength > 1e-3
        for i in range(self.cascades):
            view, proj = cascade_matrices(light_dir, center, self.radii[i], self.size)
            self.views[i], self.projs[i] = view, proj
            self.matrices[i] = proj * view

    def chunk_in_cascade(self, i, chunk):
        """Does the chunk overlap the area covered by cascade ``i`` (light space x / y)?"""
        p = self.views[i] * glm.vec4(chunk.center, 1.0)
        limit = self.radii[i] + CHUNK_SPHERE_RADIUS
        return abs(p.x) <= limit and abs(p.y) <= limit

    def render(self, programs, world, mobs, mob_renderer, extra=()):
        """Draw the depth of the blocks and mobs (and ``extra`` draw calls) seen from the light."""
        if not self.active:
            return
        ctx = self.ctx
        ctx.disable(mgl.CULL_FACE)  # voxel surfaces have no back faces: draw both sides
        ctx.polygon_offset = (1.5, 2.0)
        for program in programs:
            program['u_shadow_pass'] = 1
        chunk_program = world.app.shader_program.chunk
        for i in range(self.cascades):
            self.fbos[i].use()
            self.fbos[i].clear(depth=1.0)
            for program in programs:
                program['m_proj'].write(self.projs[i])
                program['m_view'].write(self.views[i])
            for chunk in world.chunks.values():
                if chunk.mesh is not None and not chunk.is_empty and self.chunk_in_cascade(i, chunk):
                    chunk_program['m_model'].write(chunk.m_model)
                    chunk.mesh.render()
            for mob in mobs:
                mob_renderer.render(mob)
            for draw in extra:
                draw()
        for program in programs:
            program['u_shadow_pass'] = 0
        ctx.polygon_offset = (0.0, 0.0)
        ctx.enable(mgl.CULL_FACE)

    def release(self):
        for fbo, texture in zip(self.fbos, self.textures):
            fbo.release()
            texture.release()
