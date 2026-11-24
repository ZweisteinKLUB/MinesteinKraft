import numpy as np
import pytest
from settings import STONE, LEAVES, BREAK_TIME, CRACK_STAGES
from block_breaking import BlockBreaker, make_crack_stages


def hold(breaker, target, voxel_id, seconds, dt=1 / 60):
    broken = False
    for _ in range(round(seconds / dt)):
        broken = breaker.update(target, voxel_id, True, dt) or broken
    return broken


def test_breaks_after_block_break_time():
    b = BlockBreaker()
    assert not hold(b, (1, 2, 3), STONE, BREAK_TIME[STONE] * 0.95)
    assert b.stage == CRACK_STAGES - 1
    assert hold(b, (1, 2, 3), STONE, BREAK_TIME[STONE] * 0.1)
    assert b.stage <= 0  # restarted from zero after breaking


def test_harder_blocks_take_longer():
    assert BREAK_TIME[STONE] > BREAK_TIME[LEAVES]
    b = BlockBreaker()
    assert hold(b, (0, 0, 0), LEAVES, BREAK_TIME[LEAVES] + 0.05)


def test_stages_progress():
    b = BlockBreaker()
    stages = []
    for _ in range(59):  # stops just before the block breaks
        b.update((0, 0, 0), STONE, True, BREAK_TIME[STONE] / 60)
        stages.append(b.stage)
    assert stages == sorted(stages) and stages[0] == 0


def test_release_or_retarget_resets():
    b = BlockBreaker()
    hold(b, (0, 0, 0), STONE, 1.0)
    b.update((0, 0, 0), STONE, False, 0.1)
    assert b.stage == -1 and b.progress == 0
    hold(b, (0, 0, 0), STONE, 1.0)
    b.update((5, 0, 0), STONE, True, 0.0)
    assert b.progress == 0 and b.target == (5, 0, 0)


def test_crack_stages_grow():
    images = make_crack_stages()
    assert images.shape[0] == CRACK_STAGES and images.dtype == np.uint8
    visible = images[..., 3] > 0
    counts = visible.reshape(CRACK_STAGES, -1).sum(axis=1)
    assert counts[0] > 0 and counts[-1] > counts[0]
    for s in range(1, CRACK_STAGES):
        assert np.all(visible[s - 1] <= visible[s])  # each stage contains the previous one
