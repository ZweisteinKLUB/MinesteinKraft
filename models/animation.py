"""Skeletal animation: poses, clips baked at a fixed rate, cross-fades and blends.

Pure numpy (no OpenGL). Quaternions are (x, y, z, w). A pose is the local
translation / rotation / scale of every node of a model.
"""
from dataclasses import dataclass

import numpy as np

BAKE_FPS = 30.0


# ---------------------------------------------------------------------- quaternions
def quat_normalize(q):
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    return q / np.where(n == 0, 1, n)


def quat_mul(a, b):
    ax, ay, az, aw = np.moveaxis(np.asarray(a, dtype=np.float32), -1, 0)
    bx, by, bz, bw = np.moveaxis(np.asarray(b, dtype=np.float32), -1, 0)
    return np.stack([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], axis=-1)


def quat_from_axis_angle(axis, angle):
    axis = np.asarray(axis, dtype=np.float32)
    axis = axis / max(float(np.linalg.norm(axis)), 1e-12)
    s = np.sin(angle * 0.5)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, np.cos(angle * 0.5)], dtype=np.float32)


def quat_to_matrix(q):
    """(..., 4) quaternions -> (..., 3, 3) rotation matrices."""
    q = quat_normalize(np.asarray(q, dtype=np.float32))
    x, y, z, w = np.moveaxis(q, -1, 0)
    m = np.empty(q.shape[:-1] + (3, 3), dtype=np.float32)
    m[..., 0, 0] = 1 - 2 * (y * y + z * z)
    m[..., 0, 1] = 2 * (x * y - z * w)
    m[..., 0, 2] = 2 * (x * z + y * w)
    m[..., 1, 0] = 2 * (x * y + z * w)
    m[..., 1, 1] = 1 - 2 * (x * x + z * z)
    m[..., 1, 2] = 2 * (y * z - x * w)
    m[..., 2, 0] = 2 * (x * z - y * w)
    m[..., 2, 1] = 2 * (y * z + x * w)
    m[..., 2, 2] = 1 - 2 * (x * x + y * y)
    return m


def quat_from_matrix(m):
    m = np.asarray(m, dtype=np.float64)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2
        q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s]
    return quat_normalize(np.array(q, dtype=np.float32))


def nlerp(a, b, w):
    """Normalized lerp between quaternion arrays, along the shortest arc."""
    dot = np.sum(a * b, axis=-1, keepdims=True)
    b = np.where(dot < 0, -b, b)
    return quat_normalize(a + (b - a) * w)


def rotation_matrix(axis, angle):
    return quat_to_matrix(quat_from_axis_angle(axis, angle))


# ---------------------------------------------------------------------- poses
@dataclass
class Pose:
    t: np.ndarray  # (n, 3)
    r: np.ndarray  # (n, 4)
    s: np.ndarray  # (n, 3)

    def copy(self):
        return Pose(self.t.copy(), self.r.copy(), self.s.copy())


def blend_poses(a, b, w):
    """Pose between ``a`` (w = 0) and ``b`` (w = 1)."""
    if w <= 0:
        return a
    if w >= 1:
        return b
    return Pose(a.t + (b.t - a.t) * w, nlerp(a.r, b.r, w), a.s + (b.s - a.s) * w)


def blend_many(poses_weights):
    """Weighted average of several poses (weights need not sum to 1)."""
    result, total = None, 0.0
    for pose, w in poses_weights:
        if w <= 0:
            continue
        total += w
        result = pose if result is None else blend_poses(result, pose, w / total)
    return result


# ---------------------------------------------------------------------- skeleton
class Skeleton:
    def __init__(self, model):
        self.names = [n.name for n in model.nodes]
        self.parents = np.array([n.parent for n in model.nodes], dtype=np.int64)
        self.rest = Pose(np.array([n.translation for n in model.nodes], dtype=np.float32).reshape(-1, 3),
                         np.array([n.rotation for n in model.nodes], dtype=np.float32).reshape(-1, 4),
                         np.array([n.scale for n in model.nodes], dtype=np.float32).reshape(-1, 3))
        self.joints = np.array(model.joints, dtype=np.int64)
        self.inverse_bind = model.inverse_bind.astype(np.float32)
        self.order = self._topological_order()

    def __len__(self):
        return len(self.names)

    def index(self, name):
        return self.names.index(name)

    def _topological_order(self):
        order, seen = [], set()

        def visit(i):
            if i in seen:
                return
            if self.parents[i] >= 0:
                visit(int(self.parents[i]))
            seen.add(i)
            order.append(i)

        for i in range(len(self.names)):
            visit(i)
        return order

    @staticmethod
    def local_matrices(pose):
        n = len(pose.t)
        m = np.zeros((n, 4, 4), dtype=np.float32)
        m[:, :3, :3] = quat_to_matrix(pose.r) * pose.s[:, None, :]
        m[:, :3, 3] = pose.t
        m[:, 3, 3] = 1.0
        return m

    def world_matrices(self, pose, extra=None):
        """Model-space matrix of every node.

        ``extra`` maps a node index to a 3x3 rotation applied in model space
        around the node's origin (children follow): used to aim the head.
        """
        local = self.local_matrices(pose)
        world = np.empty_like(local)
        for i in self.order:
            p = self.parents[i]
            world[i] = local[i] if p < 0 else world[p] @ local[i]
            if extra and i in extra:
                rot = extra[i]
                world[i, :3, :3] = rot @ world[i, :3, :3]
        return world

    def skin_matrices(self, pose, extra=None):
        """(J, 4, 4) joint matrices for the vertex shader."""
        world = self.world_matrices(pose, extra)
        return world[self.joints] @ self.inverse_bind


# ---------------------------------------------------------------------- clips
class Clip:
    """An animation baked at BAKE_FPS for every node (nodes without channel keep the rest pose)."""

    def __init__(self, name, animation, skeleton, fps=BAKE_FPS):
        self.name = name
        self.duration = max(animation.duration, 1.0 / fps)
        frames = max(2, int(round(self.duration * fps)) + 1)
        times = np.linspace(0.0, self.duration, frames, dtype=np.float32)
        rest = skeleton.rest
        self.t = np.repeat(rest.t[None], frames, axis=0)
        self.r = np.repeat(rest.r[None], frames, axis=0)
        self.s = np.repeat(rest.s[None], frames, axis=0)
        for ch in animation.channels:
            values = sample_channel(ch.times, ch.values, times, ch.path == 'rotation', ch.step)
            getattr(self, {'translation': 't', 'rotation': 'r', 'scale': 's'}[ch.path])[:, ch.node] = values
        self.frames = frames

    def sample(self, time, loop=True):
        """Pose at ``time`` seconds (wrapped when looping, clamped otherwise)."""
        if loop:
            time = time % self.duration
        f = float(np.clip(time / self.duration, 0.0, 1.0)) * (self.frames - 1)
        i = min(int(f), self.frames - 2)
        w = f - i
        return Pose(self.t[i] + (self.t[i + 1] - self.t[i]) * w,
                    nlerp(self.r[i], self.r[i + 1], w),
                    self.s[i] + (self.s[i + 1] - self.s[i]) * w)


def sample_channel(times, values, at, is_rotation=False, step=False):
    """Values of a keyframed channel at the times ``at`` (clamped outside the keys)."""
    if len(times) == 1:
        return np.repeat(values[:1], len(at), axis=0)
    idx = np.clip(np.searchsorted(times, at, side='right') - 1, 0, len(times) - 2)
    t0, t1 = times[idx], times[idx + 1]
    w = np.clip((at - t0) / np.where(t1 > t0, t1 - t0, 1), 0.0, 1.0)[:, None]
    if step:
        w = (w >= 1.0).astype(np.float32)
    a, b = values[idx], values[idx + 1]
    if is_rotation:
        return nlerp(a, b, w)
    return a + (b - a) * w


def load_clips(model, skeleton):
    return {name: Clip(name, anim, skeleton) for name, anim in model.animations.items()}


# ---------------------------------------------------------------------- animator
class Track:
    """One or more clips played with a shared normalized phase (walk / run stay in step)."""

    def __init__(self, key, weights, rate=1.0, loop=True, phase=0.0):
        self.key = key
        self.weights = dict(weights)
        self.rate = rate
        self.loop = loop
        self.phase = phase

    def cycle_duration(self, clips):
        total = sum(self.weights.values())
        if total <= 0:
            return 1.0
        return sum(clips[n].duration * w for n, w in self.weights.items()) / total

    def advance(self, dt, clips):
        self.phase += dt * self.rate / self.cycle_duration(clips)
        if self.loop:
            self.phase %= 1.0
        else:
            self.phase = min(self.phase, 1.0)

    def pose(self, clips):
        return blend_many([(clips[n].sample(self.phase * clips[n].duration, self.loop), w)
                           for n, w in self.weights.items()])


class Animator:
    """Base state with cross-fades, plus one-shot clips played over it."""

    def __init__(self, skeleton, clips, fade=0.2):
        self.skeleton = skeleton
        self.clips = clips
        self.fade = fade
        self.current = None
        self.previous = None
        self.fade_t = 1.0
        self.fade_duration = fade
        self.oneshot = None       # (Track, fade)

    def has(self, name):
        return name in self.clips

    def set_blend(self, key, weights, rate=1.0, loop=True, fade=None):
        """Play the clips ``weights`` together; a new ``key`` cross-fades from the old state."""
        weights = {n: w for n, w in weights.items() if n in self.clips}
        if not weights:
            return
        if self.current is not None and self.current.key == key:
            self.current.weights = weights
            self.current.rate = rate
            return
        self.previous = self.current
        self.current = Track(key, weights, rate, loop)
        self.fade_duration = self.fade if fade is None else fade
        self.fade_t = 0.0 if self.previous is not None else 1.0

    def set_state(self, name, rate=1.0, loop=True, fade=None):
        self.set_blend(name, {name: 1.0}, rate, loop, fade)

    def play_once(self, name, rate=1.0, fade=0.12):
        if name in self.clips:
            self.oneshot = (Track(name, {name: 1.0}, rate, loop=False), fade)

    @property
    def oneshot_playing(self):
        return self.oneshot is not None

    @property
    def oneshot_phase(self):
        return self.oneshot[0].phase if self.oneshot else None

    @property
    def state(self):
        return self.current.key if self.current else None

    def update(self, dt):
        if self.current is not None:
            self.current.advance(dt, self.clips)
        if self.previous is not None:
            self.previous.advance(dt, self.clips)
            self.fade_t += dt / max(self.fade_duration, 1e-6)
            if self.fade_t >= 1.0:
                self.previous = None
        if self.oneshot is not None:
            track, _ = self.oneshot
            track.advance(dt, self.clips)
            if track.phase >= 1.0:
                self.oneshot = None

    def pose(self):
        if self.current is None:
            pose = self.skeleton.rest
        else:
            pose = self.current.pose(self.clips)
            if self.previous is not None:
                pose = blend_poses(self.previous.pose(self.clips), pose, smoothstep(self.fade_t))
        if self.oneshot is not None:
            track, fade = self.oneshot
            duration = self.clips[track.key].duration / max(track.rate, 1e-6)
            elapsed = track.phase * duration
            w = min(1.0, elapsed / fade, (duration - elapsed) / fade) if fade > 0 else 1.0
            pose = blend_poses(pose, track.pose(self.clips), max(0.0, w))
        return pose

    def skin_matrices(self, extra=None):
        return self.skeleton.skin_matrices(self.pose(), extra)


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)
