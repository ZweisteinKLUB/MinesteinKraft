# MinesteinKraft

Voxel game engine in Python: an endless, saved archipelago with caves, trees and a living sea,
an accelerated day / night cycle with random weather (rain, storms, snow, fog), soft shadows and
HDR lighting, gravity and swimming, block breaking / placing, an animated player body seen in
third person, and hostile creatures.

Built with [pygame-ce](https://pyga.me/), [moderngl](https://github.com/moderngl/moderngl)
(OpenGL 3.3 core), [PyGLM](https://github.com/Zuzu-Typ/PyGLM) and [NumPy](https://numpy.org/).
Runs on Windows, macOS and Linux.

## Download

Ready-to-run builds for Windows, macOS (Apple Silicon and Intel) and Linux are attached to each
[GitHub release](../../releases). Unzip and start `MinesteinKraft`.

The builds are not code-signed:
- **Windows**: SmartScreen may warn. Click *More info*, then *Run anyway*.
- **macOS**: right-click `MinesteinKraft.app`, choose *Open*, then confirm. Alternatively, run
  `xattr -dr com.apple.quarantine MinesteinKraft.app`.

## Run from source

Requirements: Python 3.10 or newer, and a GPU / driver with **OpenGL 3.3**.

The launch scripts create a `.venv` environment and install the dependencies on the first run.
After that they start the game immediately, reinstalling only when `requirements.txt` changes:

| System        | Start the game                                    |
|---------------|---------------------------------------------------|
| Linux / macOS | `./run.sh`                                        |
| macOS         | double-click `run.command` in the Finder          |
| Windows       | double-click `run.bat`, or `run.bat` in a terminal |

Options are passed to the game, e.g. `./run.sh --world-dir ~/my-worlds` or `./run.sh --graphics low`.

By hand:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The game can be started from any directory (`python path/to/main.py`).

## Worlds and saves

- **Start menu**: choose an existing world (most recently played first) or create a new one.
  - A new world takes a name and an optional seed: empty means random, a number is used as is,
    and any text gives a stable seed.
  - Each world is generated from its own seed.
- **First launch of a world**: the starting island is generated and saved.
  - The world then **grows on its own** as you explore: chunks around the player are loaded from
    the save or generated on the fly.
  - Beyond the starting island lies an archipelago of islands of every size.
  - The terrain is computed from the seed and the coordinates, so new areas always match the
    existing ones exactly.
- **Saving is automatic**: every 5 seconds and when you quit.
  - Everything is saved: generated chunks, your changes, and the player's position.
  - Reopening a world brings everything back.
- **Where saves live**: one SQLite file per world, in
  - Windows: `%APPDATA%\MinesteinKraft\worlds\`
  - macOS: `~/Library/Application Support/MinesteinKraft/worlds/`
  - Linux: `~/.local/share/minesteinkraft/worlds/` (or `$XDG_DATA_HOME`)

  Another folder can be used with `python main.py --world-dir PATH` or the environment variable
  `MINESTEINKRAFT_DATA_DIR`.
- **Deleting a world**: delete its `.db` file and the `-wal` / `-shm` files next to it.
  The game itself never deletes a world.
- **Size**: about 0.5 KB per chunk on average. Exploring 1 km adds roughly 1.5 MB.
- **Unreadable files** are listed in red in the menu and are never modified.

## Controls

| Action                  | Keys                                      |
|-------------------------|-------------------------------------------|
| Move                    | `Z Q S D` (AZERTY), `W A S D` or arrows   |
| Jump                    | `Space` (climbs one block)                |
| Swim up / dive          | `Space` / `Left Shift` (in water)         |
| Run                     | `Left Ctrl` (walk 3.5 blocks/s, run 7)    |
| Toggle fly mode         | `F`                                       |
| Change view             | `F5`: first person, behind, in front      |
| Change the weather      | `F6` (clear, cloudy, fog, rain, storm, snow) |
| Skip one hour           | `F7`                                      |
| Fly up / down           | `Space` / `Left Shift` (fly mode)         |
| Look around             | Mouse                                     |
| Break block             | Hold left click (cracks grow; harder blocks take longer) |
| Place block             | Left click (place mode)                   |
| Switch break / place    | Right click                               |
| Release mouse           | `Esc`; click in the window to capture it again |
| Quit                    | `Esc` while the mouse is released, or close the window |

In walking mode the player is subject to gravity and collides with blocks.
Obstacles lower than half a block are climbed automatically.
Fly mode has no gravity but still collides with blocks.
In the water the player floats and sinks slowly. Under water, the view turns blue and foggy.
To climb out, swim up against the bank.
The generated world is surrounded by invisible walls.

## Day, night and weather

- **A day lasts 20 minutes.** The sun rises in the east, crosses the southern sky and sets in the
  west. The moon follows, with its phases (a full cycle every 8 days): a full moon lights the
  night and casts shadows; on a new moon the stars and the milky way take over.
  - The time of day, the day count and the weather are saved with the world. A new world starts
    at 8 am. The window title shows the day, the time and the weather.
- **The weather changes on its own**, at random, after a few game hours. Each change takes about
  40 seconds, like a front coming in.
  - *Clear*, *cloudy*: drifting clouds, their shadows move over the ground.
  - *Fog*: a thick ground fog, more likely in the morning.
  - *Rain*: rain falls (not under roofs, trees or in caves), splashes on the ground and rings on
    the water. The ground gets wet, darker and shiny, with puddles; it dries in the sun.
  - *Storm*: dark sky, heavy rain, strong wind and waves, lightning strikes.
  - *Snow*: snow flakes, and a snow layer builds up on the ground, then melts. Above the snow
    line (high mountains), rain falls as snow.
- **The sea** moves with the wind: waves (higher in a storm, calmer near the shore), ripples,
  foam on the beaches and on the crests of storm waves. It is transparent near the shore,
  reflects the sky and the land, and glitters in the sun. From below, the sky shows through a
  circular window, as in real water.
- **Light**: soft shadows of the sun (and of the moon), light reflected by the ground, dark caves,
  leaves swaying in the wind and glowing when backlit, glare and light shafts around the sun.

## Graphics

The image is computed in HDR, then tone mapped like a camera. `--graphics` sets the quality:

| Preset   | Shadows                  | Water reflections of the land | Light shafts |
|----------|--------------------------|-------------------------------|--------------|
| `low`    | 1 shadow map, 1024 px    | sky only                      | no           |
| `medium` | 2 shadow maps, 2048 px   | sky only                      | yes          |
| `high`   | 2 shadow maps, 2048 px   | yes (screen space)            | yes          |

`high` is the default. On a mid-range desktop GPU (Radeon RX 6700 XT) a frame takes about 4 ms
at 1920 x 1080; integrated GPUs may need `low`.

## Mobs

Mobs are the creatures of the world, peaceful or hostile. Each one has a body with a skeleton,
its own animations and behaviour, and collides with blocks like the player.

- **The player** is a mob too. Press `F5` to see the body from behind (over the shoulder) or from
  the front. The camera is pulled in by walls.
  - A 1.80 m human (1 block = 1 m) with head, trunk, arms and legs.
  - Animations: standing, walking, running, jumping, falling, hovering and flying, treading water
    and front crawl.
  - Walking and running blend with the speed, so the feet do not slide. The head follows the view.
- **The Tourbeux** is a hostile brute of peat and mossy stone, with glowing amber eyes.
  It walks hunched on its knuckles and has mushrooms growing on its back.
  - It wanders slowly on land.
  - When it sees you within 16 blocks, it charges at 5 blocks/s: faster than walking, slower
    than running.
  - Close enough, it rears up and slams both fists, knocking you back (no damage yet).
  - It never goes into water: swim away to escape.
  - Up to 3 appear on land, 24 to 48 blocks around the player. They vanish when left far behind
    and are not saved.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest            # unit tests (+ shader compilation if OpenGL 3.3 is available)
```

The code layout:

- `terrain_gen.py`: world generation.
- `noise.py`: simplex noise.
- `meshes/chunk_mesh_builder.py`: chunk meshing with face culling and ambient occlusion.
- `voxel_handler.py`: ray casting and editing.

All of these are vectorized with NumPy.

- `models/`: glTF (`.glb`) loading and skeletal animation (cross-fades, speed-matched blends).
  No extra dependency.
- `mobs/`: the `Mob` base class (physics, animation, rendering), the hostile `Tourbeux` and the
  spawn manager.
- `shaders/mob.*`: GPU skinning.
- `atmosphere/`: the clock, sun and moon (`daycycle.py`), the random weather (`weather.py`), the
  light colors they give (`lighting.py`) and the lightning (`environment.py`). Pure Python, tested
  without a GPU.
- `render/`: the frame (`pipeline.py`): shadow maps, HDR scene, sky, sea, rain / snow, lightning,
  then bloom, light shafts, tone mapping and FXAA (`postprocess.py`).
- `shaders/include/*.glsl`: code shared by the shaders (`#include "file.glsl"`, expanded by
  `shader_program.py`): the `Env` uniform block written once per frame, sky and fog, lighting,
  waves.
- `assets/models/*.glb`: the models and their animations. They are exported from the Blender
  sources in `assets/models/src/`; each animation is one NLA track, exported as a named clip.

### Build an executable

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm minesteinkraft.spec
```

Output goes to `dist/MinesteinKraft/` (Windows / Linux) or `dist/MinesteinKraft.app` (macOS).
PyInstaller only builds for the OS it runs on. The `Release` GitHub workflow builds all platforms
when a `v*` tag is pushed.

## Troubleshooting

- **"needs OpenGL 3.3"** at startup:
  - Update the graphics driver.
  - Virtual machines, remote desktop sessions and WSL often only offer older OpenGL versions.
    On WSL, use WSLg with an up-to-date GPU driver.
- **Linux**: install the Mesa drivers, e.g. `sudo apt install libgl1-mesa-dri libegl1`.
- **Slow or black window on a laptop with two GPUs**: force the dedicated GPU for Python or the
  executable.
- **Low frame rate**: start with `--graphics low` (or `medium`).
