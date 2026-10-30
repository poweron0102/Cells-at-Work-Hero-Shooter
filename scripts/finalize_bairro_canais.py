"""Presentation setup for the generated .blend, without rebuilding geometry."""
import bpy, sys
from mathutils import Vector
from pathlib import Path

folder = Path(__file__).resolve().parents[1] / 'Assets/Maps/BairroDosCanais'
bpy.ops.wm.open_mainfile(filepath=str(folder / 'BairroDosCanais.blend'))
bpy.context.preferences.filepaths.save_version = 0
# Project brick courses consistently on both wall orientations.
material = bpy.data.materials['Alvenaria • tijolo']
nodes, links = material.node_tree.nodes, material.node_tree.links
sep = next(n for n in nodes if n.type == 'SEPXYZ')
comb = next(n for n in nodes if n.type == 'COMBXYZ')
horizontal = nodes.new('ShaderNodeMath')
horizontal.operation = 'ADD'
links.new(sep.outputs['X'], horizontal.inputs[0])
links.new(sep.outputs['Y'], horizontal.inputs[1])
links.new(horizontal.outputs[0], comb.inputs['X'])
for link in list(comb.inputs['Z'].links): links.remove(link)
comb.inputs['Z'].default_value = 0
hero = bpy.data.objects['Camera • bairro']
hero.rotation_euler = (Vector((0,5,6)) - hero.location).to_track_quat('-Z','Y').to_euler()
bpy.data.objects['Camera • planta'].data.ortho_scale = 176
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.shading.type = 'SOLID'
            space.shading.color_type = 'MATERIAL'
            space.shading.show_cavity = True
            space.overlay.show_overlays = False
            space.clip_end = 500
            space.region_3d.view_perspective = 'CAMERA'
note = bpy.data.texts.get('LEIA-ME') or bpy.data.texts.new('LEIA-ME')
note.clear()
note.write((folder / 'LEIA-ME.md').read_text(encoding='utf-8'))
bpy.context.scene.camera = bpy.data.objects['Camera • bairro']
bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'BairroDosCanais.blend'))
scene = bpy.context.scene
scene.cycles.samples = 16
cameras = [('Camera • bairro','01_Bairro'),('Camera • canal','02_Canal'),('Camera • arterial','03_Arteria'),('Camera • planta','04_Planta')]
if '--only-top' in sys.argv: cameras = cameras[-1:]
for camera, filename in cameras:
    scene.camera = bpy.data.objects[camera]
    scene.render.filepath = str(folder / (filename + '.png'))
    bpy.ops.render.render(write_still=True)
scene.camera = hero
bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'BairroDosCanais.blend'))
print('FINALIZED', len(bpy.data.objects), 'objects')
