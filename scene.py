from settings import *
import moderngl as mgl
from world import World
from world_objects.voxel_marker import VoxelMarker
from world_objects.cracks import Cracks
from world_objects.water import Water
from world_objects.clouds import Clouds
from mobs.render import MobRenderer

class Scene:
    def __init__(self, app):
        self.app = app
        self.world = World(self.app, app.store)
        self.voxel_marker = VoxelMarker(self.world.voxel_handler)
        self.cracks = Cracks(self.world.voxel_handler)
        self.water = Water(app)
        self.clouds = Clouds(app)
        self.mob_renderer = MobRenderer(app)

    def update(self):
        self.world.update()
        self.voxel_marker.update()
        self.clouds.update()

    def render(self):
        # chunks rendering
        self.world.render()
        self.cracks.render()

        # mobs (the player's own body only shows in third person view)
        self.mob_renderer.render(self.app.player)
        
        # rendering without cull face
        self.app.ctx.disable(mgl.CULL_FACE)
        self.clouds.render()
        self.water.render()
        self.app.ctx.enable(mgl.CULL_FACE)
             
        #voxel selection
        self.voxel_marker.render()