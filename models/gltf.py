"""Minimal glTF 2.0 binary (.glb) reader: skinned meshes, skeleton and animations.

Only what the game's models use is supported: triangle primitives with
POSITION / NORMAL / COLOR_0 / JOINTS_0 / WEIGHTS_0, one skin, node TRS
transforms and LINEAR / STEP animation channels. No OpenGL here, so it can be
unit-tested.

Conventions: quaternions are (x, y, z, w) as in glTF; matrices are numpy
arrays in math order (``M @ v``), i.e. row-major (glTF stores them column-major).
"""
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

GLB_MAGIC = 0x46546C67   # 'glTF'
CHUNK_JSON = 0x4E4F534A  # 'JSON'
CHUNK_BIN = 0x004E4942   # 'BIN\0'

COMPONENT_DTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16,
                    5123: np.uint16, 5125: np.uint32, 5126: np.float32}
TYPE_SIZES = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
TRIANGLES = 4


class GltfError(ValueError):
    pass


@dataclass
class Node:
    name: str
    parent: int                     # -1 for a root node
    translation: np.ndarray         # (3,)
    rotation: np.ndarray            # (4,) x, y, z, w
    scale: np.ndarray               # (3,)
    children: list = field(default_factory=list)


@dataclass
class Channel:
    node: int
    path: str                       # 'translation', 'rotation' or 'scale'
    times: np.ndarray               # (k,)
    values: np.ndarray              # (k, 3) or (k, 4)
    step: bool = False              # STEP interpolation (else LINEAR)


@dataclass
class Animation:
    name: str
    channels: list
    duration: float


@dataclass
class Model:
    nodes: list                     # Node, parents before children not guaranteed
    joints: list                    # node index of each skin joint
    inverse_bind: np.ndarray        # (J, 4, 4)
    # one vertex per triangle corner (no index buffer): (N, 3) / (N, 3) / (N, 3) / (N, 4) / (N, 4)
    positions: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    joint_ids: np.ndarray
    weights: np.ndarray
    animations: dict                # name -> Animation

    def node_index(self, name):
        for i, node in enumerate(self.nodes):
            if node.name == name:
                return i
        raise KeyError(name)


def read_glb(path):
    """Split a .glb file into its JSON document and binary chunk."""
    data = Path(path).read_bytes()
    return parse_glb_bytes(data)


def parse_glb_bytes(data):
    if len(data) < 12:
        raise GltfError('file too short')
    magic, version, length = struct.unpack_from('<III', data, 0)
    if magic != GLB_MAGIC or version != 2:
        raise GltfError('not a glTF 2.0 binary file')
    offset, doc, binary = 12, None, b''
    while offset + 8 <= min(length, len(data)):
        chunk_len, chunk_type = struct.unpack_from('<II', data, offset)
        chunk = data[offset + 8: offset + 8 + chunk_len]
        if chunk_type == CHUNK_JSON:
            doc = json.loads(chunk.decode('utf-8'))
        elif chunk_type == CHUNK_BIN:
            binary = bytes(chunk)
        offset += 8 + chunk_len
    if doc is None:
        raise GltfError('missing JSON chunk')
    return doc, binary


def read_accessor(doc, binary, index):
    """Accessor ``index`` as a float32 (or integer) numpy array of shape (count, size)."""
    acc = doc['accessors'][index]
    dtype = np.dtype(COMPONENT_DTYPES[acc['componentType']]).newbyteorder('<')
    size = TYPE_SIZES[acc['type']]
    count = acc['count']
    if 'bufferView' not in acc:
        out = np.zeros((count, size), dtype=dtype)
    else:
        view = doc['bufferViews'][acc['bufferView']]
        start = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
        stride = view.get('byteStride') or dtype.itemsize * size
        if stride == dtype.itemsize * size:
            out = np.frombuffer(binary, dtype=dtype, count=count * size, offset=start).reshape(count, size)
        else:  # interleaved
            rows = [np.frombuffer(binary, dtype=dtype, count=size, offset=start + i * stride) for i in range(count)]
            out = np.array(rows, dtype=dtype).reshape(count, size)
    if acc.get('normalized'):
        info = np.iinfo(dtype)
        out = np.maximum(out.astype(np.float32) / info.max, -1.0)
    return out


def _node_trs(node):
    if 'matrix' in node:
        m = np.array(node['matrix'], dtype=np.float32).reshape(4, 4).T
        t = m[:3, 3].copy()
        s = np.linalg.norm(m[:3, :3], axis=0)
        rot = m[:3, :3] / np.where(s == 0, 1, s)
        from models.animation import quat_from_matrix
        return t, quat_from_matrix(rot), s
    t = np.array(node.get('translation', (0, 0, 0)), dtype=np.float32)
    r = np.array(node.get('rotation', (0, 0, 0, 1)), dtype=np.float32)
    s = np.array(node.get('scale', (1, 1, 1)), dtype=np.float32)
    return t, r, s


def _material_color(doc, material_index):
    if material_index is None:
        return np.ones(3, dtype=np.float32)
    pbr = doc['materials'][material_index].get('pbrMetallicRoughness', {})
    return np.array(pbr.get('baseColorFactor', (1, 1, 1, 1))[:3], dtype=np.float32)


def load_model(path):
    doc, binary = read_glb(path)
    return model_from_gltf(doc, binary)


def model_from_gltf(doc, binary):
    # ---- nodes
    raw_nodes = doc.get('nodes', [])
    nodes = []
    for i, n in enumerate(raw_nodes):
        t, r, s = _node_trs(n)
        nodes.append(Node(n.get('name', f'node{i}'), -1, t, r, s, list(n.get('children', []))))
    for i, node in enumerate(nodes):
        for c in node.children:
            nodes[c].parent = i

    # ---- skin
    skins = doc.get('skins', [])
    if skins:
        skin = skins[0]
        joints = list(skin['joints'])
        if 'inverseBindMatrices' in skin:
            ibm = read_accessor(doc, binary, skin['inverseBindMatrices']).astype(np.float32)
            inverse_bind = ibm.reshape(-1, 4, 4).transpose(0, 2, 1).copy()
        else:
            inverse_bind = np.tile(np.eye(4, dtype=np.float32), (len(joints), 1, 1))
    else:
        joints, inverse_bind = [], np.zeros((0, 4, 4), dtype=np.float32)

    # ---- meshes (every primitive of every mesh node, expanded to triangle corners)
    parts = {k: [] for k in ('pos', 'nrm', 'col', 'jnt', 'wgt')}
    for node in raw_nodes:
        if 'mesh' not in node:
            continue
        for prim in doc['meshes'][node['mesh']]['primitives']:
            if prim.get('mode', TRIANGLES) != TRIANGLES:
                continue
            attrs = prim['attributes']
            pos = read_accessor(doc, binary, attrs['POSITION']).astype(np.float32)
            n = len(pos)
            nrm = (read_accessor(doc, binary, attrs['NORMAL']).astype(np.float32)
                   if 'NORMAL' in attrs else np.tile([0.0, 1.0, 0.0], (n, 1)).astype(np.float32))
            base = _material_color(doc, prim.get('material'))
            if 'COLOR_0' in attrs:
                col = read_accessor(doc, binary, attrs['COLOR_0']).astype(np.float32)[:, :3] * base
            else:
                col = np.tile(base, (n, 1))
            if 'JOINTS_0' in attrs and skins:
                jnt = read_accessor(doc, binary, attrs['JOINTS_0']).astype(np.float32)
                wgt = read_accessor(doc, binary, attrs['WEIGHTS_0']).astype(np.float32)
            else:  # rigid: follow the first joint
                jnt = np.zeros((n, 4), dtype=np.float32)
                wgt = np.tile([1.0, 0.0, 0.0, 0.0], (n, 1)).astype(np.float32)
            if 'indices' in prim:
                idx = read_accessor(doc, binary, prim['indices']).reshape(-1).astype(np.int64)
            else:
                idx = np.arange(n)
            for key, arr in zip(parts, (pos, nrm, col, jnt, wgt)):
                parts[key].append(arr[idx])
    if not parts['pos']:
        raise GltfError('no triangle mesh in file')
    pos, nrm, col, jnt, wgt = (np.concatenate(parts[k]) for k in parts)
    total = wgt.sum(axis=1, keepdims=True)
    wgt = wgt / np.where(total == 0, 1, total)

    # ---- animations
    animations = {}
    for a, anim in enumerate(doc.get('animations', [])):
        channels, duration = [], 0.0
        for ch in anim['channels']:
            target = ch['target']
            path = target.get('path')
            if path not in ('translation', 'rotation', 'scale') or 'node' not in target:
                continue
            sampler = anim['samplers'][ch['sampler']]
            times = read_accessor(doc, binary, sampler['input']).reshape(-1).astype(np.float32)
            values = read_accessor(doc, binary, sampler['output']).astype(np.float32)
            interp = sampler.get('interpolation', 'LINEAR')
            if interp == 'CUBICSPLINE':  # keep the values, drop the tangents
                values = values.reshape(len(times), 3, -1)[:, 1]
            channels.append(Channel(target['node'], path, times, values, interp == 'STEP'))
            duration = max(duration, float(times[-1]) if len(times) else 0.0)
        name = anim.get('name', f'anim{a}')
        animations[name] = Animation(name, channels, duration)

    return Model(nodes, joints, inverse_bind, pos, nrm, col, jnt, wgt, animations)
