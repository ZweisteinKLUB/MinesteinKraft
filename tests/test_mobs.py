import math
import random
from types import SimpleNamespace

import pytest

from settings import *
from mobs.mob import wrap_angle, turn_towards, locomotion_blend, yaw_to_model_angle
from mobs.tourbeux import Tourbeux, WANDER, CHASE
from mobs.manager import MobManager

GROUND = 10        # top of the land
SEA_FLOOR = 2      # top of the sea bottom (below WATER_LINE)


class FakeWorld:
    """Flat land at y < 10, a sea strip for 15 <= x < 20, optional extra blocks."""

    def __init__(self, sea=(15, 20)):
        self.sea = sea
        self.extra = set()

    def top(self, x, z):
        return SEA_FLOOR if self.sea[0] <= x < self.sea[1] else GROUND

    def block_height(self, x, y, z):
        return 1.0 if (y < self.top(x, z) or (x, y, z) in self.extra) else 0.0

    def surface_height(self, x, z):
        return self.top(x, z)

    def voxel_at(self, x, y, z):
        return GRASS if y == self.top(x, z) - 1 else (STONE if y < self.top(x, z) else 0)

    def column_loaded(self, cx, cz):
        return True


class FakePlayer:
    def __init__(self, feet):
        self.feet = glm.vec3(feet)
        self.fly = False
        self.pushes = []

    @property
    def water_depth(self):
        return WATER_LINE - self.feet.y

    def push(self, horizontal, up=0.0):
        self.pushes.append((glm.vec3(horizontal), up))


def make_app(player_feet, world=None):
    world = world or FakeWorld()
    return SimpleNamespace(scene=SimpleNamespace(world=world), player=FakePlayer(player_feet))


def run(mob, seconds, dt=1 / 30):
    for _ in range(int(seconds / dt)):
        mob.update(dt)
        mob.update_animation(dt)


# ---------------------------------------------------------------------- helpers
def test_angles():
    assert wrap_angle(3 * math.pi) == pytest.approx(-math.pi)
    assert turn_towards(0.0, 1.0, 0.25) == pytest.approx(0.25)
    assert turn_towards(3.0, -3.0, 1.0) == pytest.approx(-3.0)        # shortest way across +-pi
    assert turn_towards(3.1, -3.1, 0.01) == pytest.approx(3.11)
    # models face +Z; the game's yaw 90 degrees faces +Z too
    assert yaw_to_model_angle(math.pi / 2) == pytest.approx(0.0)


def test_locomotion_blend_matches_ground_speed():
    w_walk, w_run, rate = locomotion_blend(3.5, 1.94, 4.89, walk_top=3.85, run_from=6.3)
    assert (w_walk, w_run) == (1.0, 0.0) and rate * 1.94 == pytest.approx(3.5)
    w_walk, w_run, rate = locomotion_blend(7.0, 1.94, 4.89, walk_top=3.85, run_from=6.3)
    assert (w_walk, w_run) == (0.0, 1.0) and rate * 4.89 == pytest.approx(7.0)
    w_walk, w_run, rate = locomotion_blend(5.0, 1.94, 4.89, walk_top=3.85, run_from=6.3)
    assert 0 < w_run < 1 and rate * (w_walk * 1.94 + w_run * 4.89) == pytest.approx(5.0)


# ---------------------------------------------------------------------- Tourbeux
def tourbeux_at(app, x, z, yaw=0.0):
    mob = Tourbeux(app, glm.vec3(x + 0.5, GROUND + 1e-4, z + 0.5), yaw, rng=random.Random(1))
    mob.on_ground = True
    return mob


def test_chases_attacks_and_knocks_back():
    app = make_app((10.5, GROUND, 0.5))
    mob = tourbeux_at(app, 0, 0)
    run(mob, 6.0)
    assert app.player.pushes, 'the player was never hit'
    push, up = app.player.pushes[0]
    assert push.x > 0 and up > 0            # pushed away from the mob
    assert glm.length(push) == pytest.approx(TOURBEUX_KNOCKBACK)
    assert abs(mob.feet.x - app.player.feet.x) <= TOURBEUX_ATTACK_RANGE + 0.1
    assert mob.animator.has('attack')


def test_attack_cooldown():
    app = make_app((2.0, GROUND, 0.5))
    mob = tourbeux_at(app, 0, 0)
    run(mob, 3.0)
    period = mob.animator.clips['attack'].duration + TOURBEUX_ATTACK_COOLDOWN
    assert len(app.player.pushes) <= math.ceil(3.0 / period) + 1


def test_ignores_far_player_and_wanders():
    app = make_app((40.5, GROUND, 0.5), FakeWorld(sea=(1000, 1001)))
    mob = tourbeux_at(app, 0, 0)
    run(mob, 5.0)
    assert mob.state == WANDER and not app.player.pushes
    assert math.hypot(mob.feet.x - 0.5, mob.feet.z - 0.5) < 12


def test_wall_blocks_the_view():
    world = FakeWorld(sea=(1000, 1001))
    for z in range(-20, 21):
        for y in range(GROUND, GROUND + 4):
            world.extra.add((5, y, z))
    app = make_app((10.5, GROUND, 0.5), world)
    mob = tourbeux_at(app, 0, 0)
    run(mob, 1.0)
    assert not mob.sees_player and mob.state == WANDER


def test_stops_at_the_shore():
    app = make_app((23.5, GROUND, 0.5))             # on land, across the sea strip 15..20
    mob = tourbeux_at(app, 5, 0)
    lowest = []
    for _ in range(int(8.0 * 30)):
        mob.update(1 / 30)
        lowest.append(mob.feet.y)
    assert mob.state == CHASE
    assert mob.feet.x + mob.width / 2 < 15.5         # never walked into the water
    assert min(lowest) > GROUND - 0.01
    assert not app.player.pushes


def test_gives_up_when_the_player_swims():
    app = make_app((16.5, WATER_LINE - 1.5, 0.5))   # swimming in the sea strip
    mob = tourbeux_at(app, 8, 0)
    run(mob, 1.0)
    assert mob.state == WANDER


def test_climbs_a_one_block_step():
    world = FakeWorld(sea=(1000, 1001))
    for x in range(4, 30):
        for z in range(-5, 6):
            world.extra.add((x, GROUND, z))         # a step of one block on the way
    app = make_app((9.5, GROUND + 1, 0.5), world)
    mob = tourbeux_at(app, 0, 0)
    run(mob, 6.0)
    assert mob.feet.y > GROUND + 0.9 and app.player.pushes


# ---------------------------------------------------------------------- manager
def test_spawn_spots_on_land_only():
    app = make_app((0.5, GROUND, 0.5))
    manager = MobManager(app, rng=random.Random(3))
    assert manager.spawn_spot(5, 5) is not None
    assert manager.spawn_spot(16, 5) is None        # sea
    app.scene.world.extra.update({(5, GROUND, 5), (5, GROUND + 1, 5)})
    assert manager.spawn_spot(5, 5) is None         # no room


def test_manager_spawns_up_to_the_limit_and_despawns_far_mobs():
    app = make_app((-40.5, GROUND, 0.5), FakeWorld(sea=(1000, 1001)))
    manager = MobManager(app, rng=random.Random(5))
    for _ in range(int(30 / 0.1)):
        manager.update(0.1)
        app.player.pushes.clear()
    assert len(manager.hostiles()) == MAX_HOSTILES
    for mob in manager.mobs:
        d = math.hypot(mob.feet.x - app.player.feet.x, mob.feet.z - app.player.feet.z)
        assert d <= DESPAWN_DISTANCE
    app.player.feet = glm.vec3(500, GROUND, 500)
    manager.enabled = False
    manager.update(0.1)
    assert manager.mobs == []
