"""Vectorized simplex noise (2D / 3D) in pure NumPy.

Based on Stefan Gustavson's reference simplex noise. Every function accepts
scalars or arrays (broadcast together) and returns values roughly in [-1, 1].
The permutation table is derived from ``SEED`` so the world is reproducible.
"""
import numpy as np
from settings import SEED

_GRAD3 = np.array([
    (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
    (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
    (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1),
], dtype=np.float64)

_F2 = 0.5 * (np.sqrt(3.0) - 1.0)
_G2 = (3.0 - np.sqrt(3.0)) / 6.0
_F3 = 1.0 / 3.0
_G3 = 1.0 / 6.0


def make_permutation(seed):
    p = np.random.default_rng(seed).permutation(256).astype(np.int64)
    return np.concatenate([p, p])


_PERM = make_permutation(SEED)
_PERM_MOD12 = _PERM % 12


def _corner(t, gi, *offsets):
    """Contribution of one simplex corner."""
    g = _GRAD3[gi]
    dot = sum(g[..., k] * off for k, off in enumerate(offsets))
    t = np.maximum(t, 0.0)
    t2 = t * t
    return t2 * t2 * dot


def noise2(x, y, perm=_PERM, perm12=_PERM_MOD12):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    s = (x + y) * _F2
    i = np.floor(x + s)
    j = np.floor(y + s)
    t = (i + j) * _G2
    x0 = x - (i - t)
    y0 = y - (j - t)

    i1 = (x0 > y0).astype(np.int64)
    j1 = 1 - i1

    x1 = x0 - i1 + _G2
    y1 = y0 - j1 + _G2
    x2 = x0 - 1.0 + 2.0 * _G2
    y2 = y0 - 1.0 + 2.0 * _G2

    ii = i.astype(np.int64) & 255
    jj = j.astype(np.int64) & 255
    gi0 = perm12[ii + perm[jj]]
    gi1 = perm12[ii + i1 + perm[jj + j1]]
    gi2 = perm12[ii + 1 + perm[jj + 1]]

    n0 = _corner(0.5 - x0 * x0 - y0 * y0, gi0, x0, y0)
    n1 = _corner(0.5 - x1 * x1 - y1 * y1, gi1, x1, y1)
    n2 = _corner(0.5 - x2 * x2 - y2 * y2, gi2, x2, y2)
    return 70.0 * (n0 + n1 + n2)


def noise3(x, y, z, perm=_PERM, perm12=_PERM_MOD12):
    x, y, z = np.broadcast_arrays(
        np.asarray(x, dtype=np.float64),
        np.asarray(y, dtype=np.float64),
        np.asarray(z, dtype=np.float64),
    )

    s = (x + y + z) * _F3
    i = np.floor(x + s)
    j = np.floor(y + s)
    k = np.floor(z + s)
    t = (i + j + k) * _G3
    x0 = x - (i - t)
    y0 = y - (j - t)
    z0 = z - (k - t)

    # rank the coordinates to find which simplex we are in
    xy = x0 >= y0
    yz = y0 >= z0
    xz = x0 >= z0
    i1 = (xy & xz).astype(np.int64)
    j1 = (~xy & yz).astype(np.int64)
    k1 = (~xz & ~yz).astype(np.int64)
    i2 = (xy | xz).astype(np.int64)
    j2 = (~xy | yz).astype(np.int64)
    k2 = (~(xz & yz)).astype(np.int64)

    x1 = x0 - i1 + _G3
    y1 = y0 - j1 + _G3
    z1 = z0 - k1 + _G3
    x2 = x0 - i2 + 2.0 * _G3
    y2 = y0 - j2 + 2.0 * _G3
    z2 = z0 - k2 + 2.0 * _G3
    x3 = x0 - 1.0 + 3.0 * _G3
    y3 = y0 - 1.0 + 3.0 * _G3
    z3 = z0 - 1.0 + 3.0 * _G3

    ii = i.astype(np.int64) & 255
    jj = j.astype(np.int64) & 255
    kk = k.astype(np.int64) & 255
    gi0 = perm12[ii + perm[jj + perm[kk]]]
    gi1 = perm12[ii + i1 + perm[jj + j1 + perm[kk + k1]]]
    gi2 = perm12[ii + i2 + perm[jj + j2 + perm[kk + k2]]]
    gi3 = perm12[ii + 1 + perm[jj + 1 + perm[kk + 1]]]

    n0 = _corner(0.6 - x0 * x0 - y0 * y0 - z0 * z0, gi0, x0, y0, z0)
    n1 = _corner(0.6 - x1 * x1 - y1 * y1 - z1 * z1, gi1, x1, y1, z1)
    n2 = _corner(0.6 - x2 * x2 - y2 * y2 - z2 * z2, gi2, x2, y2, z2)
    n3 = _corner(0.6 - x3 * x3 - y3 * y3 - z3 * z3, gi3, x3, y3, z3)
    return 32.0 * (n0 + n1 + n2 + n3)
