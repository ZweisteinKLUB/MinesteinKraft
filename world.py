import time
from settings import *
from world_objects.chunk import Chunk, generate_chunk_voxels
from voxel_handler import VoxelHandler

WORLD_SIZE_Y = WORLD_H * CHUNK_SIZE      # fixed world height (blocks)
BASE_SIZE_X = WORLD_W * CHUNK_SIZE       # size of the initial area (blocks)
BASE_SIZE_Z = WORLD_D * CHUNK_SIZE

HORIZONTAL_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def chunk_key(wx, wy, wz):
    """Key of the chunk containing integer world coordinates (floor division)."""
    return wx // CHUNK_SIZE, wy // CHUNK_SIZE, wz // CHUNK_SIZE


def block_height_in(get_voxels, wx, wy, wz):
    """Collision height (0..1) of the block at integer world coordinates.

    ``get_voxels(key)`` returns a chunk voxel array or None when the chunk is not
    loaded: it is then solid (a wall until it is generated). Below y = 0 is solid
    bedrock, above the world height is open sky.
    """
    if wy < 0:
        return 1.0
    if wy >= WORLD_SIZE_Y:
        return 0.0
    cx, cy, cz = chunk_key(wx, wy, wz)
    voxels = get_voxels((cx, cy, cz))
    if voxels is None:
        return 1.0
    lx, ly, lz = wx - cx * CHUNK_SIZE, wy - cy * CHUNK_SIZE, wz - cz * CHUNK_SIZE
    return 1.0 if voxels[lx + CHUNK_SIZE * lz + CHUNK_AREA * ly] else 0.0  # full cubes for now


def surface_height_in(get_voxels, wx, wz):
    """Y just above the highest non-empty block of a loaded column (0 if none)."""
    for cy in range(WORLD_H - 1, -1, -1):
        voxels = get_voxels((wx // CHUNK_SIZE, cy, wz // CHUNK_SIZE))
        if voxels is None:
            continue
        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE
        column = voxels.reshape(CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)[:, lz, lx]
        filled = np.nonzero(column)[0]
        if filled.size:
            return cy * CHUNK_SIZE + int(filled[-1]) + 1
    return 0


def voxel_at_in(get_voxels, wx, wy, wz):
    """Block id at integer world coordinates (0 above / below the world), None if not loaded."""
    if wy < 0 or wy >= WORLD_SIZE_Y:
        return 0
    cx, cy, cz = chunk_key(wx, wy, wz)
    voxels = get_voxels((cx, cy, cz))
    if voxels is None:
        return None
    lx, ly, lz = wx - cx * CHUNK_SIZE, wy - cy * CHUNK_SIZE, wz - cz * CHUNK_SIZE
    return int(voxels[lx + CHUNK_SIZE * lz + CHUNK_AREA * ly])


def columns_by_distance(center_cx, center_cz, radius):
    """Chunk columns (cx, cz) within ``radius`` of the center, nearest first."""
    r = np.arange(-radius, radius + 1)
    dx, dz = np.meshgrid(r, r)
    d2 = dx * dx + dz * dz
    inside = d2 <= radius * radius
    order = np.argsort(d2[inside], kind='stable')
    return [(center_cx + int(x), center_cz + int(z)) for x, z in zip(dx[inside][order], dz[inside][order])]


class World:
    """Chunks loaded around the player, read from the world database or generated on demand."""

    def __init__(self, app, store):
        self.app = app
        self.store = store
        self.chunks: dict[tuple, Chunk] = {}
        self.dirty = set()         # chunk keys to write to the database
        self.to_mesh = set()       # chunk keys whose mesh must be (re)built
        self.wanted = []           # columns to load, nearest first
        self.center = None         # player column the wanted list was computed for
        self.last_save = time.perf_counter()
        self.voxel_handler = VoxelHandler(self)

    # ------------------------------------------------------------------ queries
    def get_chunk(self, key):
        return self.chunks.get(key)

    def get_voxels(self, key):
        chunk = self.chunks.get(key)
        return None if chunk is None else chunk.voxels

    def block_height(self, wx, wy, wz):
        return block_height_in(self.get_voxels, wx, wy, wz)

    def surface_height(self, wx, wz):
        return surface_height_in(self.get_voxels, wx, wz)

    def voxel_at(self, wx, wy, wz):
        """Block id at integer world coordinates, None when its chunk is not loaded."""
        return voxel_at_in(self.get_voxels, wx, wy, wz)

    # ------------------------------------------------------------------ loading
    def load_column(self, cx, cz):
        """Load (or generate and queue for saving) every chunk of a column."""
        for cy in range(WORLD_H):
            key = (cx, cy, cz)
            if key in self.chunks:
                continue
            voxels = self.store.load_chunk(key)
            if voxels is None:
                voxels = generate_chunk_voxels(key)
                self.dirty.add(key)  # new chunk: remembered in the database
            self.chunks[key] = Chunk(self, key, voxels)
            # this chunk and its neighbours (their borders were solid until now) need a mesh
            self.to_mesh.add(key)
            for dx, dz in HORIZONTAL_NEIGHBOURS:
                if (cx + dx, cy, cz + dz) in self.chunks:
                    self.to_mesh.add((cx + dx, cy, cz + dz))
            for dy in (-1, 1):
                if (cx, cy + dy, cz) in self.chunks:
                    self.to_mesh.add((cx, cy + dy, cz))

    def column_loaded(self, cx, cz):
        return (cx, 0, cz) in self.chunks

    def ready_to_mesh(self, key):
        """Mesh once the horizontal neighbours are loaded, or lie outside the loaded area."""
        cx, cy, cz = key
        pcx, pcz = self.center
        for dx, dz in HORIZONTAL_NEIGHBOURS:
            nx, nz = cx + dx, cz + dz
            inside = (nx - pcx) ** 2 + (nz - pcz) ** 2 <= RENDER_DISTANCE ** 2
            if inside and not self.column_loaded(nx, nz):
                return False
        return True

    def load_area(self, center_x, center_z, radius):
        """Synchronously load and mesh every column within ``radius`` chunks (start, teleport)."""
        cx, cz = int(center_x) // CHUNK_SIZE, int(center_z) // CHUNK_SIZE
        for col in columns_by_distance(cx, cz, radius):
            self.load_column(*col)
        self.center = (cx, cz)
        for key in list(self.to_mesh):
            if key in self.chunks:
                self.chunks[key].build_mesh()
        self.to_mesh.clear()

    def generate_base_area(self, progress=None):
        """New world: generate the starting island area at once and save it."""
        columns = [(x, z) for x in range(WORLD_W) for z in range(WORLD_D)]
        for i, col in enumerate(columns):
            self.load_column(*col)
            if progress:
                progress((i + 1) / len(columns))
        self.save()

    # ------------------------------------------------------------------ streaming
    def stream(self, budget_ms=CHUNK_BUDGET_MS):
        """Load / generate / mesh / unload chunks around the player within a time budget."""
        deadline = time.perf_counter() + budget_ms / 1000
        pos = self.app.player.position
        center = (int(math.floor(pos.x)) // CHUNK_SIZE, int(math.floor(pos.z)) // CHUNK_SIZE)
        if center != self.center or not self.wanted:
            self.center = center
            self.wanted = columns_by_distance(*center, RENDER_DISTANCE)
            self.unload_far()
            # chunks at the old edge may now have all their neighbours
            self.to_mesh.update(k for k, c in self.chunks.items() if c.mesh is None)

        # nearest missing columns first
        for col in self.wanted:
            if time.perf_counter() > deadline:
                break
            if not self.column_loaded(*col):
                self.load_column(*col)

        # meshes, nearest first
        if self.to_mesh:
            pcx, pcz = self.center
            for key in sorted(self.to_mesh, key=lambda k: (k[0] - pcx) ** 2 + (k[2] - pcz) ** 2):
                if time.perf_counter() > deadline:
                    break
                chunk = self.chunks.get(key)
                if chunk is None:
                    self.to_mesh.discard(key)
                elif self.ready_to_mesh(key):
                    chunk.build_mesh()
                    self.to_mesh.discard(key)

    def unload_far(self):
        pcx, pcz = self.center
        limit = (RENDER_DISTANCE + UNLOAD_MARGIN) ** 2
        far = [k for k in self.chunks if (k[0] - pcx) ** 2 + (k[2] - pcz) ** 2 > limit]
        if not far:
            return
        self.store.save_chunks({k: self.chunks[k].voxels for k in far if k in self.dirty})
        for key in far:
            self.dirty.discard(key)
            self.to_mesh.discard(key)
            self.chunks.pop(key).release()

    # ------------------------------------------------------------------ edits / saving
    def on_chunk_modified(self, chunk):
        chunk.is_empty = not np.any(chunk.voxels)
        self.dirty.add(chunk.position)
        if chunk.mesh is not None or self.ready_to_mesh(chunk.position):
            chunk.build_mesh()

    def save(self):
        """Write new / modified chunks and the player state to the database."""
        self.store.save_chunks({k: self.chunks[k].voxels for k in self.dirty if k in self.chunks})
        self.dirty.clear()
        p = self.app.player
        self.store.save_player(p.feet.x, p.feet.y, p.feet.z, p.yaw, p.pitch, p.fly)
        self.last_save = time.perf_counter()

    def update(self):
        self.voxel_handler.update()
        self.stream()
        if time.perf_counter() - self.last_save > AUTOSAVE_INTERVAL:
            self.save()

    def render(self):
        for chunk in self.chunks.values():
            chunk.render()

    def release(self):
        for chunk in self.chunks.values():
            chunk.release()
        self.chunks.clear()
