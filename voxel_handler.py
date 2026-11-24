from settings import *
from meshes.chunk_mesh_builder import get_chunk_key
from block_breaking import BlockBreaker


class VoxelHandler:
    def __init__(self, world):
        self.app = world.app
        self.world = world
        
        # ray casting result
        self.chunk = None
        self.voxel_id = None
        self.voxel_index = None
        self.voxel_local_pos = None
        self.voxel_world_pos = None
        self.voxel_normal = None
        
        self.interaction_mode = 0 # 0: remove voxel   1: add voxel
        self.new_voxel_id = 1

        # progressive breaking while the left button is held
        self.breaker = BlockBreaker()
        self.breaking = False
        
    def add_voxel(self):
        if self.voxel_id:
            # check voxel id along normal
            new_pos = self.voxel_world_pos + self.voxel_normal
            voxel_id, voxel_index, voxel_local_pos, chunk = self.get_voxel_id(new_pos)

            # is the new place inside the world, empty, and not inside the player?
            if chunk is not None and not voxel_id and not self.app.player.intersects_block(*new_pos):
                chunk.voxels[voxel_index] = self.new_voxel_id
                self.world.on_chunk_modified(chunk)
                self.rebuild_adjacent_chunks(voxel_local_pos, new_pos)

    def rebuild_adj_chunk(self, adj_voxel_pos):
        chunk = self.world.get_chunk(get_chunk_key(adj_voxel_pos))
        if chunk is not None and chunk.mesh is not None:
            chunk.build_mesh()
    
    def rebuild_adjacent_chunks(self, voxel_local_pos, voxel_world_pos):
        lx, ly, lz = voxel_local_pos
        wx, wy, wz = voxel_world_pos
        
        if lx == 0:
            self.rebuild_adj_chunk((wx - 1, wy, wz))
        elif lx == CHUNK_SIZE - 1:
            self.rebuild_adj_chunk((wx + 1, wy, wz))
        
        if ly == 0:
            self.rebuild_adj_chunk((wx, wy - 1, wz))
        elif ly == CHUNK_SIZE - 1:
            self.rebuild_adj_chunk((wx, wy + 1, wz))
    
        if lz == 0:
            self.rebuild_adj_chunk((wx, wy, wz - 1))
        elif lz == CHUNK_SIZE - 1:
            self.rebuild_adj_chunk((wx, wy, wz + 1))

    def remove_voxel(self):
        if self.voxel_id:
            self.chunk.voxels[self.voxel_index] = 0
            self.world.on_chunk_modified(self.chunk)
            self.rebuild_adjacent_chunks(self.voxel_local_pos, self.voxel_world_pos)
              
    def set_voxel(self):
        if self.interaction_mode:
            self.add_voxel()
        else:
            self.remove_voxel()
    
    def switch_mode(self):
        self.interaction_mode = not self.interaction_mode
    
    def update(self):
        self.ray_cast()
        target = self.voxel_world_pos if self.voxel_id else None
        holding = self.breaking and not self.interaction_mode
        if self.breaker.update(target, self.voxel_id, holding, self.app.delta_time * 0.001):
            self.remove_voxel()
    
    def ray_cast(self):
        # start point
        x1, y1, z1 = self.app.player.position
        # end point, along the view direction
        x2, y2, z2 = self.app.player.position + self.app.player.look * MAX_RAY_DIST
        
        current_voxel_pos = glm.ivec3(glm.floor(self.app.player.position))
        self.voxel_id = 0
        self.voxel_normal = glm.ivec3(0)
        step_dir = -1
        
        dx = glm.sign(x2 - x1)
        delta_x = min(dx / (x2 - x1), 10000000.0) if dx != 0 else 10000000.0
        max_x = delta_x * (1.0 - glm.fract(x1)) if dx > 0 else delta_x * glm.fract(x1)
        
        dy = glm.sign(y2 - y1)
        delta_y = min(dy / (y2 - y1), 10000000.0) if dy != 0 else 10000000.0
        max_y = delta_y * (1.0 - glm.fract(y1)) if dy > 0 else delta_y * glm.fract(y1)
        
        dz = glm.sign(z2 - z1)
        delta_z = min(dz / (z2 - z1), 10000000.0) if dz != 0 else 10000000.0
        max_z = delta_z * (1.0 - glm.fract(z1)) if dz > 0 else delta_z * glm.fract(z1)
        
        while not (max_x > 1.0 and max_y > 1.0 and max_z > 1.0):
            
            result = self.get_voxel_id(voxel_world_pos=current_voxel_pos)
            if result[0]:
                self.voxel_id, self.voxel_index, self.voxel_local_pos, self.chunk = result
                self.voxel_world_pos = current_voxel_pos
                
                if step_dir == 0:
                    self.voxel_normal.x = -dx
                elif step_dir == 1:
                    self.voxel_normal.y = -dy
                else:
                    self.voxel_normal.z = -dz
                return True
            
            if max_x < max_y:
                if max_x < max_z:
                    current_voxel_pos.x += dx
                    max_x += delta_x
                    step_dir = 0
                else:
                    current_voxel_pos.z += dz
                    max_z += delta_z
                    step_dir = 2
            else:        
                if max_y < max_z:
                    current_voxel_pos.y += dy
                    max_y += delta_y
                    step_dir = 1
                else:
                    current_voxel_pos.z += dz
                    max_z += delta_z
                    step_dir = 2
        return False
    
    def get_voxel_id(self, voxel_world_pos):
        """Return (voxel_id, voxel_index, voxel_local_pos, chunk); chunk is None if not loaded."""
        wx, wy, wz = (int(v) for v in voxel_world_pos)
        # floor division, also correct for negative coordinates
        cx, cy, cz = wx // CHUNK_SIZE, wy // CHUNK_SIZE, wz // CHUNK_SIZE

        chunk = self.world.get_chunk((cx, cy, cz)) if 0 <= cy < WORLD_H else None
        if chunk is not None:
            lx, ly, lz = wx - cx * CHUNK_SIZE, wy - cy * CHUNK_SIZE, wz - cz * CHUNK_SIZE
            voxel_index = lx + CHUNK_SIZE * lz + CHUNK_AREA * ly
            voxel_id = int(chunk.voxels[voxel_index])

            return voxel_id, voxel_index, glm.ivec3(lx, ly, lz), chunk
        return 0, 0, None, None
