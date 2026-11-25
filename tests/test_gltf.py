import json
import math
import struct

import numpy as np
import pytest

from models.gltf import parse_glb_bytes, model_from_gltf, GltfError
from models.animation import (Skeleton, Clip, Animator, load_clips, quat_from_axis_angle,
                              quat_to_matrix, quat_from_matrix, nlerp, blend_poses)


def make_glb(doc, binary):
    js = json.dumps(doc).encode()
    js += b' ' * (-len(js) % 4)
    binary += b'\0' * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<II', len(js), 0x4E4F534A) + js
            + struct.pack('<II', len(binary), 0x004E4942) + binary)


def two_bone_glb():
    """Root joint at the origin, child joint 1 m up, one triangle on the child, one clip."""
    buf = bytearray()
    views, accessors = [], []

    def add(array, component, type_, **extra):
        array = np.ascontiguousarray(array)
        views.append({'buffer': 0, 'byteOffset': len(buf), 'byteLength': array.nbytes})
        buf.extend(array.tobytes())
        buf.extend(b'\0' * (-len(buf) % 4))
        accessors.append({'bufferView': len(views) - 1, 'componentType': component,
                          'count': len(array), 'type': type_, **extra})
        return len(accessors) - 1

    pos = add(np.array([[0, 1, 0], [1, 1, 0], [0, 2, 0]], np.float32), 5126, 'VEC3')
    col = add(np.array([[65535, 0, 0, 65535]] * 3, np.uint16), 5123, 'VEC4', normalized=True)
    jnt = add(np.array([[1, 0, 0, 0]] * 3, np.uint8), 5121, 'VEC4')
    wgt = add(np.array([[1, 0, 0, 0]] * 3, np.float32), 5126, 'VEC4')
    ibm_rows = [np.eye(4), np.eye(4)]
    ibm_rows[1][1, 3] = -1.0  # inverse of a translation by +1 in y
    ibm = add(np.array([m.T.reshape(-1) for m in ibm_rows], np.float32), 5126, 'MAT4')  # column-major
    times = add(np.array([0, 1], np.float32), 5126, 'SCALAR')
    rots = add(np.array([[0, 0, 0, 1], list(quat_from_axis_angle((0, 0, 1), math.pi / 2))], np.float32),
               5126, 'VEC4')
    doc = {
        'asset': {'version': '2.0'},
        'nodes': [
            {'name': 'root', 'children': [1]},
            {'name': 'child', 'translation': [0, 1, 0]},
            {'name': 'body', 'mesh': 0, 'skin': 0},
        ],
        'meshes': [{'primitives': [{'attributes': {'POSITION': pos, 'COLOR_0': col,
                                                   'JOINTS_0': jnt, 'WEIGHTS_0': wgt}}]}],
        'skins': [{'joints': [0, 1], 'inverseBindMatrices': ibm}],
        'animations': [{'name': 'bend', 'samplers': [{'input': times, 'output': rots}],
                        'channels': [{'sampler': 0, 'target': {'node': 1, 'path': 'rotation'}}]}],
        'buffers': [{'byteLength': len(buf)}],
        'bufferViews': views,
        'accessors': accessors,
    }
    return make_glb(doc, bytes(buf))


@pytest.fixture
def model():
    return model_from_gltf(*parse_glb_bytes(two_bone_glb()))


def test_reads_mesh_skin_and_animation(model):
    assert [n.name for n in model.nodes] == ['root', 'child', 'body']
    assert model.nodes[1].parent == 0
    assert model.positions.shape == (3, 3)
    np.testing.assert_allclose(model.colors, [[1, 0, 0]] * 3)
    np.testing.assert_allclose(model.inverse_bind[1][:3, 3], [0, -1, 0])
    assert model.animations['bend'].duration == pytest.approx(1.0)


def test_rejects_non_glb():
    with pytest.raises(GltfError):
        parse_glb_bytes(b'not a glb file at all')


def skin_vertex(matrices, model, i):
    j = int(model.joint_ids[i, 0])
    return (matrices[j] @ np.append(model.positions[i], 1.0))[:3]


def test_rest_pose_leaves_vertices_in_place(model):
    sk = Skeleton(model)
    m = sk.skin_matrices(sk.rest)
    for i in range(3):
        np.testing.assert_allclose(skin_vertex(m, model, i), model.positions[i], atol=1e-6)


def test_clip_rotates_the_child_bone(model):
    sk = Skeleton(model)
    clip = Clip('bend', model.animations['bend'], sk)
    m = sk.skin_matrices(clip.sample(1.0, loop=False))
    # vertex (1, 1, 0) turns 90 degrees around z about the child joint (0, 1, 0) -> (0, 2, 0)
    np.testing.assert_allclose(skin_vertex(m, model, 1), [0, 2, 0], atol=1e-5)
    half = clip.sample(0.5, loop=False)
    np.testing.assert_allclose(half.r[1], quat_from_axis_angle((0, 0, 1), math.pi / 4), atol=1e-4)


def test_extra_rotation_turns_children_around_the_node(model):
    sk = Skeleton(model)
    rot = quat_to_matrix(quat_from_axis_angle((0, 0, 1), math.pi / 2))
    world = sk.world_matrices(sk.rest, extra={0: rot})
    np.testing.assert_allclose(world[1][:3, 3], [-1, 0, 0], atol=1e-6)


def test_quaternion_helpers():
    q = quat_from_axis_angle((0, 1, 0), 0.7)
    np.testing.assert_allclose(quat_from_matrix(quat_to_matrix(q)), q, atol=1e-6)
    a, b = np.array([0, 0, 0, 1.0]), -np.array([0, 0, 0, 1.0])
    np.testing.assert_allclose(nlerp(a, b, 0.5), a)  # shortest arc: no flip through zero


def test_animator_cross_fade_and_oneshot(model):
    sk = Skeleton(model)
    clips = load_clips(model, sk)
    anim = Animator(sk, clips, fade=0.2)
    anim.set_state('bend', loop=False)
    anim.update(0.5)
    assert anim.state == 'bend'
    np.testing.assert_allclose(anim.pose().r[1], quat_from_axis_angle((0, 0, 1), math.pi / 4), atol=1e-3)
    anim.play_once('bend')
    assert anim.oneshot_playing
    anim.update(1.1)
    assert not anim.oneshot_playing


def test_blend_weights_share_phase(model):
    sk = Skeleton(model)
    clips = load_clips(model, sk)
    anim = Animator(sk, clips)
    anim.set_blend('loco', {'bend': 1.0}, rate=1.0)
    anim.update(0.25)
    anim.set_blend('loco', {'bend': 1.0}, rate=2.0)  # same key: no restart, no fade
    assert anim.current.phase == pytest.approx(0.25)
    assert anim.previous is None
    p = blend_poses(sk.rest, sk.rest, 0.5)
    np.testing.assert_allclose(p.r, sk.rest.r)
