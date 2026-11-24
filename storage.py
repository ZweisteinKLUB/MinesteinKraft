"""World persistence in SQLite: one database file per world.

All storage goes through WorldStore, so the backend can be replaced later
(e.g. by region files) without touching the game code.

Schema:
  meta(key TEXT PRIMARY KEY, value TEXT)    format_version, generator_version, seed, name, ...
  chunks(cx, cy, cz, data BLOB)              zlib-compressed uint8 voxels
  player(id = 1, x, y, z, yaw, pitch, fly)
"""
import re
import sqlite3
import time
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FORMAT_VERSION = 1
CHUNK_DTYPE = np.uint8


class WorldFormatError(Exception):
    """The file is not a world database or comes from an unknown format version."""


@dataclass
class WorldInfo:
    path: Path
    name: str
    seed: int = 0
    created_at: float = 0.0
    last_played: float = 0.0
    chunk_count: int = 0
    error: str = ''  # set when the file cannot be opened (never deleted automatically)


def slugify(name):
    """File-name-safe version of a world name (accents transliterated: 'Île été' -> 'ile-ete')."""
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-')
    return slug or 'world'


class WorldStore:
    def __init__(self, path, connection):
        self.path = Path(path)
        self.db = connection

    # ------------------------------------------------------------------ create / open
    @staticmethod
    def _connect(path, create):
        uri = f'file:{Path(path).as_posix()}?mode={"rwc" if create else "rw"}'
        db = sqlite3.connect(uri, uri=True)
        db.execute('PRAGMA journal_mode=WAL')     # crash-safe, readers never block
        db.execute('PRAGMA synchronous=NORMAL')   # durable at checkpoints, fast commits
        return db

    @classmethod
    def create(cls, worlds_dir, name, seed, generator_version):
        worlds_dir = Path(worlds_dir)
        worlds_dir.mkdir(parents=True, exist_ok=True)
        base = slugify(name)
        path = worlds_dir / f'{base}.db'
        n = 2
        while path.exists():
            path = worlds_dir / f'{base}-{n}.db'
            n += 1
        db = cls._connect(path, create=True)
        with db:
            db.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('CREATE TABLE chunks (cx INTEGER, cy INTEGER, cz INTEGER, data BLOB NOT NULL,'
                       ' PRIMARY KEY (cx, cy, cz)) WITHOUT ROWID')
            db.execute('CREATE TABLE player (id INTEGER PRIMARY KEY CHECK (id = 1),'
                       ' x REAL, y REAL, z REAL, yaw REAL, pitch REAL, fly INTEGER)')
            now = time.time()
            db.executemany('INSERT INTO meta VALUES (?, ?)', [
                ('format_version', str(FORMAT_VERSION)),
                ('generator_version', str(generator_version)),
                ('seed', str(int(seed))),
                ('name', name),
                ('created_at', repr(now)),
                ('last_played', repr(now)),
            ])
        return cls(path, db)

    @classmethod
    def open(cls, path):
        path = Path(path)
        if not path.is_file():
            raise WorldFormatError(f'{path} does not exist')
        try:
            db = cls._connect(path, create=False)
            rows = dict(db.execute('SELECT key, value FROM meta'))
        except sqlite3.DatabaseError as error:
            raise WorldFormatError(f'{path.name}: not a world database ({error})') from None
        version = int(rows.get('format_version', -1))
        if version != FORMAT_VERSION:
            db.close()
            raise WorldFormatError(f'{path.name}: unsupported format version {version}')
        return cls(path, db)

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None

    # ------------------------------------------------------------------ meta
    def get_meta(self, key, default=None):
        row = self.db.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
        return default if row is None else row[0]

    def set_meta(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', (key, str(value)))

    @property
    def name(self):
        return self.get_meta('name', self.path.stem)

    @property
    def seed(self):
        return int(self.get_meta('seed'))

    @property
    def generator_version(self):
        return int(self.get_meta('generator_version', 1))

    def touch(self):
        self.set_meta('last_played', repr(time.time()))

    # ------------------------------------------------------------------ chunks
    def load_chunk(self, key):
        row = self.db.execute('SELECT data FROM chunks WHERE cx = ? AND cy = ? AND cz = ?', key).fetchone()
        if row is None:
            return None
        return np.frombuffer(zlib.decompress(row[0]), dtype=CHUNK_DTYPE).copy()

    def save_chunks(self, chunks):
        """Write {key: voxels} in one transaction."""
        if not chunks:
            return
        rows = [(*key, zlib.compress(np.ascontiguousarray(voxels, dtype=CHUNK_DTYPE).tobytes(), 6))
                for key, voxels in chunks.items()]
        with self.db:
            self.db.executemany('INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?)', rows)

    def chunk_count(self):
        return self.db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]

    # ------------------------------------------------------------------ player
    def load_player(self):
        row = self.db.execute('SELECT x, y, z, yaw, pitch, fly FROM player WHERE id = 1').fetchone()
        if row is None:
            return None
        x, y, z, yaw, pitch, fly = row
        return dict(x=x, y=y, z=z, yaw=yaw, pitch=pitch, fly=bool(fly))

    def save_player(self, x, y, z, yaw, pitch, fly):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO player VALUES (1, ?, ?, ?, ?, ?, ?)',
                            (x, y, z, yaw, pitch, int(fly)))

    # ------------------------------------------------------------------ maintenance
    def compact(self):
        """Give back the space of rewritten chunks to the file system (VACUUM)."""
        self.db.execute('VACUUM')


def list_worlds(worlds_dir):
    """Worlds found in a folder, most recently played first; unreadable files are reported."""
    worlds_dir = Path(worlds_dir)
    infos = []
    if not worlds_dir.is_dir():
        return infos
    for path in sorted(worlds_dir.glob('*.db')):
        try:
            store = WorldStore.open(path)
        except WorldFormatError as error:
            infos.append(WorldInfo(path=path, name=path.stem, error=str(error)))
            continue
        try:
            infos.append(WorldInfo(
                path=path, name=store.name, seed=store.seed,
                created_at=float(store.get_meta('created_at', 0)),
                last_played=float(store.get_meta('last_played', 0)),
                chunk_count=store.chunk_count(),
            ))
        finally:
            store.close()
    infos.sort(key=lambda w: w.last_played, reverse=True)
    return infos
