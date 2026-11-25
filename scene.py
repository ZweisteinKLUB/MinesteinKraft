from settings import *
from world import World
from world_objects.voxel_marker import VoxelMarker
from world_objects.cracks import Cracks
from mobs.render import MobRenderer
from mobs.manager import MobManager


class Scene:
    """What the world contains; render/pipeline.py draws it (with the sky, the sea and the weather)."""

    def __init__(self, app):
        self.app = app
        self.world = World(self.app, app.store)
        self.voxel_marker = VoxelMarker(self.world.voxel_handler)
        self.cracks = Cracks(self.world.voxel_handler)
        self.mob_renderer = MobRenderer(app)
        self.mobs = MobManager(app)

    def update(self):
        dt = self.app.delta_time * 0.001
        self.app.environment.update(dt, self.app.player.position)
        self.world.update()
        self.mobs.update(dt)
        self.voxel_marker.update()
