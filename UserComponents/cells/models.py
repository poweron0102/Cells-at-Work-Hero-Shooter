"""Personagens 3D do Blender com clipes esqueléticos ou animação por partes.

Cada personagem é um GLB com uma malha por parte (body, arm_l, arm_r, leg_l, leg_r, weapon,
tail, tentacles_*, ...) e um JSON com o índice da malha no raylib, o pivô da articulação e a
família de animação.  Nada é carregado na importação: o Model é carregado na primeira vez que
um personagem é desenhado (precisa de contexto OpenGL) e fica em cache por chave, compartilhado
por todas as instâncias.

Personagens com esqueleto (hemácia, macrófago e plaqueta; referencias/scripts/personagens/
rig_tripo.py) trazem clipes Idle/Walk e um clipe de ação ("action_clip"), textura de cor no
material e, no macrófago, a arma presa ao osso da mão ("mount.bone").
"""
import json
import math
import struct
import time
from pathlib import Path

import numpy as np
import pyray as rl
import raylib as _raw

from . import model_lighting

ASSET_DIR = Path(__file__).resolve().parents[2] / 'Assets' / 'Characters3D'
CHARACTER_KEYS = ('neutrophil', 'macrophage', 'b_cell', 'killer_t', 'pneumococcus', 'staphylococcus',
                  'pseudomonas', 'streptococcus', 'red_blood_cell', 'platelet')
_ffi = _raw.ffi
_DrawMesh = _raw.DrawMesh
_WHITE = (255, 255, 255, 255)


def read_glb(path):
    """Lê um .glb e devolve (json, bin) sem depender de GPU."""
    data = Path(path).read_bytes()
    magic, _, length = struct.unpack_from('<III', data, 0)
    if magic != 0x46546C67:
        raise ValueError(f'{path} não é GLB')
    off, js, binc = 12, None, b''
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        off += 8
        if ctype == 0x4E4F534A:
            js = json.loads(data[off:off + clen])
        elif ctype == 0x004E4942:
            binc = data[off:off + clen]
        off += clen
    return js, binc


def raylib_mesh_indices(gltf):
    """Mesma ordem do LoadGLTF do raylib: nós em ordem, só nós com malha, um Mesh por primitivo
    de triângulos.  Devolve ({nome_do_nó: [índices]}, total)."""
    out, idx = {}, 0
    for node in gltf.get('nodes', []):
        if 'mesh' not in node:
            continue
        ids = []
        for prim in gltf['meshes'][node['mesh']]['primitives']:
            if prim.get('mode', 4) == 4:
                ids.append(idx)
                idx += 1
        out[node.get('name', '')] = ids
    return out, idx


def load_meta(key):
    return json.loads((ASSET_DIR / f'{key}.json').read_text(encoding='utf-8'))


# --------------------------------------------------------------------------------------
# Matemática mínima (Python puro) para montar as matrizes das partes
# --------------------------------------------------------------------------------------

def _rot(ax, ay, az):
    """R = Rz @ Ry @ Rx (vetores-coluna)."""
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    return ((cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
            (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
            (-sy, cy * sx, cy * cx))


def _about(pivot, r):
    """Matriz 3x4 (rotação r em torno do pivô) como tupla ((r, t))."""
    px, py, pz = pivot
    t = (px - (r[0][0] * px + r[0][1] * py + r[0][2] * pz),
         py - (r[1][0] * px + r[1][1] * py + r[1][2] * pz),
         pz - (r[2][0] * px + r[2][1] * py + r[2][2] * pz))
    return r, t


def _compose(a, b):
    """a ∘ b (aplica b, depois a)."""
    (ra, ta), (rb, tb) = a, b
    r = tuple(tuple(sum(ra[i][k] * rb[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    t = tuple(sum(ra[i][k] * tb[k] for k in range(3)) + ta[i] for i in range(3))
    return r, t


def _to_matrix(m):
    (r, t) = m
    p = _ffi.new('Matrix *', (r[0][0], r[0][1], r[0][2], t[0], r[1][0], r[1][1], r[1][2], t[1],
                              r[2][0], r[2][1], r[2][2], t[2], 0.0, 0.0, 0.0, 1.0))
    return p


_IDENTITY = (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))


# --------------------------------------------------------------------------------------
# Skinning na GPU: poses do raylib (Transform no espaço do modelo) -> matrizes de pele
# --------------------------------------------------------------------------------------

def _poses(poses, frames, bones):
    """``ModelAnimPose`` x quadros -> (quadros, ossos, 10): translação, rotação xyzw, escala."""
    out = np.empty((frames, bones, 10), np.float32)
    for f in range(frames):
        out[f] = np.frombuffer(_ffi.buffer(poses[f], bones * 40), np.float32).reshape(bones, 10)
    return out


def _transforms(p):
    """(..., 10) -> (..., 4, 4) com vetores-coluna (T * R * S)."""
    x, y, z, w = p[..., 3], p[..., 4], p[..., 5], p[..., 6]
    m = np.zeros(p.shape[:-1] + (4, 4), np.float32)
    m[..., 0, 0] = 1 - 2 * (y * y + z * z)
    m[..., 0, 1] = 2 * (x * y - z * w)
    m[..., 0, 2] = 2 * (x * z + y * w)
    m[..., 1, 0] = 2 * (x * y + z * w)
    m[..., 1, 1] = 1 - 2 * (x * x + z * z)
    m[..., 1, 2] = 2 * (y * z - x * w)
    m[..., 2, 0] = 2 * (x * z - y * w)
    m[..., 2, 1] = 2 * (y * z + x * w)
    m[..., 2, 2] = 1 - 2 * (x * x + y * y)
    m[..., :3, :3] *= p[..., None, 7:10]
    m[..., :3, 3] = p[..., :3]
    m[..., 3, 3] = 1.0
    return m


def _blend_poses(a, b, k):
    """Mistura duas poses (ossos, 10): translação/escala lineares, rotação nlerp."""
    qa, qb = a[:, 3:7], b[:, 3:7]
    qb = np.where((qa * qb).sum(1, keepdims=True) < 0, -qb, qb)
    out = a + (b - a) * k
    q = qa + (qb - qa) * k
    out[:, 3:7] = q / np.linalg.norm(q, axis=1, keepdims=True)
    return out


def _slash(a):
    """Golpe: prepara (braço sobe à frente/acima) e corta para baixo. Ângulo em X (rad)."""
    if a <= 0.0:
        return 0.0, 0.0
    if a < 0.35:
        k = a / 0.35
        return -2.3 * (1 - (1 - k) ** 2), 0.25 * k
    if a < 0.65:
        k = (a - 0.35) / 0.3
        return -2.3 + 2.75 * k * k * (3 - 2 * k), 0.25 - 0.55 * k
    k = (a - 0.65) / 0.35
    return 0.45 * (1 - k), -0.3 * (1 - k)


# --------------------------------------------------------------------------------------
# Rig compartilhado por chave
# --------------------------------------------------------------------------------------

class _Part:
    __slots__ = ('name', 'mesh', 'texture', 'swing', 'pivot', 'parent', 'phase', 'amp', 'action', 'side')

    def __init__(self, entry, mesh, texture):
        self.name = entry['name']
        self.mesh = mesh
        self.texture = texture
        self.swing = entry.get('swing', 'static')
        self.pivot = tuple(entry.get('pivot', (0.0, 0.0, 0.0)))
        self.parent = entry.get('parent', 'body')
        self.phase = float(entry.get('phase', 0.0))
        self.amp = float(entry.get('amp', 0.5))
        self.action = entry.get('action')
        self.side = 1.0 if self.pivot[0] >= 0 else -1.0


class _Rig:
    def __init__(self, key):
        self.key = key
        meta = load_meta(key)
        self.height = meta['height']
        self.model = rl.load_model(str(ASSET_DIR / f'{key}.glb'))
        if self.model.meshCount != meta.get('mesh_count', self.model.meshCount):
            raise RuntimeError(f'{key}: GLB tem {self.model.meshCount} malhas, JSON espera {meta["mesh_count"]}')
        self.material = rl.load_material_default()
        self.default_texture = _ffi.new('Texture *', self.material.maps[0].texture)[0]
        # Textura de cor de cada malha (a do material do GLB; sem textura = branca 1x1 do raylib).
        self.textures = []
        self.owned_textures = {}
        for i in range(self.model.meshCount):
            maps = self.model.materials[self.model.meshMaterial[i]].maps
            tex = maps[0].texture
            if tex.id != self.default_texture.id and tex.id not in self.owned_textures:
                # Mipmaps: as multidões aparecem pequenas e de longe.
                _raw.GenTextureMipmaps(_ffi.addressof(maps[0], 'texture'))
                rl.set_texture_filter(maps[0].texture, rl.TextureFilter.TEXTURE_FILTER_TRILINEAR)
                self.owned_textures[tex.id] = maps[0].texture
            self.textures.append(maps[0].texture)
        self.animations = None
        self.clips = {}
        self.poses = {}
        self.skins = {}
        self.skin = None
        self.skin_ptr = None
        self.animation_count = 0
        self.seconds = meta.get('clip_seconds', {})
        self.action_clip = meta.get('action_clip')
        self.action_mode = meta.get('action_mode', 'blend')
        self.walk_rate = float(meta.get('walk_rate', 1.0))
        if meta.get('clips'):
            count = _ffi.new('int *')
            self.animations = rl.load_model_animations(str(ASSET_DIR / f'{key}.glb'), count)
            self.animation_count = count[0]
            for i in range(self.animation_count):
                clip = self.animations[i]
                if rl.is_model_animation_valid(self.model, clip):
                    self.clips[_ffi.string(clip.name).decode()] = clip
            if set(self.clips) != set(meta['clips']):
                self.unload()
                raise ValueError(f'{key}: clipes incompatíveis com o esqueleto')
            self._init_skinning()
        parts = [_Part(e, self.model.meshes[e['mesh']], self.textures[e['mesh']]) for e in meta['parts']]
        # Pais antes dos filhos (a arma usa a matriz do braço direito).
        order = {p.name: i for i, p in enumerate(parts)}
        parts.sort(key=lambda p: (p.parent != 'body' and p.parent in order, order[p.name]))
        self.parts = parts
        self.has_weapon = any(p.swing == 'weapon' for p in parts)
        self.identity = _to_matrix(_IDENTITY)
        # Arma do herói (Assets/Weapons) presa a uma parte ou a um osso: matriz arma -> personagem
        # (no osso, arma -> pose de repouso; a matriz de pele do osso no quadro vai por cima).
        mount = meta.get('mount')
        self.mount_part = mount.get('part') if mount else None
        self.mount_bone = None
        if mount and mount.get('bone'):
            names = [_ffi.string(self.model.skeleton.bones[i].name).decode()
                     for i in range(self.model.skeleton.boneCount)]
            self.mount_bone = names.index(mount['bone'])
        self.mount = (tuple(tuple(r[:3]) for r in mount['matrix']), tuple(r[3] for r in mount['matrix'])) \
            if mount else None

    def _init_skinning(self):
        """Envia índices/pesos de osso para o VAO de cada malha (posições 7 e 8 do shader) e
        pré-calcula as matrizes de pele de todos os quadros de cada clipe."""
        bones = self.model.skeleton.boneCount
        if bones > model_lighting.MAX_BONES:
            raise RuntimeError(f'{self.key}: {bones} ossos (máximo {model_lighting.MAX_BONES})')
        for i in range(self.model.meshCount):
            mesh = self.model.meshes[i]
            if mesh.boneIndices == _ffi.NULL or mesh.vboId[7]:
                continue
            rl.rl_enable_vertex_array(mesh.vaoId)
            mesh.vboId[7] = rl.rl_load_vertex_buffer(mesh.boneIndices, mesh.vertexCount * 4, False)
            rl.rl_set_vertex_attribute(7, 4, rl.RL_UNSIGNED_BYTE, False, 0, 0)
            rl.rl_enable_vertex_attribute(7)
            mesh.vboId[8] = rl.rl_load_vertex_buffer(mesh.boneWeights, mesh.vertexCount * 16, False)
            rl.rl_set_vertex_attribute(8, 4, rl.RL_FLOAT, False, 0, 0)
            rl.rl_enable_vertex_attribute(8)
            rl.rl_disable_vertex_array()
        bind = _poses([self.model.skeleton.bindPose], 1, bones)[0]
        self.bind_inv = np.linalg.inv(_transforms(bind)).astype(np.float32)
        for name, clip in self.clips.items():
            poses = _poses(clip.keyframePoses, clip.keyframeCount, bones)
            self.poses[name] = poses
            # Linhas da matriz em sequência = layout do struct Matrix do raylib.
            self.skins[name] = np.ascontiguousarray(_transforms(poses) @ self.bind_inv, np.float32)

    def frame(self, name, cycles):
        """Quadro do clipe ``name`` após ``cycles`` voltas (a fração é a posição no laço)."""
        clip = self.clips[name]
        return (cycles % 1.0) * max(1, clip.keyframeCount - 1)

    def pose_skin(self, name, frame, work=None, work_frame=0.0, weight=0.0):
        """Matrizes de pele do quadro (``frame`` fracionário) com mistura opcional de ``work``."""
        skins = self.skins[name]
        last = len(skins) - 1
        f0 = min(int(frame), last)
        f1 = min(f0 + 1, last)
        k = frame - f0
        if work is None or weight <= 0.0:
            skin = skins[f0] if k < 1e-3 else skins[f0] + (skins[f1] - skins[f0]) * k
        else:
            a = self.poses[name][f0]
            b = self.poses[work][min(int(round(work_frame)), len(self.poses[work]) - 1)]
            skin = _transforms(_blend_poses(a, b, min(1.0, weight))) @ self.bind_inv
        self.skin = np.ascontiguousarray(skin, np.float32)
        self.skin_ptr = _ffi.cast('Matrix *', _ffi.from_buffer(self.skin))
        return self.skin

    def bone_matrix(self, index):
        """Matriz de pele do osso no quadro atual (repouso -> pose), como (r, t)."""
        b = self.skin[index]
        return ((float(b[0, 0]), float(b[0, 1]), float(b[0, 2])), (float(b[1, 0]), float(b[1, 1]), float(b[1, 2])),
                (float(b[2, 0]), float(b[2, 1]), float(b[2, 2]))), (float(b[0, 3]), float(b[1, 3]), float(b[2, 3]))

    def unload(self):
        if self.animations:
            rl.unload_model_animations(self.animations, self.animation_count)
        # O shader do material é o toon compartilhado: não deixa UnloadMaterial descarregá-lo.
        self.material.shader = rl.Shader(rl.rl_get_shader_id_default(), rl.rl_get_shader_locs_default())
        # As texturas do GLB são liberadas aqui (UnloadModel não as descarrega).
        self.material.maps[0].texture = self.default_texture
        rl.unload_material(self.material)
        for tex in self.owned_textures.values():
            rl.unload_texture(tex)
        rl.unload_model(self.model)


_RIGS = {}


def release_models():
    """Descarrega todos os modelos (chamar antes de fechar a janela, se desejado)."""
    for rig in _RIGS.values():
        if rig is not None:
            rig.unload()
    _RIGS.clear()


class CharacterModel:
    """Desenha um personagem animado proceduralmente.  API usada pelo resto do jogo:
    ``CharacterModel(hero).draw(position, yaw, phase, moving, reveal, shield, action, tint)``.

    ``draw`` não guarda estado entre chamadas: uma mesma instância pode ser compartilhada por
    vários atores/NPCs (o jogo faz isso)."""

    def __init__(self, hero):
        self.hero = hero
        self.phase = 0.0
        self.moving = False
        self.reveal = self.shield = 0

    @property
    def rig(self):
        rig = _RIGS.get(self.hero, False)
        if rig is False:
            try:
                rig = _Rig(self.hero)
            except (OSError, KeyError, RuntimeError, ValueError) as exc:
                print(f'[models] não foi possível carregar {self.hero}: {exc}', flush=True)
                rig = None
            _RIGS[self.hero] = rig
        return rig

    def draw(self, position, yaw=0, phase=0, moving=False, reveal=0, shield=0, action=0.0, tint=None, kick=0.0,
             weapon=True, cull=None, animation=None):
        """Desenha o personagem; ``kick`` (0..1) é o recuo do último disparo. Se o herói tem arma
        montada (e ``weapon``), desenha a arma na mão e devolve a posição do cano no mundo.
        ``cull`` ('front'/'back') liga o descarte de faces, usado pelos passes de contorno/silhueta."""
        self.phase, self.moving, self.reveal, self.shield = phase, moving, reveal, shield
        rig = self.rig
        if rig is None:
            return None
        now = time.perf_counter()
        walk = 1.0 if moving else 0.0
        # Defasagem pela posição: multidões (hemácias/plaquetas) não respiram em sincronia.
        t = now + (position.x * 1.37 + position.z * 0.71) % math.tau
        material = rig.material
        material.shader = model_lighting.shader()
        skinned = False
        c = _WHITE if tint is None else ((tint.r, tint.g, tint.b, tint.a) if hasattr(tint, 'r') else tuple(tint))
        color = material.maps[0].color
        color.r, color.g, color.b, color.a = c[0], c[1], c[2], (c[3] if len(c) > 3 else 255)
        if reveal and reveal > 0:
            model_lighting.set_highlight(1.0, 0.36, 0.22, min(1.0, 0.55 + 0.25 * math.sin(now * 9)))
        elif shield and shield > 0:
            model_lighting.set_highlight(0.5, 0.82, 1.0, 0.45)
        else:
            model_lighting.set_highlight(0.0, 0.0, 0.0, 0.0)
        bob = abs(math.sin(phase)) * 0.035 * walk + math.sin(t * 2.1) * 0.006 * (1 - walk)
        if rig.clips:
            self._animate(rig, phase, moving, t, action, animation)
            skinned = model_lighting.set_skin(material.shader, rig.skin_ptr, len(rig.skin))
            bob = 0.0
        rl.rl_push_matrix()
        rl.rl_translatef(position.x, position.y + bob, position.z)
        rl.rl_rotatef(180 - math.degrees(yaw), 0, 1, 0)
        if cull:
            rl.rl_draw_render_batch_active()
            rl.rl_enable_backface_culling()
            rl.rl_set_cull_face(rl.RL_CULL_FACE_FRONT if cull == 'front' else rl.RL_CULL_FACE_BACK)
        else:
            rl.rl_disable_backface_culling()
        mats = {}
        for part in rig.parts:
            material.maps[0].texture = part.texture
            if rig.clips:
                _DrawMesh(part.mesh, material, rig.identity[0])
                continue
            m = self._part_transform(part, phase, walk, t, action, kick if part.name == rig.mount_part else 0.0)
            parent = mats.get(part.parent) if part.parent != 'body' else None
            if parent is not None:
                m = parent if m is None else _compose(parent, m)
            mats[part.name] = m
            if m is None:
                _DrawMesh(part.mesh, material, rig.identity[0])
            else:
                p = _to_matrix(m)
                _DrawMesh(part.mesh, material, p[0])
        material.maps[0].texture = rig.default_texture
        if skinned:
            model_lighting.set_skin(material.shader, None)  # arma e cenário usam o mesmo shader
        muzzle = None
        if weapon and rig.mount is not None:
            muzzle = self._draw_weapon(rig, mats, kick, position, bob, yaw)
        if cull:
            rl.rl_set_cull_face(rl.RL_CULL_FACE_BACK)
        rl.rl_enable_backface_culling()
        rl.rl_pop_matrix()
        return muzzle

    def _draw_weapon(self, rig, mats, kick, position, bob, yaw):
        from .weapons import asset, draw_parts, m_apply, m_translate
        a = asset(self.hero)
        if a is None:
            return None
        if rig.mount_bone is not None:
            parent = rig.bone_matrix(rig.mount_bone)
        else:
            parent = mats.get(rig.mount_part) if rig.mount_part != 'body' else None
        base = rig.mount if parent is None else _compose(parent, rig.mount)
        if kick > 0:
            # Recuo: arma desliza para trás e o cano sobe, girando na mão.
            base = _compose(base, _compose(m_translate(0.0, 0.0, -0.05 * kick), _about((0.0, 0.0, 0.0),
                                                                                         _rot(-0.3 * kick, 0, 0))))
        st = {'bolt': kick, 'pulse': 1 - .15 * kick}
        draw_parts(a, base, st, first_person=False)
        # Cano no mundo: mesma transformação do rlTranslatef/rlRotatef acima.
        x, y, z = m_apply(base, a.muzzle)
        ang = math.pi - yaw
        c, s = math.cos(ang), math.sin(ang)
        return (position.x + x * c + z * s, position.y + bob + y, position.z - x * s + z * c)

    @staticmethod
    def _animate(rig, phase, moving, t, action, animation):
        """Pose esquelética do quadro. ``Walk`` segue a distância andada (``phase``: 2π por passada
        do jogo, vezes ``walk_rate``); ``Idle`` e o laço de trabalho seguem o relógio; um clipe pedido
        por nome (``animation``) usa ``phase`` como tempo em segundos. A ação do jogo mistura o
        clipe de ação: em laço (``blend``) ou pelo andamento do golpe, 1 - ação (``progress``)."""
        name = animation or ('Walk' if moving else 'Idle')
        if name == 'Walk':
            frame = rig.frame(name, phase * rig.walk_rate / math.tau)
        else:
            clock = t if animation is None else phase
            frame = rig.frame(name, clock / rig.seconds.get(name, 1.0))
        work_name = rig.action_clip if action > 0 and animation is None else None
        if work_name in rig.clips:
            work = rig.clips[work_name]
            if rig.action_mode == 'progress':
                work_frame = (1.0 - min(1.0, action)) * max(1, work.keyframeCount - 1)
                weight = min(1.0, action / 0.08)
            else:
                work_frame = rig.frame(work_name, t / rig.seconds.get(work_name, 1.0))
                weight = min(1.0, action * 2.0)
            rig.pose_skin(name, frame, work_name, work_frame, weight)
        else:
            rig.pose_skin(name, frame)

    @staticmethod
    def _part_transform(part, phase, walk, t, action, kick=0.0):
        """Matriz local da parte (None = identidade). ``kick`` = recuo do disparo (braço da arma)."""
        swing = part.swing
        if swing == 'static' or swing == 'weapon':
            return None
        ax = ay = az = 0.0
        if swing == 'leg':
            ax = math.sin(phase + part.phase) * part.amp * walk
        elif swing == 'arm':
            ax = math.sin(phase + part.phase) * part.amp * walk
            ax += math.sin(t * 2.1 + part.phase) * 0.035 * (1 - walk)
            az = part.side * (0.03 + 0.02 * math.sin(t * 2.1)) * (1 - walk)
            if part.action == 'slash' and action > 0:
                sx, sz = _slash(action)
                ax = ax * (1 - min(1.0, action * 4)) + sx
                az += sz * part.side * -1
            elif part.action == 'wave' and action > 0:
                # NPCs: braço sobe proporcional à "ação" (trabalho/aceno).
                ax -= 1.5 * min(1.0, action)
                az += 0.35 * min(1.0, action) * part.side
            if kick > 0:
                # Braço que segura a arma sobe um pouco a cada disparo.
                ax -= 0.28 * kick
        elif swing == 'tail':
            ay = math.sin(t * 1.7 + part.phase) * part.amp * 0.6 + math.sin(phase * 0.5) * part.amp * 0.4 * walk
            ax = math.sin(t * 1.3 + part.phase) * part.amp * 0.15
            if part.action == 'strike' and action > 0:
                sx, _ = _slash(action)
                ax += sx * 0.55
        elif swing == 'tentacle':
            az = math.sin(t * 1.9 + part.phase) * part.amp * part.side
            ax = math.sin(t * 1.3 + part.phase * 1.7) * part.amp * 0.7 + math.sin(phase) * part.amp * 0.5 * walk
        elif swing == 'head':
            ax = math.sin(t * 1.5) * 0.04 + math.sin(phase * 2) * 0.03 * walk
            if part.action == 'lunge' and action > 0:
                ax += 0.55 * math.sin(action * math.pi)
        if ax == 0.0 and ay == 0.0 and az == 0.0:
            return None
        return _about(part.pivot, _rot(ax, ay, az))
