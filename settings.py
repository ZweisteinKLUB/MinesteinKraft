import numpy as np
try:
    from pyglm import glm  # PyGLM >= 2.8
except ImportError:
    import glm
import math

# OpenGL settings
MAJOR_VER, MINOR_VER = 3, 3
DEPTH_SIZE = 24
NUM_SAMPLES = 0  # MSAA samples (0 = off); falls back to 0 if unsupported

# preferred window size; shrunk to fit the desktop, window is resizable
WIN_RES = (1600, 900)
WIN_SCREEN_RATIO = 0.9  # max fraction of the desktop used by the window

#world generation
SEED = 16

# ray casting
MAX_RAY_DIST = 6

# chunk
CHUNK_SIZE = 32
H_CHUNK_SIZE = CHUNK_SIZE // 2
CHUNK_AREA = CHUNK_SIZE * CHUNK_SIZE
CHUNK_VOL = CHUNK_AREA * CHUNK_SIZE
CHUNK_SPHERE_RADIUS = H_CHUNK_SIZE * math.sqrt(3)

# world
WORLD_W, WORLD_H = 5, 2
WORLD_D = WORLD_W
WORLD_AREA = WORLD_W * WORLD_D
WORLD_VOL = WORLD_AREA * WORLD_H

# world center
CENTER_XZ = WORLD_W * H_CHUNK_SIZE
CENTER_Y = WORLD_H * H_CHUNK_SIZE


# camera
FOV_DEG = 50
V_FOV = glm.radians(FOV_DEG) # vertical FOV (horizontal FOV follows the window aspect ratio)
NEAR = 0.1
FAR = 2000.0
PITCH_MAX = glm.radians(89)

#player
PLAYER_SPEED = 0.005  # blocks per millisecond (5 blocks/s)
PLAYER_SPRINT_FACTOR = 10  # fly mode sprint
WALK_SPRINT_FACTOR = 1.6  # walking sprint
PLAYER_ROT_SPEED = 0.003
PLAYER_POS = glm.vec3(CENTER_XZ, WORLD_H * CHUNK_SIZE, CENTER_XZ)  # eye position before spawning
MOUSE_SENSITIVITY = 0.002

# player body and physics (units: blocks, seconds)
PLAYER_WIDTH = 0.6
PLAYER_HEIGHT = 1.8
PLAYER_EYE_HEIGHT = 1.62
GRAVITY = 28.0
JUMP_HEIGHT = 1.25  # enough to climb one block, not two
MAX_FALL_SPEED = 50.0
STEP_HEIGHT = 0.5  # obstacles up to this height are climbed automatically

# colors
BG_COLOR = glm.vec3(0.58, 0.83, 0.99)

# textures
SAND = 1
GRASS = 2
DIRT = 3
STONE = 4
SNOW = 5
LEAVES = 6
WOOD = 7

# terrain levels
SNOW_LVL = 54
STONE_LVL = 49
DIRT_LVL = 40
GRASS_LVL = 8
SAND_LVL = 7

# island: terrain sinks into the sea beyond this distance from the world center
ISLAND_RADIUS = 0.85 * CENTER_XZ
ISLAND_FALLOFF = 20  # higher = steeper coast

# archipelago beyond the starting island (world extension)
GENERATOR_VERSION = 1           # stored in each world; bump when the generator changes
ARCHIPELAGO_SCALE = 450.0       # size of the land / sea patterns (blocks)
ARCHIPELAGO_THRESHOLD = 0.15    # higher = less land
START_CLEAR_RADIUS = (120.0, 190.0)  # no archipelago land inside, full effect beyond

# tree settings
TREE_PROBABILITY = 0.02
TREE_WIDTH, TREE_HEIGHT = 4, 8
TREE_H_WIDTH, TREE_H_HEIGHT = TREE_WIDTH // 2, TREE_HEIGHT // 2

# water
WATER_LINE = 5.6
WATER_AREA = 5 * CHUNK_SIZE * WORLD_W

# swimming (units: blocks, seconds); terminal speed = acceleration / drag
WATER_GRAVITY = 5.0       # net sinking acceleration (gravity minus buoyancy)
WATER_DRAG = 4.0          # 1/s, brakes falls into the water
SWIM_UP_ACCEL = 17.0      # Space: rises at ~3 blocks/s
DIVE_ACCEL = 9.0          # Left Shift: dives at ~3.5 blocks/s
WATER_SPEED_FACTOR = 0.55 # horizontal speed in water
WATER_CLIMB_SPEED = 9.5   # boost to climb out onto a bank up to ~1.5 block above the water
WATER_ENTRY_DAMPING = 0.3 # vertical speed kept when plunging into the water

# underwater ambiance
WATER_FOG_COLOR = glm.vec3(0.04, 0.22, 0.42)
WATER_FOG_DENSITY = 0.006  # visibility ~ 20-25 blocks

# cloud
CLOUD_SCALE = 25
CLOUD_HEIGHT = WORLD_H * CHUNK_SIZE * 2

# block breaking: seconds to break each block type while holding the left button
BREAK_TIME = {SAND: 0.5, GRASS: 0.6, DIRT: 0.6, STONE: 1.5, SNOW: 0.35, LEAVES: 0.3, WOOD: 1.0}
DEFAULT_BREAK_TIME = 1.0
CRACK_STAGES = 10
CRACK_TEXTURE_SIZE = 16

# FPS Limit
FPS = 60