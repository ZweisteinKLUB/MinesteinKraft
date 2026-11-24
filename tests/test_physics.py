import math
import pytest
from physics import step, collides, EPS

W, H = 0.6, 1.8
G = 28.0
JUMP_SPEED = math.sqrt(2 * G * 1.25)
DT = 1 / 60


class FakeWorld:
    """Flat ground: full blocks at y == 0 for x, z in [-20, 20)."""

    def __init__(self):
        self.blocks = {(x, 0, z): 1.0 for x in range(-20, 20) for z in range(-20, 20)}

    def __call__(self, x, y, z):
        return self.blocks.get((x, y, z), 0.0)


def simulate(world, feet, frames, wish=(0.0, 0.0), jump_at=None, step_height=0.5, on_ground=False):
    """Walking mode: gravity + horizontal wish velocity (blocks/s)."""
    vel = (0.0, 0.0, 0.0)
    max_y = feet[1]
    for i in range(frames):
        vy = vel[1] - G * DT
        if jump_at is not None and i >= jump_at and on_ground:
            vy = JUMP_SPEED
            jump_at = None
        vel = (wish[0], max(vy, -50.0), wish[1])
        feet, vel, on_ground = step(feet, vel, DT, world, W, H, step_height, on_ground)
        max_y = max(max_y, feet[1])
    return feet, on_ground, max_y


def test_falls_and_lands_on_ground():
    feet, on_ground, _ = simulate(FakeWorld(), (0.5, 10.0, 0.5), 120)
    assert on_ground
    assert feet[1] == pytest.approx(1.0, abs=2 * EPS)


def test_wall_stops_walking():
    world = FakeWorld()
    for y in (1, 2, 3):
        world.blocks[(3, y, 0)] = 1.0
    feet, _, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 120, wish=(5.0, 0.0), on_ground=True)
    assert feet[0] == pytest.approx(3 - W / 2, abs=2 * EPS)


def test_slides_along_wall_diagonally():
    world = FakeWorld()
    for z in range(-5, 10):
        for y in (1, 2):
            world.blocks[(3, y, z)] = 1.0
    feet, _, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 60, wish=(4.0, 4.0), on_ground=True)
    assert feet[0] == pytest.approx(3 - W / 2, abs=2 * EPS)
    assert feet[2] > 3.0  # kept moving along z


def test_jump_height_clears_one_block_not_two():
    _, _, max_y = simulate(FakeWorld(), (0.5, 1.0 + EPS, 0.5), 90, jump_at=0, on_ground=True)
    # above one block, well below two
    assert 1.0 + 1.0 < max_y < 1.0 + 1.5


def test_jump_onto_one_block():
    world = FakeWorld()
    for x in range(2, 10):  # a one-block-high platform
        world.blocks[(x, 1, 0)] = 1.0
    feet, on_ground, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 90, wish=(3.0, 0.0), jump_at=10, on_ground=True)
    assert on_ground and feet[1] == pytest.approx(2.0, abs=2 * EPS)
    assert feet[0] > 2.0


def test_cannot_jump_onto_two_blocks():
    world = FakeWorld()
    world.blocks[(2, 1, 0)] = 1.0
    world.blocks[(2, 2, 0)] = 1.0
    feet, _, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 90, wish=(3.0, 0.0), jump_at=10, on_ground=True)
    assert feet[0] < 2.0 and feet[1] == pytest.approx(1.0, abs=2 * EPS)


def test_auto_step_half_block():
    world = FakeWorld()
    world.blocks[(2, 1, 0)] = 0.5  # a half block "step"
    # 40 frames at 3 blocks/s: feet end at x = 2.5, on top of the step
    feet, on_ground, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 40, wish=(3.0, 0.0), on_ground=True)
    assert feet[0] > 2.0
    assert on_ground and feet[1] == pytest.approx(1.5, abs=2 * EPS)


def test_no_auto_step_on_full_block():
    world = FakeWorld()
    world.blocks[(2, 1, 0)] = 1.0
    feet, _, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 60, wish=(3.0, 0.0), on_ground=True)
    assert feet[0] == pytest.approx(2 - W / 2, abs=2 * EPS)
    assert feet[1] == pytest.approx(1.0, abs=2 * EPS)


def test_no_auto_step_in_the_air_or_when_disabled():
    world = FakeWorld()
    world.blocks[(2, 1, 0)] = 0.5
    feet, _, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 60, wish=(3.0, 0.0), step_height=0.0, on_ground=True)
    assert feet[0] < 2.0


def test_falls_into_dug_hole():
    world = FakeWorld()
    world.blocks.update({(0, -1, 0): 1.0})
    feet, on_ground, _ = simulate(world, (0.5, 1.0 + EPS, 0.5), 10, on_ground=True)
    assert on_ground and feet[1] == pytest.approx(1.0, abs=2 * EPS)
    del world.blocks[(0, 0, 0)]  # dig the block under the feet
    feet, on_ground, _ = simulate(world, feet, 60, on_ground=on_ground)
    assert on_ground and feet[1] == pytest.approx(0.0, abs=2 * EPS)


def test_no_tunneling_at_high_speed():
    world = FakeWorld()
    feet, vel, on_ground = step((0.5, 3.0, 0.5), (0.0, -50.0, 0.0), 1.0, world, W, H)  # dt clamped
    for _ in range(10):
        feet, vel, on_ground = step(feet, (0.0, -50.0, 0.0), 0.05, world, W, H, on_ground=on_ground)
    assert on_ground and feet[1] == pytest.approx(1.0, abs=2 * EPS)


def test_ceiling_stops_jump():
    world = FakeWorld()
    world.blocks[(0, 3, 0)] = 1.0  # ceiling: 2 blocks of headroom
    _, _, max_y = simulate(world, (0.5, 1.0 + EPS, 0.5), 60, jump_at=0, on_ground=True)
    assert max_y <= 3.0 - H + EPS


def test_collides():
    world = FakeWorld()
    assert collides((0.5, 0.5, 0.5), W, H, world)
    assert not collides((0.5, 1.0 + EPS, 0.5), W, H, world)
