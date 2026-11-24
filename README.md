# MinesteinKraft

Voxel game engine in Python: procedural island terrain with caves, trees, water and clouds,
ambient occlusion, and block breaking / placing.

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

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The game can be started from any directory (`python path/to/main.py`).

## Controls

| Action                  | Keys                                      |
|-------------------------|-------------------------------------------|
| Move                    | `Z Q S D` (AZERTY), `W A S D` or arrows   |
| Jump                    | `Space` (climbs one block)                |
| Swim up / dive          | `Space` / `Left Shift` (in water)         |
| Sprint                  | `Left Ctrl`                               |
| Toggle fly mode         | `F`                                       |
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
