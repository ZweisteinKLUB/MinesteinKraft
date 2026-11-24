# PyInstaller spec - build with:  pyinstaller --noconfirm minesteinkraft.spec
# Output: dist/MinesteinKraft/ (Windows, Linux) and dist/MinesteinKraft.app (macOS)
import sys
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = 'MinesteinKraft'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('shaders', 'shaders')],
    # moderngl picks its OpenGL loader (wgl / x11 / egl / darwin) at runtime
    hiddenimports=collect_submodules('glcontext'),
    excludes=['tkinter', 'pytest', 'numba', 'llvmlite'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=f'{APP_NAME}.app',
        bundle_identifier='org.minesteinkraft.game',
        info_plist={'NSHighResolutionCapable': False},
    )
