import numpy as np
from noise import noise2, noise3, make_permutation


def test_noise_range_and_determinism():
    rng = np.random.default_rng(0)
    x, y, z = rng.uniform(-1000, 1000, (3, 20000))
    a = noise2(x, y)
    b = noise3(x, y, z)
    assert np.all(np.abs(a) <= 1.0) and np.all(np.abs(b) <= 1.0)
    assert np.array_equal(a, noise2(x, y))
    assert np.array_equal(b, noise3(x, y, z))
    # roughly centered, both signs present
    assert abs(a.mean()) < 0.05 and abs(b.mean()) < 0.05


def test_noise_is_continuous():
    t = np.linspace(0, 20, 200001)
    assert np.abs(np.diff(noise2(t, 0.37))).max() < 0.01
    assert np.abs(np.diff(noise3(t, 0.37, 1.7))).max() < 0.01


def test_scalar_input():
    assert np.ndim(noise2(1.5, 2.5)) == 0
    assert np.ndim(noise3(1.5, 2.5, 3.5)) == 0


def test_permutation_depends_on_seed():
    assert not np.array_equal(make_permutation(1), make_permutation(2))
    assert np.array_equal(make_permutation(7), make_permutation(7))
