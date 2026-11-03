"""Offline vertex lighting for Bairro Arterial; run inside Blender.

blender --background Assets/Maps/BairroArterial/BairroArterial.blend --python scripts/bake_distrito.py

The editable scene stays intact. The export receives a sampling grid, warm sun
shadows and cool sky/contact occlusion. UV.y = 1.5 marks prelit vertices; UV.x
and the animated water/emissive patterns keep their original meaning.
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SPACING = 0.85
SKY_SAMPLES = 24
SUN = Vector((-0.42, -0.38, 0.82)).normalized()  # Blender coordinates
MAX_CORNERS = 48000  # safely below raylib's unsigned-short index limit


def bake_objects(art):
    """Return temporary export meshes. Never modify source mesh/color data."""
    started = time.monotonic()
    points, triangles = [], []
    for ob in art.objects:
        if ob.type != 'MESH':
            continue
        mesh = ob.data
        mesh.calc_loop_triangles()
        base = len(points)
        points.extend(ob.matrix_world @ v.co for v in mesh.vertices)
        uv = mesh.uv_layers.active.data
        for tri in mesh.loop_triangles:
            # Water and light bulbs must not cast opaque shadows.
            if int(uv[tri.loops[0]].uv.x) not in (5, 13, 17):
                triangles.append(tuple(base + i for i in tri.vertices))
    bvh = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    sky = []
    for i in range(SKY_SAMPLES):
        r = math.sqrt((i + 0.5) / SKY_SAMPLES)
        phi = i * 2.399963229728653
        sky.append(Vector((r * math.cos(phi), r * math.sin(phi), math.sqrt(1-r*r))))
    tangent = SUN.cross(Vector((0, 0, 1))).normalized()
    bitangent = SUN.cross(tangent)
    sun_rays = [SUN] + [(SUN + 0.018 * (math.cos(i*math.tau/4)*tangent +
                 math.sin(i*math.tau/4)*bitangent)).normalized() for i in range(4)]
    cache = {}

    def irradiance(p, n):
        key = tuple(round(v, 3) for v in (*p, *n))
        if key in cache:
            return cache[key]
        origin = p + n * 0.035
        axis = Vector((0, 0, 1)) if abs(n.z) < 0.95 else Vector((1, 0, 0))
        t = n.cross(axis).normalized()
        b = n.cross(t)
        visible, contact = 0.0, 0.0
        for d in sky:
            ray = t*d.x + b*d.y + n*d.z
            hit, _, _, distance = bvh.ray_cast(origin, ray, 120.0)
            if hit is None:
                visible += 1.0
            else:
                contact += max(0.0, 1.0 - distance/3.0)
        visible /= SKY_SAMPLES
        ao = 1.0 - 0.30 * contact / SKY_SAMPLES
        ndotl = max(0.0, n.dot(SUN))
        direct = 0.0
        if ndotl > 0:
            direct = sum(bvh.ray_cast(origin, ray, 600.0)[0] is None for ray in sun_rays) / len(sun_rays)
        # Broad ground fill keeps covered routes readable. Sky and sun have
        # distinct colors, with no baked albedo or runtime light counted twice.
        hemi = 0.78 + 0.22 * max(0.0, n.z)
        result = tuple(ao * (0.23*fill + 0.47*visible*hemi*cool + 0.34*ndotl*direct*warm)
                       for fill, cool, warm in zip((1.0, 0.94, 0.90), (0.91, 0.96, 1.06), (1.08, 1.02, 0.90)))
        cache[key] = result
        return result

    output = []
    coll = bpy.data.collections.new('_LightingExport')
    bpy.context.scene.collection.children.link(coll)
    try:
        for ob in art.objects:
            if ob.type != 'MESH':
                continue
            verts, faces, colors, uvs, smooth = [], [], [], [], []
            part = 0

            def flush():
                nonlocal verts, faces, colors, uvs, smooth, part
                if not faces:
                    return
                mesh = bpy.data.meshes.new(f'{ob.name}.light.{part}')
                mesh.from_pydata(verts, [], faces)
                color = mesh.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
                color.data.foreach_set('color', colors)
                mesh.color_attributes.active_color = color
                mesh.uv_layers.new(name='UVMap').data.foreach_set('uv', uvs)
                mesh.polygons.foreach_set('use_smooth', smooth)
                mesh.update()
                obj = bpy.data.objects.new(mesh.name, mesh)
                coll.objects.link(obj)
                output.append(obj)
                verts, faces, colors, uvs, smooth = [], [], [], [], []
                part += 1

            mesh = ob.data
            source_color = mesh.color_attributes.active_color.data
            source_uv = mesh.uv_layers.active.data
            normal_matrix = ob.matrix_world.to_3x3().inverted().transposed()
            for poly in mesh.polygons:
                loops = list(poly.loop_indices)
                ps = [ob.matrix_world @ mesh.vertices[mesh.loops[i].vertex_index].co for i in loops]
                ns = [(normal_matrix @ (mesh.vertices[mesh.loops[i].vertex_index].normal if poly.use_smooth else poly.normal)).normalized() for i in loops]
                cs = [tuple(source_color[i].color) for i in loops]
                pat = source_uv[loops[0]].uv.x
                lit = int(pat) not in (5, 13)
                # Bilinear grids preserve quads, including narrow railings.
                # Small curved caps retain their original vertex sampling.
                spacing = 3.0 if max(abs(p.x) for p in ps) > 85 or max(abs(p.y) for p in ps) > 110 else SPACING

                def emit(samples):
                    if len(verts) + len(samples) > MAX_CORNERS:
                        flush()
                    center = sum((p for p, _, _ in samples), Vector()) / len(samples)
                    start = len(verts)
                    for p, n, c in samples:
                        # Move ray origins a little into the face to avoid the
                        # neighboring face at shared corners causing black seams.
                        sample = p.lerp(center, min(0.08, 0.025/max((center-p).length, 0.001)))
                        light = irradiance(sample, n) if lit else (1, 1, 1)
                        verts.append(tuple(p))
                        colors.extend((*[min(1.0, c[k]*light[k]) for k in range(3)], c[3]))
                        uvs.extend((pat, 1.5))
                    faces.append(tuple(range(start, len(verts))))
                    smooth.append(poly.use_smooth)

                def sample(weights):
                    p = sum((v*w for v, w in zip(ps, weights)), Vector())
                    n = sum((v*w for v, w in zip(ns, weights)), Vector()).normalized()
                    c = tuple(sum(v[k]*w for v, w in zip(cs, weights)) for k in range(4))
                    return p, n, c

                if len(ps) == 4 and lit:
                    nu = max(1, math.ceil(max((ps[1]-ps[0]).length, (ps[2]-ps[3]).length)/spacing))
                    nv = max(1, math.ceil(max((ps[3]-ps[0]).length, (ps[2]-ps[1]).length)/spacing))
                    for y in range(nv):
                        for x in range(nu):
                            emit([sample(((1-u)*(1-v), u*(1-v), u*v, (1-u)*v))
                                  for u, v in ((x/nu,y/nv), ((x+1)/nu,y/nv), ((x+1)/nu,(y+1)/nv), (x/nu,(y+1)/nv))])
                elif len(ps) <= 4 or not lit:
                    emit(list(zip(ps, ns, cs)))
                else:
                    for j in range(1, len(ps)-1):
                        emit([(ps[k], ns[k], cs[k]) for k in (0, j, j+1)])
            flush()
            print(f'Bake {ob.name}: {len(output)} chunks, {len(cache)} samples, {time.monotonic()-started:.1f}s', flush=True)
        return coll, output
    except BaseException:
        remove_bake(coll)
        raise


def remove_bake(coll):
    for ob in list(coll.objects):
        mesh = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    bpy.data.collections.remove(coll)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(__file__))
    from export_distrito import export
    export(save_blend=False)
