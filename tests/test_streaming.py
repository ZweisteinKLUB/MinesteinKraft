from world import columns_by_distance


def test_columns_nearest_first_and_within_radius():
    cols = columns_by_distance(10, -4, 3)
    assert cols[0] == (10, -4)
    d2 = [(x - 10) ** 2 + (z + 4) ** 2 for x, z in cols]
    assert d2 == sorted(d2) and max(d2) <= 9
    assert len(cols) == len(set(cols)) == 29  # disc of radius 3
