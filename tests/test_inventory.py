import numpy as np
import pytest
from settings import glm, SAND, GRASS, STONE, WOOD, WATER_LINE
from inventory import Inventory, Stack, HOTBAR_SIZE, SLOT_COUNT, STACK_MAX
from world_objects.drops import DropManager, Drop, DROP_SIZE, PICKUP_DELAY
from render.drops import cube_vertices, instance_data


# ---------------------------------------------------------------------- inventory
def test_add_stacks_then_fills_hotbar_first():
    inv = Inventory()
    assert inv.add(SAND) == 0 and inv.add(SAND, 2) == 0
    assert inv.slots[0] == Stack(SAND, 3)
    inv.add(STONE)
    assert inv.slots[1] == Stack(STONE, 1)
    # same item goes on the existing stack (wherever it is), overflow in a new slot
    inv.add(SAND, STACK_MAX)
    assert inv.slots[0].count == STACK_MAX and inv.slots[2] == Stack(SAND, 3)
    assert inv.count(SAND) == STACK_MAX + 3


def test_full_inventory_refuses():
    inv = Inventory()
    for i in range(SLOT_COUNT):
        inv.slots[i] = Stack(100 + i, STACK_MAX)
    assert not inv.can_add(SAND)
    assert inv.add(SAND, 5) == 5
    inv.slots[7] = Stack(SAND, STACK_MAX - 2)
    assert inv.can_add(SAND) and inv.add(SAND, 5) == 3


def test_building_uses_the_selected_slot_until_empty():
    inv = Inventory()
    inv.slots[1] = Stack(WOOD, 2)
    assert inv.take_selected() is None          # slot 0 is empty: nothing to build with
    inv.scroll(1)
    assert inv.selected == 1 and inv.selected_item() == WOOD
    assert inv.take_selected() == WOOD and inv.slots[1].count == 1
    assert inv.take_selected() == WOOD and inv.slots[1] is None
    assert inv.take_selected() is None and inv.selected_item() is None


def test_scroll_wraps():
    inv = Inventory()
    inv.scroll(-1)
    assert inv.selected == HOTBAR_SIZE - 1
    inv.scroll(2)
    assert inv.selected == 1


def test_click_pick_put_merge_swap():
    inv = Inventory()
    inv.slots[0] = Stack(SAND, 10)
    inv.slots[6] = Stack(SAND, 60)
    inv.slots[7] = Stack(STONE, 3)
    inv.click(0)                                 # pick up
    assert inv.held == Stack(SAND, 10) and inv.slots[0] is None
    inv.click(6)                                 # merge up to the max, keep the rest
    assert inv.slots[6].count == STACK_MAX and inv.held == Stack(SAND, 6)
    inv.click(7)                                 # swap with another item
    assert inv.slots[7] == Stack(SAND, 6) and inv.held == Stack(STONE, 3)
    inv.click(12)                                # put down in an empty slot
    assert inv.slots[12] == Stack(STONE, 3) and inv.held is None


def test_quick_move_between_hotbar_and_backpack():
    inv = Inventory()
    inv.slots[2] = Stack(GRASS, 5)
    inv.slots[9] = Stack(GRASS, 62)
    inv.quick_move(2)                            # fills the backpack stack, rest in a free slot
    assert inv.slots[2] is None and inv.slots[9].count == STACK_MAX
    assert inv.slots[HOTBAR_SIZE] == Stack(GRASS, 3)
    inv.quick_move(HOTBAR_SIZE)                  # back to the first free hotbar slot
    assert inv.slots[0] == Stack(GRASS, 3)


def test_drop_held_goes_back():
    inv = Inventory()
    inv.slots[3] = Stack(SAND, 4)
    inv.click(3)
    assert inv.drop_held() is None and inv.slots[3] == Stack(SAND, 4)


def test_json_round_trip_and_bad_data():
    inv = Inventory()
    inv.add(SAND, 70)
    inv.slots[20] = Stack(WOOD, 2)
    inv.select(3)
    again = Inventory.from_json(inv.to_json())
    assert again.slots == inv.slots and again.selected == 3
    assert Inventory.from_json('not json').slots == [None] * SLOT_COUNT
    assert Inventory.from_json(None).selected == 0


# ---------------------------------------------------------------------- drops
def flat_ground(x, y, z):
    return 1.0 if y < 10 else 0.0


def test_drop_falls_and_rests_on_the_ground():
    drops = DropManager(flat_ground)
    drops.add(Drop(SAND, (0.5, 14.0, 0.5)))
    for _ in range(120):
        drops.update(1 / 60)
    d = drops.drops[0]
    assert d.feet.y == pytest.approx(10.0, abs=1e-3) and d.on_ground


def test_drop_floats_on_the_sea():
    drops = DropManager(lambda x, y, z: 1.0 if y < 0 else 0.0)
    drops.add(Drop(WOOD, (0.5, 1.0, 0.5)))
    for _ in range(600):
        drops.update(1 / 60)
    assert drops.drops[0].center.y == pytest.approx(WATER_LINE, abs=0.05)


def test_drop_pushed_out_of_a_placed_block():
    solid = {(0, 10, 0)}
    drops = DropManager(lambda x, y, z: 1.0 if y < 10 or (x, y, z) in solid else 0.0)
    drops.add(Drop(SAND, (0.5, 10.0, 0.5)))
    drops.update(1 / 60)
    assert drops.drops[0].feet.y >= 11.0


def test_player_picks_drops_up():
    drops = DropManager(flat_ground)
    inv = Inventory()
    drops.spawn(STONE, (3, 10, 3))
    player = glm.vec3(4.6, 10.0, 3.5)  # feet, next to the block
    picked = 0
    for _ in range(30):                      # not before the pickup delay
        picked += drops.update(1 / 60, player, inv)
    assert picked == 0 and len(drops) == 1
    for _ in range(int(PICKUP_DELAY * 60) + 60):
        picked += drops.update(1 / 60, player, inv)
    assert picked == 1 and len(drops) == 0 and inv.slots[0] == Stack(STONE, 1)


def test_drop_stays_when_inventory_is_full():
    drops = DropManager(flat_ground)
    inv = Inventory()
    for i in range(SLOT_COUNT):
        inv.slots[i] = Stack(GRASS, STACK_MAX)
    drops.add(Drop(SAND, (0.5, 10.0, 0.5), age=5.0))
    for _ in range(60):
        drops.update(1 / 60, glm.vec3(0.5, 10.0, 0.5), inv)
    assert len(drops) == 1


def test_drops_json_round_trip():
    drops = DropManager(flat_ground)
    drops.add(Drop(SAND, (1.5, 10.0, 2.5), count=3, age=4.0))
    again = DropManager(flat_ground)
    again.load_json(drops.to_json())
    d = again.drops[0]
    assert (d.item, d.count) == (SAND, 3) and d.feet == glm.vec3(1.5, 10.0, 2.5)
    again.load_json('[[1, 2]]')
    assert len(again) == 0


# ---------------------------------------------------------------------- drawing data
def test_cube_faces_point_outwards():
    v = cube_vertices()
    assert v.shape == (36, 9)
    tri = v[:, :3].reshape(-1, 3, 3)
    normals = v[::3, 3:6]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    assert np.all(np.einsum('ij,ij->i', cross, normals) > 0)       # counter-clockwise from outside
    assert np.all(np.abs(v[:, :3]) == 0.5)
    assert sorted(set(v[:, 8].astype(int))) == list(range(6))


def test_instance_data():
    data = instance_data([Drop(SAND, (1.0, 2.0, 3.0))])
    assert data.shape == (1, 6) and data[0, 4] == pytest.approx(DROP_SIZE) and data[0, 5] == SAND
    assert data[0, 1] >= 2.0 + DROP_SIZE * 0.5


# ---------------------------------------------------------------------- HUD
def test_block_icon_is_an_opaque_cube_on_a_transparent_background():
    from hud import load_atlas, make_block_icon
    atlas = load_atlas()
    icon = make_block_icon(atlas, GRASS, 48)
    assert icon.shape == (48, 48, 4) and icon.dtype == np.uint8
    assert icon[0, 0, 3] == 0 and icon[47, 0, 3] == 0      # corners: transparent
    assert icon[24, 24, 3] == 255                          # middle: the cube
    top, left, right = icon[10, 24, :3], icon[30, 12, :3], icon[30, 36, :3]
    assert top[1] > top[0]                                 # grass on top
    assert left.sum() > right.sum()                        # right side in the shade


def test_slot_layout_does_not_overlap():
    import pygame as pg
    from hud import slot_rects, slot_at, backpack_layout
    for size in ((1280, 720), (1920, 1080), (640, 360)):
        rects = slot_rects(size)
        assert len(rects) == SLOT_COUNT
        for i, a in enumerate(rects):
            assert pg.Rect(0, 0, *size).contains(a)
            assert all(not a.colliderect(b) for b in rects[i + 1:])
        panel, _ = backpack_layout(size)
        assert slot_at(size, rects[7].center, True) == 7
        assert slot_at(size, rects[7].center, False) is None
        assert slot_at(size, rects[2].center, False) == 2


def test_drop_in_a_pit_next_to_the_player_is_picked_up():
    hole = {(1, 8, 0), (1, 9, 0)}
    drops = DropManager(lambda x, y, z: 1.0 if y < 10 and (x, y, z) not in hole else 0.0)
    inv = Inventory()
    drops.add(Drop(SAND, (1.6, 8.0, 0.5), age=1.0))   # bottom of a 2-block hole beside the feet
    for _ in range(60):
        drops.update(1 / 60, glm.vec3(0.5, 10.0, 0.5), inv)
    assert inv.count(SAND) == 1


def test_resting_drop_falls_when_its_block_is_removed():
    removed = set()
    drops = DropManager(lambda x, y, z: 1.0 if y < 10 and (x, y, z) not in removed else 0.0)
    drops.add(Drop(SAND, (0.5, 10.0, 0.5)))
    for _ in range(30):
        drops.update(1 / 60)
    assert drops.drops[0].feet.y == pytest.approx(10.0, abs=1e-3)
    removed.add((0, 9, 0))
    for _ in range(60):
        drops.update(1 / 60)
    assert drops.drops[0].feet.y == pytest.approx(9.0, abs=1e-3)
