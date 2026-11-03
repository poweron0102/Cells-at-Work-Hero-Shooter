"""Exporta o Bairro Arterial do Blender para o jogo.

Gera em Assets/Maps/BairroArterial/:
  BairroArterial.blend   fonte editavel (salva antes de exportar)
  BairroArterial.glb     arte (cores por vertice + padrao do shader em UV.x)
  runtime.json           colisao (triangulos), marcadores, rotas e metadados

Uso no Blender aberto (depois de build_distrito.py ou abrindo o .blend):
    exec(open(r'<repo>/scripts/export_distrito.py', encoding='utf-8').read(), {'REPO': r'<repo>'})
Em segundo plano:
    blender --background Assets/Maps/BairroArterial/BairroArterial.blend --python scripts/export_distrito.py
"""
import json
import os
import sys

import bpy

_RUN_EXPORT = __name__ == '__main__' or 'REPO' in globals()
REPO = globals().get('REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'Assets', 'Maps', 'BairroArterial')


def to_game(v):
    return (round(v[0], 4), round(v[2], 4), round(-v[1], 4))


def export(save_blend=True, bake=True):
    os.makedirs(OUT, exist_ok=True)
    if save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'BairroArterial.blend'), copy=True)
    art = bpy.data.collections['Arte']
    temporary = None
    try:
        objects = art.objects
        if bake:
            sys.path.insert(0, os.path.join(REPO, 'scripts'))
            from bake_distrito import bake_objects, remove_bake
            temporary, objects = bake_objects(art)
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects:
            if ob.type == 'MESH':
                ob.select_set(True)
                bpy.context.view_layer.objects.active = ob
        # Export atomically so an interrupted bake keeps the last playable map.
        target = os.path.join(OUT, 'BairroArterial.glb')
        pending = os.path.join(OUT, '_BairroArterial.pending.glb')
        bpy.ops.export_scene.gltf(filepath=pending, use_selection=True,
                                  export_format='GLB', export_yup=True, export_apply=True,
                                  export_vertex_color='ACTIVE', export_materials='NONE',
                                  export_normals=True, export_texcoords=True)
        os.replace(pending, target)
    finally:
        if temporary is not None:
            remove_bake(temporary)
    # Collision triangles, in game coordinates.
    vertices, indices = [], []
    for ob in bpy.data.collections['Colisao'].objects:
        if ob.type != 'MESH':
            continue
        mesh = ob.data
        mesh.calc_loop_triangles()
        base = len(vertices)
        matrix = ob.matrix_world
        vertices.extend(to_game(matrix @ v.co) for v in mesh.vertices)
        for tri in mesh.loop_triangles:
            indices.extend(base+i for i in tri.vertices)
    meta = json.loads(bpy.data.texts['marcadores.json'].as_string())
    points = {}
    for ob in bpy.data.collections['Marcadores'].objects:
        points[ob.name] = to_game(ob.matrix_world.translation)
    meta['points'] = dict(sorted(points.items()))
    meta['vertices'] = vertices
    meta['indices'] = indices
    with open(os.path.join(OUT, 'runtime.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, separators=(',', ':'))
    print(f'Exportado: {len(art.objects)} objetos de arte, {len(indices)//3} triangulos de colisao, {len(points)} marcadores')


if _RUN_EXPORT:
    export(globals().get('SAVE_BLEND', True))
