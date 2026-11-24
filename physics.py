"""Player physics: axis-aligned box moving through a voxel world.

Pure Python, no OpenGL, so it can be unit-tested. The world is seen through a
``block_height(x, y, z)`` callback returning the height of the block's collision
box at integer voxel coordinates: 0 = empty, 1 = full block, 0.5 = half block...
A block box spans [x, x+1] x [y, y+h] x [z, z+1].

The player box is described by its ``feet`` position: center of the bottom face.
"""
import math

EPS = 1e-4            # gap kept between the player and the blocks it touches
MAX_SUBSTEP_MOVE = 0.4  # max displacement per sub-step (< 1 block: no tunneling)
MAX_DT = 0.05         # longer frames are clamped (window drag, loading hitch...)


def _box(feet, width, height):
    hw = width * 0.5
    x, y, z = feet
    return (x - hw, y, z - hw), (x + hw, y + height, z + hw)


def _hits(feet, width, height, block_height):
    """Collision boxes of the blocks overlapping the player box."""
    (x0, y0, z0), (x1, y1, z1) = _box(feet, width, height)
    hits = []
    for bx in range(math.floor(x0), math.ceil(x1)):
        for bz in range(math.floor(z0), math.ceil(z1)):
            for by in range(math.floor(y0), math.ceil(y1)):
                h = block_height(bx, by, bz)
                if h > 0 and y0 < by + h and y1 > by:
                    hits.append(((bx, by, bz), (bx + 1, by + h, bz + 1)))
    return hits


def collides(feet, width, height, block_height):
    return bool(_hits(feet, width, height, block_height))


def _move_axis(feet, axis, delta, width, height, block_height):
    """Move along one axis, stopping against blocks. Returns (feet, blocked)."""
    if delta == 0:
        return feet, False
    new = list(feet)
    new[axis] += delta
    hits = _hits(new, width, height, block_height)
    if not hits:
        return new, False

    # extent of the player box around ``feet`` on this axis: [feet - lo, feet + hi]
    lo, hi = (0.0, height) if axis == 1 else (width * 0.5, width * 0.5)
    if delta > 0:
        limit = min(b_min[axis] for b_min, _ in hits) - hi - EPS
        new[axis] = max(feet[axis], limit)  # never pushed backwards
    else:
        limit = max(b_max[axis] for _, b_max in hits) + lo + EPS
        new[axis] = min(feet[axis], limit)
    return new, True


def _move_horizontal(feet, dx, dz, width, height, block_height):
    feet, blocked_x = _move_axis(feet, 0, dx, width, height, block_height)
    feet, blocked_z = _move_axis(feet, 2, dz, width, height, block_height)
    return feet, blocked_x, blocked_z


def _substep(feet, vel, dt, width, height, block_height, step_height, on_ground, step_anywhere):
    dx, dy, dz = vel[0] * dt, vel[1] * dt, vel[2] * dt

    feet, blocked_y = _move_axis(feet, 1, dy, width, height, block_height)
    if blocked_y:
        if dy < 0:
            on_ground = True
        vel[1] = 0.0
    elif dy != 0:
        on_ground = False

    start = feet
    feet, blocked_x, blocked_z = _move_horizontal(feet, dx, dz, width, height, block_height)

    # auto step: climb obstacles lower than step_height while on the ground (or swimming)
    if (blocked_x or blocked_z) and (on_ground or step_anywhere) and step_height > 0:
        raised, _ = _move_axis(start, 1, step_height, width, height, block_height)
        stepped, s_bx, s_bz = _move_horizontal(raised, dx, dz, width, height, block_height)
        stepped, _ = _move_axis(stepped, 1, -(raised[1] - start[1]) - EPS, width, height, block_height)

        def progress(p):
            return (p[0] - start[0]) ** 2 + (p[2] - start[2]) ** 2

        if progress(stepped) > progress(feet) + 1e-12:
            feet, blocked_x, blocked_z = stepped, s_bx, s_bz

    if blocked_x:
        vel[0] = 0.0
    if blocked_z:
        vel[2] = 0.0
    return feet, on_ground


def step(feet, velocity, dt, block_height, width, height, step_height=0.0, on_ground=False,
         step_anywhere=False):
    """Advance the player box by ``dt`` seconds with collisions.

    Returns (feet, velocity, on_ground). Blocked velocity components are zeroed.
    ``step_anywhere`` allows the auto step without ground contact (swimming).
    """
    dt = min(max(dt, 0.0), MAX_DT)
    vel = list(velocity)
    feet = list(feet)

    distance = max(abs(v) for v in vel) * dt
    n = max(1, math.ceil(distance / MAX_SUBSTEP_MOVE))
    sub_dt = dt / n

    # "on ground" is re-evaluated: probe just below the feet
    on_ground = on_ground and collides((feet[0], feet[1] - 2 * EPS, feet[2]), width, height, block_height)
    for _ in range(n):
        feet, on_ground = _substep(feet, vel, sub_dt, width, height, block_height, step_height, on_ground,
                                   step_anywhere)
    return tuple(feet), tuple(vel), on_ground


def water_vertical_velocity(vy, dt, swim, gravity, drag, up_accel, down_accel):
    """Vertical speed in water: weak net gravity (buoyancy), linear drag, swimming.

    ``swim`` is +1 (swim up), -1 (dive) or 0. Terminal speeds are accel / drag,
    so sinking is slow and a fast fall is braked when entering the water.
    """
    dt = min(max(dt, 0.0), MAX_DT)
    accel = -gravity
    if swim > 0:
        accel += up_accel
    elif swim < 0:
        accel -= down_accel
    vy += accel * dt
    return vy * math.exp(-drag * dt)
