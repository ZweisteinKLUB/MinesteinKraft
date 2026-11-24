import os
import sqlite3
import numpy as np
import pytest
from settings import CHUNK_VOL
from storage import WorldStore, WorldFormatError, list_worlds, slugify, FORMAT_VERSION
import paths


def random_chunk(seed):
    return np.random.default_rng(seed).integers(0, 8, CHUNK_VOL, dtype=np.uint8)


def test_create_and_reopen(tmp_path):
    store = WorldStore.create(tmp_path, 'Mon Monde', seed=123456789012, generator_version=1)
    a, b = random_chunk(1), random_chunk(2)
    store.save_chunks({(0, 0, 0): a, (-5, 1, 7): b})
    store.save_player(1.5, 20.0, -3.25, 0.5, -0.2, True)
    path = store.path
    store.close()

    store = WorldStore.open(path)
    assert store.name == 'Mon Monde' and store.seed == 123456789012 and store.generator_version == 1
    assert np.array_equal(store.load_chunk((0, 0, 0)), a)
    assert np.array_equal(store.load_chunk((-5, 1, 7)), b)
    assert store.load_chunk((1, 0, 0)) is None
    assert store.load_player() == dict(x=1.5, y=20.0, z=-3.25, yaw=0.5, pitch=-0.2, fly=True)
    assert store.chunk_count() == 2
    store.close()


def test_chunk_overwrite_and_writable_copy(tmp_path):
    store = WorldStore.create(tmp_path, 'w', 1, 1)
    store.save_chunks({(0, 0, 0): np.zeros(CHUNK_VOL, np.uint8)})
    loaded = store.load_chunk((0, 0, 0))
    loaded[5] = 3  # must be writable (game edits voxels in place)
    store.save_chunks({(0, 0, 0): loaded})
    assert store.load_chunk((0, 0, 0))[5] == 3 and store.chunk_count() == 1
    store.compact()
    store.close()


def test_unique_file_names(tmp_path):
    s1 = WorldStore.create(tmp_path, 'Île été', 1, 1)
    s2 = WorldStore.create(tmp_path, 'Île été', 2, 1)
    assert (s1.path.name, s2.path.name) == ('ile-ete.db', 'ile-ete-2.db')
    assert s2.name == 'Île été'  # display name kept as typed
    s1.close(); s2.close()
    assert slugify('***') == 'world'


def test_list_worlds_sorted_and_reports_bad_files(tmp_path):
    a = WorldStore.create(tmp_path, 'A', 1, 1)
    b = WorldStore.create(tmp_path, 'B', 2, 1)
    a.set_meta('last_played', 100.0)
    b.set_meta('last_played', 200.0)
    a.close(); b.close()
    (tmp_path / 'broken.db').write_bytes(b'not a database at all')
    infos = list_worlds(tmp_path)
    assert [w.name for w in infos if not w.error] == ['B', 'A']
    broken = [w for w in infos if w.error]
    assert len(broken) == 1 and broken[0].path.read_bytes() == b'not a database at all'  # untouched


def test_unknown_format_version_is_refused(tmp_path):
    store = WorldStore.create(tmp_path, 'future', 1, 1)
    store.set_meta('format_version', FORMAT_VERSION + 1)
    store.close()
    with pytest.raises(WorldFormatError):
        WorldStore.open(tmp_path / 'future.db')


def test_open_missing_file_does_not_create_it(tmp_path):
    with pytest.raises(WorldFormatError):
        WorldStore.open(tmp_path / 'nope.db')
    assert not (tmp_path / 'nope.db').exists()


def test_user_data_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv('MINESTEINKRAFT_DATA_DIR', str(tmp_path))
    assert paths.user_data_dir() == tmp_path
    assert paths.worlds_dir() == tmp_path / 'worlds'
    monkeypatch.delenv('MINESTEINKRAFT_DATA_DIR')
    assert paths.user_data_dir().is_absolute()
