"""3D models of the mobs: glTF loading and skeletal animation (see gltf.py, animation.py)."""
from dataclasses import dataclass
from functools import lru_cache

from paths import resource_path
from models.gltf import Model, load_model
from models.animation import Skeleton, Clip, load_clips


@dataclass
class ModelAsset:
    name: str
    model: Model
    skeleton: Skeleton
    clips: dict  # name -> Clip


def model_path(name):
    return resource_path('assets', 'models', f'{name}.glb')


@lru_cache(maxsize=None)
def load_asset(name):
    """Model ``assets/models/<name>.glb`` with its baked clips, loaded once and shared."""
    model = load_model(model_path(name))
    skeleton = Skeleton(model)
    return ModelAsset(name, model, skeleton, load_clips(model, skeleton))
