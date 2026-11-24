"""Locate bundled resources (shaders, assets) independently of the working directory.

Works both when running from sources and inside a PyInstaller bundle,
where data files are extracted next to ``sys._MEIPASS``.
"""
import sys
from pathlib import Path

BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))


def resource_path(*parts) -> Path:
    return BASE_DIR.joinpath(*parts)


def user_data_dir() -> Path:
    """Per-user folder for saves (worlds), following each OS convention.

    Override with the MINESTEINKRAFT_DATA_DIR environment variable (tests, development).
    """
    import os
    override = os.environ.get('MINESTEINKRAFT_DATA_DIR')
    if override:
        return Path(override).expanduser()
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'MinesteinKraft'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'MinesteinKraft'
    xdg = os.environ.get('XDG_DATA_HOME')
    return (Path(xdg) if xdg else Path.home() / '.local' / 'share') / 'minesteinkraft'


def worlds_dir(base: Path = None) -> Path:
    return (base or user_data_dir()) / 'worlds'
