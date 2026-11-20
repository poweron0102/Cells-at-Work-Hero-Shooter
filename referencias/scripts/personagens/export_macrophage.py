"""Exporta a Macrófaga e a escopeta da cena de autoria para o Raylib."""
import json
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'referencias' / 'blender' / 'macrophage.blend'
CLIPS = {'Idle', 'Walk', 'Run', 'Jump', 'Land', 'Fire', 'Reload', 'Melee'}


def load_collection(name, actions=False):
    with bpy.data.libraries.load(str(SOURCE)) as (source, loaded):
        loaded.collections = [name]
        if actions:
            loaded.actions = [name for name in source.actions if name in CLIPS]
    collection = loaded.collections[0]
    bpy.context.scene.collection.children.link(collection)
    return collection


def export(path, objects, animations=False, active=None):
    from build_characters import read_glb, raylib_mesh_indices

    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active if active else objects[0]
    scene = bpy.context.scene
    previous_fps, scene.render.fps = scene.render.fps, 30
    try:
        bpy.ops.export_scene.gltf(
            filepath=str(path), export_format='GLB', use_selection=True,
            export_vertex_color='ACTIVE', export_animation_mode='ACTIONS',
            export_anim_single_armature=True, export_anim_slide_to_zero=True,
            export_frame_range=False, export_animations=animations, export_skins=animations,
            export_morph=False,
        )
    finally:
        scene.render.fps = previous_fps
    gltf, _ = read_glb(path)
    mapping, count = raylib_mesh_indices(gltf)
    primitives = [p for mesh in gltf['meshes'] for p in mesh['primitives']]
    count_triangles = sum(gltf['accessors'][p['indices']]['count'] // 3 for p in primitives)
    return gltf, mapping, count, count_triangles


def write_meta(path, meta):
    path.with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def character():
    from build_characters import CONVENTION, to_gltf

    collection = load_collection('macrophage', actions=True)
    rig, body = collection.objects['macrophage.rig'], collection.objects['macrophage.body']
    path = ROOT / 'Assets' / 'Characters3D' / 'macrophage.glb'
    gltf, mapping, count, triangles = export(path, [rig, body], animations=True, active=rig)
    clips = [a['name'] for a in gltf['animations']]
    if set(clips) != CLIPS:
        raise ValueError(f'Clipes da Macrófaga: {clips}')
    origin = to_gltf(rig.data.bones['socket_weapon'].head_local)
    write_meta(path, {'key': 'macrophage', 'height': 1.82, 'convention': CONVENTION, 'mesh_count': count,
                      'triangles': triangles, 'clips': clips,
                      'parts': [{'name': 'body', 'mesh': mapping[body.name][0], 'pivot': [0, 0, 0],
                                 'parent': 'body', 'swing': 'static'}],
                      'mount': {'part': 'body', 'bone': 'socket_weapon',
                                'matrix': [[1, 0, 0, origin[0]], [0, 1, 0, origin[1]], [0, 0, 1, origin[2]]]}})
    # As prévias em grupo reposicionam malhas avulsas.
    body.modifiers.clear()
    body.parent = None
    bpy.data.objects.remove(rig, do_unlink=True)
    return [body]


def weapon():
    from build_weapons import CONVENTION, gl_matrix, gl_vec

    collection = load_collection('macrophage.weapon')
    objects = list(collection.objects)
    path = ROOT / 'Assets' / 'Weapons' / 'macrophage.glb'
    _, mapping, count, triangles = export(path, objects)
    flat = collection['fp']
    fp = Matrix([flat[i:i + 4] for i in range(0, 16, 4)])
    parts = []
    for obj in objects:
        name = obj.name.split('.', 1)[1]
        anim = {'pump': 'bolt', 'mag': 'mag'}.get(name, 'static')
        part = {'name': name, 'mesh': mapping[obj.name][0], 'anim': anim, 'space': 'gun', 'fp_only': False}
        if anim != 'static':
            delta = {'pump': (0, 0.075, 0), 'mag': collection['cartucho_curso']}[name]
            part.update(pivot=[0, 0, 0], axis=gl_vec(delta), amount=1.0)
        parts.append(part)
    spec = {'key': 'macrophage', 'kind': 'shotgun', 'convention': CONVENTION, 'mesh_count': count,
            'triangles': triangles, 'fp': gl_matrix(fp), 'muzzle': gl_vec(collection['muzzle']),
            'eject': gl_vec(collection['eject']), 'parts': parts}
    write_meta(path, spec)
    return objects, {'fp': fp}, [SimpleNamespace(**part) for part in parts]


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    character()
    weapon()
