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

# world streaming (the world is unbounded horizontally; WORLD_W x WORLD_D is the base area)
RENDER_DISTANCE = 8         # chunks loaded around the player (horizontal radius)
UNLOAD_MARGIN = 2           # extra chunks kept before unloading (avoids load / unload flicker)
CHUNK_BUDGET_MS = 6.0       # time per frame spent loading / generating / meshing chunks
AUTOSAVE_INTERVAL = 5.0     # seconds between saves of modified / new chunks
# fog: light haze, then fully opaque at the edge of the loaded area (hides chunk pop-in)
FOG_END = (RENDER_DISTANCE - 1) * CHUNK_SIZE
FOG_START = 0.55 * FOG_END

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
PLAYER_SPEED = 0.0035  # blocks per millisecond (3.5 blocks/s: brisk walk)
WALK_SPRINT_FACTOR = 2.0  # running (Left Ctrl): 7 blocks/s
FLY_SPEED = 5.0  # blocks/s
PLAYER_SPRINT_FACTOR = 10  # fly mode sprint
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

# view: first person, third person from behind, third person from the front (F5)
CAMERA_DISTANCE = 4.0     # third person camera distance from the eyes (shortened by walls)
CAMERA_MARGIN = 0.25      # gap kept between the camera and a block
CAMERA_SHOULDER = (0.6, 0.35)  # third person: camera shifted right / up (over the shoulder)

# mobs: animation (ground speed of each locomotion clip at its nominal rate, see models/)
ANIM_FADE = 0.2           # seconds of cross-fade between animation states
WALK_ANIM_SPEED = 1.94    # player walk clip
RUN_ANIM_SPEED = 4.89     # player run clip
SWIM_ANIM_SPEED = 1.3     # player crawl clip
BODY_TURN_SPEED = 10.0    # rad/s, body turning towards the moving direction
HEAD_MAX_YAW = math.radians(70)
HEAD_MAX_PITCH = math.radians(55)
SWIM_DEPTH = 1.0          # water depth (above the feet) from which the player swims

# hostile mob: the Tourbeux (peat-and-stone brute, walks on its knuckles, avoids water)
TOURBEUX_WALK_ANIM_SPEED = 0.68    # ground speed of its clips at their nominal rate
TOURBEUX_CHARGE_ANIM_SPEED = 2.69
TOURBEUX_WANDER_SPEED = 1.2        # blocks/s
TOURBEUX_CHARGE_SPEED = 5.0        # faster than walking (3.5), slower than running (7)
TOURBEUX_DETECT_RANGE = 16.0       # sees the player within this distance (line of sight)
TOURBEUX_GIVE_UP_RANGE = 24.0      # stops chasing beyond this distance
TOURBEUX_MEMORY = 3.0              # seconds it keeps chasing after losing sight of the player
TOURBEUX_ATTACK_RANGE = 1.7        # distance (feet to feet) from which it strikes
TOURBEUX_ATTACK_COOLDOWN = 1.2     # seconds between two strikes
TOURBEUX_IMPACT = 0.55             # moment of the impact in the attack clip (fraction)
TOURBEUX_KNOCKBACK = 9.0           # horizontal push given to the player (blocks/s)
TOURBEUX_KNOCKBACK_UP = 5.5        # small hop given to the player (blocks/s)

# mob spawning around the player (not saved with the world)
MAX_HOSTILES = 3
SPAWN_INTERVAL = 2.0               # seconds between spawn attempts
SPAWN_DISTANCE = (24.0, 48.0)      # min / max horizontal distance from the player
DESPAWN_DISTANCE = 64.0

# day / night cycle (accelerated)
DAY_LENGTH = 20 * 60.0      # real seconds per game day (24 game hours)
START_HOUR = 8.0            # time of day when a new world starts
LATITUDE = 35.0             # degrees: the sun culminates 55 degrees above the southern horizon
LUNAR_CYCLE_DAYS = 8.0      # game days from new moon to new moon
TIME_SKIP_HOURS = 1.0       # F7: jump forward in time

# light (linear HDR units, before the exposure)
SUN_ILLUMINANCE = 3.0
MOON_ILLUMINANCE = 0.16
DAY_EXPOSURE = 1.0
NIGHT_EXPOSURE = 8.0        # the eye adapts to the dark: nights stay playable
MIN_AMBIENT = 0.008         # cave ambient light (caves are dark, never fully black)

# weather: random durations (game hours), transition time (real seconds)
WEATHER_DURATION_HOURS = {
    'clear': (4.0, 10.0), 'cloudy': (2.0, 6.0), 'fog': (1.5, 4.0),
    'rain': (1.5, 4.0), 'storm': (1.0, 2.5), 'snow': (2.0, 5.0),
}
WEATHER_TRANSITION_S = 40.0
WETNESS_RATES = (1 / 30.0, 1 / 180.0)       # ground gets wet / dries (per second at full rain / sun)
SNOW_COVER_RATES = (1 / 90.0, 1 / 300.0)    # snow settles / melts
LIGHTNING_INTERVAL = (2.0, 10.0)            # seconds between strikes in a full storm
LIGHTNING_DISTANCE = (60.0, 500.0)          # blocks from the player
CLOUD_ALTITUDE = 420.0                      # blocks above the sea
CLOUD_SPEED = 6.0                           # blocks/s at full wind
WAVE_HEIGHT = (0.06, 0.55)                  # wave amplitude (blocks): calm, storm

# graphics: shadows, water reflections, post-processing ('--graphics low|medium|high')
GRAPHICS_PRESETS = {
    'low':    dict(shadow_size=1024, cascades=1, ssr=False, godrays=False, bloom=True, water_grid=96),
    'medium': dict(shadow_size=2048, cascades=2, ssr=False, godrays=True, bloom=True, water_grid=160),
    'high':   dict(shadow_size=2048, cascades=2, ssr=True, godrays=True, bloom=True, water_grid=256),
}
DEFAULT_GRAPHICS = 'high'
SHADOW_CASCADE_RADIUS = (36.0, 150.0)       # blocks around the camera covered by each shadow map
HEIGHTMAP_SIZE = 1024                       # sky occlusion / rain map (blocks, wraps around)
PRECIPITATION_RADIUS = 28.0                 # rain / snow is drawn in this box around the camera
RAIN_DROPS = 9000

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


# block breaking: seconds to break each block type while holding the left button
BREAK_TIME = {SAND: 0.5, GRASS: 0.6, DIRT: 0.6, STONE: 1.5, SNOW: 0.35, LEAVES: 0.3, WOOD: 1.0}
DEFAULT_BREAK_TIME = 1.0
CRACK_STAGES = 10
CRACK_TEXTURE_SIZE = 16

# FPS Limit
FPS = 60