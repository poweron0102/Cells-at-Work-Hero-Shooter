"""Exporta um mapa do Blender para o jogo.

Salva a fonte editavel em referencias/blender/<Pasta>.blend e gera em Assets/Maps/<Pasta>/:
  <Pasta>.glb            arte (cores por vertice + padrao do shader em UV.x)
  runtime.json           colisao (triangulos), marcadores, rotas e metadados

O mapa vem de MAP no exec(...), de ``-- --map chave`` ou do texto ``mapa.txt`` que o build
grava na cena (o .blend sabe qual mapa e). Sem nada disso, exporta o Bairro Arterial.

Uso no Blender aberto (depois de build_distrito.py ou abrindo o .blend):
    exec(open(r'<repo>/referencias/scripts/mapa/export_distrito.py', encoding='utf-8').read(), {'REPO': r'<repo>'})
Em segundo plano:
    blender --background referencias/blender/Timo.blend --python referencias/scripts/mapa/export_distrito.py
"""
import json
import os
import sys

import bpy

REPO = globals().get('REPO') or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FOLDERS = {'bairro': 'BairroArterial', 'timo': 'Timo', 'medula': 'MedulaOssea', 'coracao': 'Coracao'}


def chosen_map():
    if globals().get('MAP'):
        return globals()['MAP']
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if '--map' in argv and argv.index('--map')+1 < len(argv):
        return argv[argv.index('--map')+1]
    text = bpy.data.texts.get('mapa.txt')
    return text.as_string().strip() if text else 'bairro'


MAP = chosen_map()
FOLDER = FOLDERS[MAP]
OUT = os.path.join(REPO, 'Assets', 'Maps', FOLDER)


def to_game(v):
    return (round(v[0], 4), round(v[2], 4), round(-v[1], 4))


def export(save_blend=True):
    os.makedirs(OUT, exist_ok=True)
    if save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(REPO, 'referencias', 'blender', f'{FOLDER}.blend'), copy=True)
    art = bpy.data.collections['Arte']
    bpy.ops.object.select_all(action='DESELECT')
    for ob in art.objects:
        if ob.type == 'MESH':
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f'{FOLDER}.glb'), use_selection=True,
                              export_format='GLB', export_yup=True, export_apply=True,
                              export_vertex_color='ACTIVE', export_materials='NONE',
                              export_normals=True, export_texcoords=True)
    # Collision triangles, in game coordinates.
    def triangles(name):
        vertices, indices = [], []
        coll = bpy.data.collections.get(name)
        for ob in (coll.objects if coll else ()):
            if ob.type != 'MESH':
                continue
            mesh = ob.data
            mesh.calc_loop_triangles()
            base = len(vertices)
            matrix = ob.matrix_world
            vertices.extend(to_game(matrix @ v.co) for v in mesh.vertices)
            for tri in mesh.loop_triangles:
                indices.extend(base+i for i in tri.vertices)
        return vertices, indices
    vertices, indices = triangles('Colisao')
    screen_vertices, screen_indices = triangles('ColisaoVazada')
    meta = json.loads(bpy.data.texts['marcadores.json'].as_string())
    points = {}
    for ob in bpy.data.collections['Marcadores'].objects:
        points[ob.name] = to_game(ob.matrix_world.translation)
    meta['points'] = dict(sorted(points.items()))
    meta['vertices'] = vertices
    meta['indices'] = indices
    if screen_indices:
        meta['screen_vertices'] = screen_vertices
        meta['screen_indices'] = screen_indices
    with open(os.path.join(OUT, 'runtime.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, separators=(',', ':'))
    print(f'Exportado: {len(art.objects)} objetos de arte, {len(indices)//3} triangulos de colisao, {len(points)} marcadores')


if __name__ == '__main__' or 'REPO' in globals():
    export(globals().get('SAVE_BLEND', True))
