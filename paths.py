"""Locate bundled resources (shaders, assets) independently of the working directory.

Works both when running from sources and inside a PyInstaller bundle,
where data files are extracted next to ``sys._MEIPASS``.
"""
import sys
from pathlib import Path

BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))


def resource_path(*parts) -> Path:
    return BASE_DIR.joinpath(*parts)
