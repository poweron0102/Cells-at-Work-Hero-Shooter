"""Ossos dos dedos da Macrófaga (malha do Tripo) e pesos de pele das mãos.

A malha veio com a mão inteira presa ao osso ``hand.L/R``: a personagem não conseguia fechar a mão
em volta do cabo nem da bomba. Aqui cada dedo ganha dois ossos (base e ponta) e o polegar também,
posicionados pelos próprios vértices: acima da linha dos nós, os dedos da malha já são ilhas
separadas, então cada ilha vira um dedo. Os pesos de ``hand.X`` desses vértices são redistribuídos
entre a mão e as falanges com transições suaves nas juntas. Idempotente: não faz nada se os ossos
já existirem.

Eixos (iguais aos da mão no esqueleto): Y ao longo do dedo, X para o lado do polegar e Z para o
dorso. Fechar = girar em torno do X local com ângulo negativo.
"""
import bpy
from mathutils import Vector

FINGERS = ('index', 'middle', 'ring', 'pinky')
KNUCKLE, SPLIT, THUMB_SPLIT = 0.10, 0.12, 0.09  # ao longo do osso da mão (m)


def _components(me, adj, sel):
    seen, out = set(), []
    for i in sel:
        if i in seen:
            continue
        stack, comp = [i], []
        seen.add(i)
        while stack:
            j = stack.pop()
            comp.append(j)
            for k in adj[j]:
                if k in sel and k not in seen:
                    seen.add(k)
                    stack.append(k)
        out.append(comp)
    return out


def _centroid(me, ids):
    return sum((me.vertices[i].co for i in ids), Vector()) / len(ids)


def _smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def finger_names(side):
    names = [f'{f}.{k}.{side}' for f in FINGERS for k in (1, 2)]
    return names + [f'thumb.{k}.{side}' for k in (1, 2)]


def add_fingers(rig, body):
    if 'index.1.L' in rig.data.bones:
        return False
    me = body.data
    adj = {v.index: set() for v in me.vertices}
    for e in me.edges:
        a, b = e.vertices
        adj[a].add(b)
        adj[b].add(a)
    plan = {}
    for side in ('L', 'R'):
        hb = rig.data.bones[f'hand.{side}']
        head = hb.head_local.copy()
        ax = (hb.tail_local - hb.head_local).normalized()
        gi = body.vertex_groups[f'hand.{side}'].index
        weight = {}
        for v in me.vertices:
            for g in v.groups:
                if g.group == gi and g.weight > 0:
                    weight[v.index] = g.weight
        t = {i: (me.vertices[i].co - head).dot(ax) for i in weight}
        comps = _components(me, adj, {i for i in weight if t[i] > SPLIT})
        comps = sorted(comps, key=len, reverse=True)[:4]
        if len(comps) != 4:
            raise ValueError(f'mão {side}: {len(comps)} dedos encontrados')
        # O polegar se separa antes dos outros dedos: é a segunda maior ilha nessa altura.
        thumb = sorted(_components(me, adj, {i for i in weight if t[i] > THUMB_SPLIT}), key=len, reverse=True)[1]
        thumb_c = _centroid(me, thumb)
        comps.sort(key=lambda c: (_centroid(me, c) - thumb_c).length)  # do indicador ao mínimo
        chains = {}
        for name, comp in zip(FINGERS, comps):
            tip_t = max(t[i] for i in comp)
            low = min(t[i] for i in comp)
            near = [i for i in comp if t[i] < low + 0.012]
            base = _centroid(me, near)
            base = base - ax * ((base - head).dot(ax) - KNUCKLE)
            mid_t = KNUCKLE + (tip_t - KNUCKLE) * 0.5
            mid = _centroid(me, [i for i in comp if abs(t[i] - mid_t) < 0.008] or comp)
            tip = _centroid(me, [i for i in comp if t[i] > tip_t - 0.008])
            chains[name] = (base, mid, tip + (tip - mid).normalized() * 0.004, comp)
        tip_t = max(t[i] for i in thumb)
        low = min(t[i] for i in thumb)
        start = _centroid(me, [i for i in thumb if t[i] < low + 0.01])
        mid = _centroid(me, [i for i in thumb if abs(t[i] - (low + tip_t) / 2) < 0.008] or thumb)
        tip = _centroid(me, [i for i in thumb if t[i] > tip_t - 0.008])
        root = start - (mid - start).normalized() * 0.03  # metacarpo dentro da palma
        chains['thumb'] = (root, mid, tip + (tip - mid).normalized() * 0.004, thumb)
        plan[side] = (hb.name, ax, chains, weight, t)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    for side, (hand, _ax, chains, _w, _t) in plan.items():
        back = Vector(rig.data.bones[hand].matrix_local.col[2][:3])
        for name, (base, mid, tip, _c) in chains.items():
            parent = eb[hand]
            for k, (h, tl) in enumerate(((base, mid), (mid, tip)), start=1):
                bone = eb.new(f'{name}.{k}.{side}')
                bone.head, bone.tail = h, tl
                bone.align_roll(back)
                bone.parent = parent
                bone.use_deform = True
                parent = bone
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'

    # Pesos: a parcela de hand.X de cada vértice de dedo vai para a mão e as falanges.
    for side, (hand, ax, chains, weight, t) in plan.items():
        head = rig.data.bones[hand].head_local
        groups = {n: body.vertex_groups.get(n) or body.vertex_groups.new(name=n) for n in finger_names(side)}
        hand_group = body.vertex_groups[hand]
        owner = {}
        for name, (_b, _m, _t, comp) in chains.items():
            for i in comp:
                owner[i] = name
        # Vértices entre a palma e a separação dos dedos: o dedo mais próximo (lateralmente).
        for i in weight:
            if i in owner or t[i] < KNUCKLE - 0.012:
                continue
            p = me.vertices[i].co
            best, dist = None, 9.0
            for name, (b, m, _t, _c) in chains.items():
                d = ((p - b) - (m - b).normalized() * (p - b).dot((m - b).normalized())).length
                if name == 'thumb':
                    d *= 1.4
                if d < dist:
                    best, dist = name, d
            if dist < 0.016:
                owner[i] = best
        for i, name in owner.items():
            b, m, _tip, _c = chains[name]
            d = (m - b).normalized()
            s = (me.vertices[i].co - b).dot(d)  # distância ao longo do dedo a partir da base
            seg = (m - b).length
            w_finger = _smooth(-0.012, 0.006, s) if name != 'thumb' else _smooth(-0.02, 0.01, s)
            w_tip = _smooth(seg - 0.006, seg + 0.006, s)
            total = weight[i]
            parts = {hand: total * (1 - w_finger), f'{name}.1.{side}': total * w_finger * (1 - w_tip),
                     f'{name}.2.{side}': total * w_finger * w_tip}
            hand_group.add([i], parts[hand], 'REPLACE')
            for g, wv in parts.items():
                if g != hand:
                    if wv > 1e-4:
                        groups[g].add([i], wv, 'REPLACE')
    return True
