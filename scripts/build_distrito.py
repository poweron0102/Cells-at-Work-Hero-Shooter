"""Monta o Bairro Arterial no Blender (cena nova, sem reaproveitar o mapa antigo).

Executar no Blender aberto (MCP ou console Python):
    exec(open(r'<repo>/scripts/build_distrito.py', encoding='utf-8').read(), {'REPO': r'<repo>'})
ou em segundo plano:
    blender --background --factory-startup --python scripts/build_distrito.py

Coordenadas: o layout e escrito no espaco do JOGO (x leste, y cima, z sul).
No Blender: X = x, Y = -z, Z = y (norte = +Y). O exportador glTF (+Y up)
devolve exatamente as coordenadas do jogo.
"""
import importlib
import json
import math
import os
import sys

import bpy

REPO = globals().get('REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
import distrito_geo as geo_module  # noqa: E402
importlib.reload(geo_module)
from distrito_geo import *  # noqa: E402,F401,F403
import distrito_layout  # noqa: E402
importlib.reload(distrito_layout)

MAX_CORNERS = 60000


def to_blender(p):
    return (p[0], -p[2], p[1])


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.texts):
        for item in list(block):
            block.remove(item)


def collection(name, hide=False):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    coll.hide_render = hide
    return coll


def make_object(name, verts, faces, coll):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([to_blender(v) for v in verts], [], [f[0] for f in faces])
    mesh.validate(clean_customdata=False)
    color = mesh.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
    uv = mesh.uv_layers.new(name='UVMap')
    cols, uvs, smooth = [], [], []
    for (idx, rgb, pat, sm) in faces:
        c = (rgb[0]/255, rgb[1]/255, rgb[2]/255, 1.0)
        for _ in idx:
            cols.extend(c)
            uvs.extend((pat+.5, .5))
        smooth.append(sm)
    color.data.foreach_set('color', cols)
    uv.data.foreach_set('uv', uvs)
    mesh.polygons.foreach_set('use_smooth', smooth)
    mesh.color_attributes.active_color = color
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    coll.objects.link(ob)
    return ob


def emit_groups(geo, coll):
    count = 0
    for name, group in geo.groups.items():
        if not group.faces:
            continue
        chunk, corners, part = [], 0, 0

        def flush():
            nonlocal chunk, corners, part, count
            if not chunk:
                return
            remap, verts, faces = {}, [], []
            for idx, rgb, pat, sm in chunk:
                new = []
                for i in idx:
                    if i not in remap:
                        remap[i] = len(verts)
                        verts.append(group.verts[i])
                    new.append(remap[i])
                faces.append((new, rgb, pat, sm))
            make_object(f'{name}.{part:02}', verts, faces, coll)
            count += len(faces)
            chunk, corners, part = [], 0, part+1
        for face in group.faces:
            if corners+len(face[0]) > MAX_CORNERS:
                flush()
            chunk.append(face)
            corners += len(face[0])
        flush()
    return count


def emit_collision(geo, coll):
    verts, faces, index = [], [], {}
    for tri in geo.collision:
        f = []
        for p in tri:
            key = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
            if key not in index:
                index[key] = len(verts)
                verts.append(key)
            f.append(index[key])
        if len(set(f)) == 3:
            faces.append(f)
    mesh = bpy.data.meshes.new('Colisao')
    mesh.from_pydata([to_blender(v) for v in verts], [], faces)
    ob = bpy.data.objects.new('Colisao', mesh)
    coll.objects.link(ob)
    ob.display_type = 'WIRE'
    ob.hide_render = True
    return len(faces)


def emit_markers(markers, coll):
    for name, data in markers['points'].items():
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = 'SPHERE'
        empty.empty_display_size = .6
        empty.location = to_blender(data)
        coll.objects.link(empty)
    text = bpy.data.texts.new('marcadores.json')
    text.write(json.dumps({k: v for k, v in markers.items() if k != 'points'}, indent=1))


def setup_view():
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new('World')
    scene.world = world
    world.color = (.86, .82, .74)
    sun = bpy.data.lights.new('Sol', 'SUN')
    sun.energy = 3.5
    ob = bpy.data.objects.new('Sol', sun)
    ob.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    scene.collection.objects.link(ob)
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.shading.color_type = 'VERTEX'
                    space.clip_end = 1500
                    space.overlay.show_relationship_lines = False


def build(only=None):
    clear_scene()
    geo = Geo()
    markers = distrito_layout.build(geo, only)
    art = collection('Arte')
    col = collection('Colisao', hide=True)
    marks = collection('Marcadores', hide=True)
    faces = emit_groups(geo, art)
    tris = emit_collision(geo, col)
    emit_markers(markers, marks)
    setup_view()
    print(f'Bairro Arterial: {faces} faces visiveis, {tris} triangulos de colisao, '
          f'{len(art.objects)} objetos de arte')
    return geo, markers


if __name__ == '__main__' or 'REPO' in globals():
    build(globals().get('ONLY'))
