"""Armas dos heróis: GLBs de ``scripts/build_weapons.py`` + viewmodel animado em primeira pessoa.

O viewmodel é desenhado num passe próprio, depois da cena: a profundidade é limpa (a arma
nunca atravessa paredes), a câmera tem FOV fixo (a arma não deforma com o zoom/FOV do mundo)
e a luz vem de cima/atrás do ombro. A animação é procedural:

* recuo por molas (posição e rotação) com parâmetros por tipo de arma;
* ferrolho/bomba/tambor/bolsa reagindo a cada disparo; clarão no cano e cápsulas ejetadas;
* balanço do mouse (a arma "atrasa" ao girar), passo ao andar, respiração parada, pulo/queda;
* pose de corrida, recarga com troca de carregador, golpe (faca/garra/cutelo) e saque.

As mesmas peças (sem os braços de primeira pessoa) são desenhadas na mão dos personagens
por ``models.CharacterModel`` em terceira pessoa.
"""
import ctypes
import ctypes.util
import json
import math
import random
import sys
import time
from pathlib import Path

import pyray as rl
import raylib as _raw

from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3
from . import model_lighting
from .models import _rot, _about, _compose, _to_matrix, _IDENTITY
from . import shots

ASSET_DIR = Path(__file__).resolve().parents[2] / 'Assets' / 'Weapons'
WEAPON_KEYS = ('neutrophil', 'macrophage', 'b_cell', 'killer_t', 'pneumococcus', 'staphylococcus',
               'pseudomonas', 'streptococcus')
VM_FOV = 50.0
VM_LIGHT = (-0.35, 0.8, -0.45)
_DrawMesh = _raw.DrawMesh


# --------------------------------------------------------------------------------------
# Matrizes 3x4 ((r), (t)) — mesma convenção de models.py (vetores-coluna)
# --------------------------------------------------------------------------------------

def m_translate(x, y, z):
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (x, y, z)


def m_axis(axis, angle, pivot=(0.0, 0.0, 0.0)):
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / n, y / n, z / n
    c, s = math.cos(angle), math.sin(angle)
    k = 1 - c
    r = ((c + x * x * k, x * y * k - z * s, x * z * k + y * s),
         (y * x * k + z * s, c + y * y * k, y * z * k - x * s),
         (z * x * k - y * s, z * y * k + x * s, c + z * z * k))
    return _about(pivot, r)


def m_scale(s, pivot):
    px, py, pz = pivot
    return ((s, 0.0, 0.0), (0.0, s, 0.0), (0.0, 0.0, s)), (px - s * px, py - s * py, pz - s * pz)


def m_rows(rows):
    return tuple(tuple(r[:3]) for r in rows), tuple(r[3] for r in rows)


def m_apply(m, p):
    r, t = m
    return (r[0][0] * p[0] + r[0][1] * p[1] + r[0][2] * p[2] + t[0],
            r[1][0] * p[0] + r[1][1] * p[1] + r[1][2] * p[2] + t[1],
            r[2][0] * p[0] + r[2][1] * p[1] + r[2][2] * p[2] + t[2])


def m_dir(m, d):
    r = m[0]
    return (r[0][0] * d[0] + r[0][1] * d[1] + r[0][2] * d[2],
            r[1][0] * d[0] + r[1][1] * d[1] + r[1][2] * d[2],
            r[2][0] * d[0] + r[2][1] * d[1] + r[2][2] * d[2])


def smooth(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def bell(a, b, c, d, x):
    """Sobe de a a b, fica em 1, desce de c a d."""
    return smooth(a, b, x) * (1 - smooth(c, d, x))


# --------------------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------------------

class _WPart:
    __slots__ = ('name', 'mesh', 'anim', 'pivot', 'axis', 'amount', 'space', 'fp_only', 'tip')

    def __init__(self, e, mesh):
        self.name, self.mesh, self.anim = e['name'], mesh, e.get('anim', 'static')
        self.pivot = tuple(e.get('pivot', (0.0, 0.0, 0.0)))
        self.axis = tuple(e.get('axis', (0.0, 0.0, 1.0)))
        self.amount = float(e.get('amount', 0.0))
        self.space, self.fp_only = e.get('space', 'gun'), bool(e.get('fp_only'))
        self.tip = tuple(e['tip']) if e.get('tip') else None


class WeaponAsset:
    def __init__(self, key):
        meta = json.loads((ASSET_DIR / f'{key}.json').read_text(encoding='utf-8'))
        self.key, self.kind = key, meta['kind']
        self.model = rl.load_model(str(ASSET_DIR / f'{key}.glb'))
        if self.model.meshCount != meta['mesh_count']:
            raise RuntimeError(f'arma {key}: GLB tem {self.model.meshCount} malhas, JSON espera {meta["mesh_count"]}')
        self.material = rl.load_material_default()
        self.parts = [_WPart(e, self.model.meshes[e['mesh']]) for e in meta['parts']]
        self.by_name = {p.name: p for p in self.parts}
        self.fp = m_rows(meta['fp'])
        self.muzzle = tuple(meta['muzzle'])
        self.eject = tuple(meta['eject']) if meta.get('eject') else None
        self.identity = _to_matrix(_IDENTITY)

    def unload(self):
        self.material.shader = rl.Shader(rl.rl_get_shader_id_default(), rl.rl_get_shader_locs_default())
        rl.unload_material(self.material)
        rl.unload_model(self.model)


_ASSETS = {}


def asset(key):
    """Arma do herói (carregada no primeiro uso; precisa de contexto OpenGL). None se faltar."""
    a = _ASSETS.get(key, False)
    if a is False:
        try:
            a = WeaponAsset(key) if key in WEAPON_KEYS else None
        except (OSError, KeyError, RuntimeError, ValueError) as exc:
            print(f'[weapons] não foi possível carregar {key}: {exc}', flush=True)
            a = None
        _ASSETS[key] = a
    return a


def release_assets():
    for a in _ASSETS.values():
        if a is not None:
            a.unload()
    _ASSETS.clear()


def part_local(part, st):
    """Transformação animada da peça no espaço da arma (None = identidade)."""
    anim = part.anim
    if anim == 'bolt':
        k = st.get('bolt', 0.0)
        if k <= 0:
            return None
        a = part.amount * k
        return m_translate(part.axis[0] * a, part.axis[1] * a, part.axis[2] * a)
    if anim == 'mag':
        k = st.get('mag', 0.0)
        if k <= 0:
            return None
        a = part.amount * k
        return m_translate(part.axis[0] * a, part.axis[1] * a, part.axis[2] * a)
    if anim == 'pulse':
        s = st.get('pulse', 1.0)
        return None if s == 1.0 else m_scale(s, part.pivot)
    if anim == 'spin':
        ang = st.get('spin', 0.0)
        return None if not ang else m_axis(part.axis, ang, part.pivot)
    if anim == 'support':
        off = st.get('support')
        return None if not off else m_translate(*off)
    return None


def draw_parts(a, base, st, first_person, view=None):
    """Desenha as peças com a matriz ``base`` (arma -> mundo/vista)."""
    material = a.material
    material.shader = model_lighting.shader()
    c = material.maps[0].color
    c.r = c.g = c.b = c.a = 255
    for part in a.parts:
        if part.fp_only and not first_person:
            continue
        if part.space == 'view':
            if view is None:
                continue
            m = view(part)
            if m is None:
                continue
        else:
            local = part_local(part, st)
            m = base if local is None else _compose(base, local)
        _DrawMesh(part.mesh, material, _to_matrix(m)[0])


# --------------------------------------------------------------------------------------
# Vista <-> mundo
# --------------------------------------------------------------------------------------

def view_to_world(p, camera):
    """Ponto do espaço do viewmodel -> mundo, na mesma posição de tela (FOVs diferentes)."""
    t = camera.global_transform
    f, u = t.forward, t.up
    r = f.cross(u).normalize()
    k = math.tan(math.radians(camera.vfov) / 2) / math.tan(math.radians(VM_FOV) / 2)
    x, y, z = p
    w = t.position + f * z + r * (-x * k) + u * (y * k)
    return w.to_tuple


_glclear = None


def clear_depth():
    """glClear(GL_DEPTH_BUFFER_BIT) no framebuffer atual (o rlgl só expõe limpar cor+profundidade)."""
    global _glclear
    if _glclear is None:
        try:
            if sys.platform == 'win32':
                lib = ctypes.windll.opengl32
            else:
                lib = ctypes.CDLL(ctypes.util.find_library('GL') or 'libGL.so.1')
            _glclear = lib.glClear
            _glclear.argtypes = [ctypes.c_uint]
            _glclear.restype = None
        except (OSError, AttributeError):
            _glclear = False
    if _glclear:
        _glclear(0x00000100)
    return bool(_glclear)


# --------------------------------------------------------------------------------------
# Viewmodel
# --------------------------------------------------------------------------------------

class Spring:
    """Mola amortecida em 3 canais (x'' = -k(x - alvo) - c x')."""
    __slots__ = ('x', 'v', 'k', 'c')

    def __init__(self, freq, zeta=.72):
        self.x, self.v = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        self.set(freq, zeta)

    def set(self, freq, zeta=.72):
        self.k, self.c = freq * freq, 2 * zeta * freq

    def kick(self, i, peak):
        """Impulso que leva o canal a ~``peak`` no pico (amortecimento ~crítico)."""
        self.v[i] += peak * math.sqrt(self.k) * math.e

    def step(self, dt, target=(0.0, 0.0, 0.0)):
        steps = max(1, int(dt / (1 / 240)) + 1)
        h = dt / steps
        for _ in range(steps):
            for i in range(3):
                a = -self.k * (self.x[i] - target[i]) - self.c * self.v[i]
                self.v[i] += a * h
                self.x[i] += self.v[i] * h


# Por tipo de arma: deslocamento para trás (m), subida/lado/rolagem (rad), frequência da mola.
KICK = {
    'smg': dict(back=.018, up=.05, side=.02, roll=.035, freq=19, rfreq=17, flash=.045),
    'shotgun': dict(back=.075, up=.24, side=.03, roll=.09, freq=10, rfreq=9, flash=.06),
    'rifle': dict(back=.038, up=.085, side=.012, roll=.035, freq=14, rfreq=13, flash=.05),
    'burst': dict(back=.028, up=.065, side=.022, roll=.035, freq=16, rfreq=15, flash=.045),
    'organic': dict(back=.032, up=.075, side=.02, roll=.03, freq=14, rfreq=13, flash=.08),
}
HEAVY_KINDS = ('mark', 'sticky', 'acid', 'beam')
MELEE_HEROES = ('neutrophil', 'macrophage', 'killer_t', 'streptococcus')
MELEE_TIME = .42


class ViewModel(Renderable3D):
    """Primeira pessoa: braços e arma do herói local, animados e com efeitos de disparo."""

    render_order = 100

    def __init__(self, arena, camera):
        self.arena, self.cam = arena, camera
        self.vm_cam = rl.Camera3D(rl.Vector3(0, 0, 0), rl.Vector3(0, 0, 1), rl.Vector3(0, 1, 0), VM_FOV,
                                  rl.CameraProjection.CAMERA_PERSPECTIVE)
        self.pos, self.rot = Spring(16), Spring(14)
        self.rng = random.Random(11)
        self.time = 0.0
        self.last = time.perf_counter()
        self.hero = None
        self.alive = False
        self.serial = 0
        self.prev_yaw = self.prev_pitch = None
        self.prev_sec = self.prev_ability = 0.0
        self.prev_grounded, self.prev_vy = True, 0.0
        self.bob_phase = 0.0
        self.sprint = 0.0
        self.equip = 1.0
        self.fire_t = 9.0
        self.melee_t = 9.0
        self.spin = self.spin_target = 0.0
        self.flash = None
        self.shells = []
        self.pending_shell = None
        self.gun_view = _IDENTITY
        self.swoosh = []  # [(ponta, idade)] do golpe

    # -- eventos ---------------------------------------------------------------------------
    def on_fire(self, actor, a, kind):
        p = KICK.get(a.kind, KICK['smg'])
        heavy = 1.8 if kind in HEAVY_KINDS else 1.0
        rng = self.rng
        self.pos.kick(2, -p['back'] * heavy)
        self.pos.kick(1, p['back'] * .15 * heavy)
        self.rot.kick(0, p['up'] * heavy * rng.uniform(.85, 1.15))
        self.rot.kick(1, rng.uniform(-p['side'], p['side']) * heavy)
        self.rot.kick(2, rng.uniform(-p['roll'], p['roll']) * heavy)
        self.fire_t = 0.0
        self.spin_target += next((pt.amount for pt in a.parts if pt.anim == 'spin'), 0.0)
        st = shots.style_for(kind, actor.hero)
        self.flash = dict(age=0.0, life=p['flash'] * (1.5 if heavy > 1 else 1), st=st,
                          angle=rng.uniform(0, math.tau), size=st['flash_size'] * .32)
        if a.eject is not None:
            if a.kind == 'shotgun':
                self.pending_shell = .24
            else:
                self.spawn_shell(a)

    def spawn_shell(self, a):
        rng = self.rng
        self.shells.append(dict(pos=m_apply(self.gun_view, a.eject), age=0.0,
                                vel=(rng.uniform(-1.5, -1.0), rng.uniform(1.0, 1.6), rng.uniform(-.4, .1)),
                                axis=(rng.uniform(-1, 1), rng.uniform(-.3, .3), rng.uniform(-1, 1)),
                                spin=rng.uniform(14, 24), big=a.kind == 'shotgun'))
        if len(self.shells) > 24:
            del self.shells[0]

    # -- simulação -----------------------------------------------------------------------
    def simulate(self, actor, a, dt):
        self.time += dt
        if actor.hero != self.hero or not self.alive:
            self.hero = actor.hero
            self.equip = 0.0
            self.serial = actor.fire_serial
            self.prev_yaw, self.prev_pitch = actor.yaw, actor.pitch
            self.prev_sec, self.prev_ability = actor.secondary_cd, actor.ability_cd
            self.shells.clear()
            self.flash = None
        self.alive = True
        p = KICK.get(a.kind, KICK['smg'])
        self.pos.set(p['freq'])
        self.rot.set(p['rfreq'])
        if actor.fire_serial != self.serial:
            self.serial = actor.fire_serial
            self.on_fire(actor, a, actor.fire_kind)
        if actor.secondary_cd > self.prev_sec + .05 and actor.hero in MELEE_HEROES:
            self.melee_t = 0.0
        elif actor.secondary_cd > self.prev_sec + .05 and actor.hero == 'pneumococcus':
            self.pos.kick(2, .06)
            self.rot.kick(0, -.12)
        if actor.ability_cd > self.prev_ability + .05:
            self.pos.kick(1, -.03)
            self.rot.kick(0, .1)
            self.rot.kick(2, .08)
        self.prev_sec, self.prev_ability = actor.secondary_cd, actor.ability_cd
        self.equip = min(1.0, self.equip + dt / .45)
        self.fire_t += dt
        self.melee_t += dt
        if self.pending_shell is not None:
            self.pending_shell -= dt
            if self.pending_shell <= 0:
                self.pending_shell = None
                self.spawn_shell(a)

        # Balanço do mouse: a arma atrasa em relação ao giro da câmera.
        dyaw = (actor.yaw - self.prev_yaw + math.pi) % math.tau - math.pi if self.prev_yaw is not None else 0.0
        dpitch = actor.pitch - self.prev_pitch if self.prev_pitch is not None else 0.0
        self.prev_yaw, self.prev_pitch = actor.yaw, actor.pitch
        wy = max(-6.0, min(6.0, dyaw / max(dt, 1e-4)))
        wp = max(-6.0, min(6.0, dpitch / max(dt, 1e-4)))
        rot_target = (-wp * .016, wy * .014, wy * .01)
        pos_target = [wy * .0045, -wp * .004, 0.0]

        # Locomoção.
        vel = actor.body.velocity
        speed = math.hypot(vel.x, vel.z)
        grounded = bool(getattr(actor.controller, 'is_grounded', True))
        cmd = actor.controls or {}
        reloading = actor.weapon.reload_time > 0
        sprint_on = (cmd.get('sprint') and speed > 2.5 and grounded and not reloading and self.fire_t > .35
                     and self.melee_t > MELEE_TIME and not cmd.get('fire'))
        self.sprint += ((1.0 if sprint_on else 0.0) - self.sprint) * min(1.0, dt * 9)
        if grounded:
            self.bob_phase += dt * speed * 1.75
        amp = min(1.0, speed / 6.0) * (1.0 if grounded else .2) * (1 + self.sprint * .9)
        if grounded and not self.prev_grounded and self.prev_vy < -3:
            self.pos.kick(1, max(-.05, self.prev_vy * .007))
            self.rot.kick(0, max(-.08, self.prev_vy * .01))
        self.prev_grounded, self.prev_vy = grounded, vel.y
        pos_target[1] += max(-.025, min(.025, -vel.y * .0035)) if not grounded else 0.0
        self.pos.step(dt, pos_target)
        self.rot.step(dt, rot_target)
        bob = (math.sin(self.bob_phase) * .007 * amp, -abs(math.cos(self.bob_phase)) * .009 * amp,
               math.sin(self.bob_phase * 2) * .002 * amp)
        breath = math.sin(self.time * 1.7)
        return dict(speed=speed, amp=amp, bob=bob, breath=breath, reloading=reloading)

    def pose(self, actor, a, sim):
        """Matriz arma->vista e estados das peças para este quadro."""
        px, py, pz = self.pos.x
        pitch, yaw, roll = self.rot.x
        bob, breath = sim['bob'], sim['breath']
        px += bob[0]
        py += bob[1] + breath * .0012
        pz += bob[2]
        pitch += breath * .004
        roll += math.sin(self.bob_phase) * .014 * sim['amp']
        st = {}
        # Corrida: arma baixa, inclinada e virada para dentro.
        s = self.sprint
        pitch -= .38 * s
        yaw += .42 * s
        roll += .3 * s
        px += .02 * s
        py -= .035 * s
        pz -= .02 * s
        # Recarga.
        if sim['reloading']:
            p = 1 - actor.weapon.reload_time / 1.6
            w = bell(0.0, .14, .84, 1.0, p)
            roll += .5 * w
            pitch += .16 * w
            yaw += .12 * w
            px += .03 * w
            py += .01 * w
            pz -= .03 * w
            st['mag'] = bell(.12, .3, .5, .72, p)
            hand = smooth(.2, .38, p) if p < .5 else st['mag']
            mag = a.by_name.get('mag')
            if mag is not None:
                d = mag.axis
                k = mag.amount * hand
                st['support'] = (d[0] * k, d[1] * k, d[2] * k)
            else:
                k = bell(.15, .35, .6, .85, p)
                st['support'] = (0.0, -.05 * k, -.06 * k)
                st['pulse'] = 1 - .45 * bell(.1, .35, .55, .85, p)
                py -= .02 * k
            st['bolt'] = bell(.76, .82, .86, .93, p) if a.kind != 'shotgun' else 0.0
            if a.kind == 'shotgun':
                st['bolt'] = bell(.78, .84, .88, .95, p)
        # Disparo: ferrolho/bomba, bolsa orgânica, tambor.
        t = self.fire_t
        if a.kind == 'shotgun':
            k = bell(.16, .26, .3, .42, t)
            st['bolt'] = max(st.get('bolt', 0.0), k)
        else:
            k = (t / .025) if t < .025 else max(0.0, 1 - (t - .025) / .07)
            st['bolt'] = max(st.get('bolt', 0.0), k)
        if a.kind == 'shotgun' and st.get('bolt'):
            pump = a.by_name.get('pump')
            if pump is not None:
                d, k = pump.axis, pump.amount * st['bolt']
                st['support'] = (d[0] * k, d[1] * k, d[2] * k)
        if 'pulse' not in st:
            sq = (1 - t / .05) if t < .05 else 0.0
            refill = smooth(.05, .32, t) if t < .32 else 1.0
            st['pulse'] = 1 - .2 * (1 - refill) - .05 * max(0.0, sq) + .03 * math.sin(self.time * 3.1)
        self.spin += (self.spin_target - self.spin) * min(1.0, sim['dt'] * 18)
        st['spin'] = self.spin
        # Golpe.
        mt = self.melee_t
        if mt < MELEE_TIME:
            w = bell(0.0, .07, .28, MELEE_TIME, mt)
            if 'melee' in a.by_name:
                px -= .04 * w
                py -= .07 * w
                pitch -= .25 * w
                roll -= .2 * w
            else:
                # Cutelo/escopeta do Macrophage: ergue e desce num golpe largo.
                up = smooth(0.0, .11, mt) * (1 - smooth(.11, .25, mt))
                chop = smooth(.11, .25, mt) * (1 - smooth(.25, MELEE_TIME, mt))
                pitch += .42 * up - .55 * chop
                roll += .25 * up - .35 * chop
                yaw += .22 * chop
                pz += .06 * chop
                px += .04 * chop
                py += .02 * up - .03 * chop
        # Saque.
        e = self.equip
        ee = 1 - (1 - e) ** 3
        py -= (1 - ee) * .22
        pitch -= (1 - ee) * .8
        roll += (1 - ee) * .3
        rest = a.fp
        g = rest[1]
        gun_view = _compose(m_translate(px, py, pz), _compose(_about(g, _rot(-pitch, yaw, roll)), rest))
        return gun_view, st

    def melee_matrix(self, part):
        mt = self.melee_t
        if mt >= MELEE_TIME:
            return None
        k = smooth(.04, .24, mt)
        ang = 1.35 + (-1.15 - 1.35) * k - .5 * smooth(.24, MELEE_TIME, mt)
        return m_axis(part.axis, ang, part.pivot)

    # -- desenho -------------------------------------------------------------------------
    def render(self):
        now = time.perf_counter()
        dt = min(.05, max(1e-4, now - self.last))
        self.last = now
        actor = self.arena.actors.get(self.game.session.local_slot)
        if actor is None or not actor.alive:
            self.alive = False
            if actor is not None:
                actor.vm_muzzle = None
            return
        a = asset(actor.hero)
        if a is None or actor.zoom:
            actor.vm_muzzle = None
            self.alive = actor.zoom and self.alive
            return
        sim = self.simulate(actor, a, dt)
        sim['dt'] = dt
        self.gun_view, st = self.pose(actor, a, sim)
        actor.vm_muzzle = m_apply(self.gun_view, a.muzzle)

        rl.rl_draw_render_batch_active()
        cleared = clear_depth()
        rl.end_mode_3d()
        near, far = rl.rl_get_cull_distance_near(), rl.rl_get_cull_distance_far()
        rl.rl_set_clip_planes(.01, 20.0)
        rl.begin_mode_3d(self.vm_cam)
        if not cleared:
            rl.rl_disable_depth_test()
        model_lighting.shader()
        model_lighting.set_light(*VM_LIGHT)
        f = self.flash
        flash_k = 0.0
        if f is not None:
            f['age'] += dt
            flash_k = max(0.0, 1 - f['age'] / f['life'])
        if flash_k > 0:
            g = f['st']['glow']
            model_lighting.set_highlight(g[0] / 255, g[1] / 255, g[2] / 255, .28 * flash_k)
        else:
            model_lighting.set_highlight(0.0, 0.0, 0.0, 0.0)
        hurt = actor.hurt > 0
        if hurt:
            model_lighting.set_highlight(1.0, .35, .3, .25 * min(1.0, actor.hurt * 4))
        rl.rl_disable_backface_culling()
        draw_parts(a, self.gun_view, st, True, view=self.melee_matrix)
        rl.rl_enable_backface_culling()
        self.update_swoosh(a, dt)
        model_lighting.set_light(*model_lighting.WORLD_LIGHT)
        model_lighting.set_highlight(0.0, 0.0, 0.0, 0.0)
        self.draw_shells(dt)
        if flash_k > 0:
            self.draw_flash(a, f, flash_k)
        elif f is not None:
            self.flash = None
        rl.end_mode_3d()
        rl.rl_set_clip_planes(near, far)
        rl.begin_mode_3d(self.cam.rl_camera)

    def update_swoosh(self, a, dt):
        """Rastro claro da ponta da faca/garra durante o golpe."""
        melee = a.by_name.get('melee')
        trail = [(p, age + dt) for p, age in self.swoosh if age + dt < .12]
        if melee is not None and melee.tip is not None:
            m = self.melee_matrix(melee)
            if m is not None and .03 < self.melee_t < .3:
                trail.append((m_apply(m, melee.tip), 0.0))
        self.swoosh = trail
        if len(trail) < 2:
            return
        b = shots.Batch()
        for (p0, a0), (p1, a1) in zip(trail, trail[1:]):
            k = 1 - max(a0, a1) / .12
            b.add((shots.ADD, 'beam'), shots.ribbon, p0, p1, .05 * k + .01, (0.0, 0.0, 0.0), (235, 245, 255),
                  int(170 * k))
        rl.rl_draw_render_batch_active()
        rl.rl_disable_depth_mask()
        rl.rl_disable_backface_culling()
        b.flush()
        rl.rl_enable_backface_culling()
        rl.rl_enable_depth_mask()

    def draw_shells(self, dt):
        keep = []
        for s in self.shells:
            s['age'] += dt
            if s['age'] > .7:
                continue
            keep.append(s)
            vx, vy, vz = s['vel']
            vy -= 9.0 * dt
            s['vel'] = (vx, vy, vz)
            x, y, z = s['pos']
            s['pos'] = (x + vx * dt, y + vy * dt, z + vz * dt)
            ang = s['age'] * s['spin']
            ax = m_dir(m_axis(s['axis'], ang), (0.0, 0.0, 1.0))
            ln, r = (.03, .0085) if s['big'] else (.02, .0048)
            p0 = s['pos']
            p1 = (p0[0] + ax[0] * ln, p0[1] + ax[1] * ln, p0[2] + ax[2] * ln)
            body = (184, 52, 48) if s['big'] else (214, 172, 84)
            rl.draw_cylinder_ex(rl.Vector3(*p0), rl.Vector3(*p1), r, r, 7, rl.Color(*body, 255))
            q = (p0[0] + ax[0] * ln * .2, p0[1] + ax[1] * ln * .2, p0[2] + ax[2] * ln * .2)
            rl.draw_cylinder_ex(rl.Vector3(*p0), rl.Vector3(*q), r * 1.08, r * 1.08, 7, rl.Color(226, 190, 96, 255))
        self.shells = keep

    def draw_flash(self, a, f, k):
        st = f['st']
        mz = m_apply(self.gun_view, a.muzzle)
        fwd = m_dir(self.gun_view, (0.0, 0.0, 1.0))
        size = f['size'] * (.75 + .25 * k)
        tip = (mz[0] + fwd[0] * size * 1.6, mz[1] + fwd[1] * size * 1.6, mz[2] + fwd[2] * size * 1.6)
        center = (mz[0] + fwd[0] * size * .35, mz[1] + fwd[1] * size * .35, mz[2] + fwd[2] * size * .35)
        R, U = (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        b = shots.Batch()
        tex = {'star': 'star', 'ring': 'ring'}.get(st['flash'], 'glow')
        b.add((shots.ADD, 'glow'), shots.billboard, center, size * 1.8, R, U, st['glow'], int(170 * k))
        b.add((shots.ADD, 'streak'), shots.ribbon, mz, tip, size * .9, (0.0, 0.0, 0.0), st['glow'], int(220 * k))
        b.add((shots.ADD, tex), shots.billboard, center, size, R, U, st['core'], int(255 * k), f['angle'])
        if st['flash'] == 'spit':
            for i in range(3):
                q = (center[0] + fwd[0] * size * (.5 + i * .4) + math.sin(f['angle'] + i * 2.1) * size * .25,
                     center[1] + fwd[1] * size * (.5 + i * .4) + math.cos(f['angle'] + i * 2.1) * size * .25,
                     center[2] + fwd[2] * size * (.5 + i * .4))
                b.add((shots.ADD, 'core'), shots.billboard, q, size * .22, R, U, st['core'], int(230 * k))
        rl.rl_draw_render_batch_active()
        rl.rl_disable_depth_mask()
        rl.rl_disable_backface_culling()
        b.flush()
        rl.rl_enable_backface_culling()
        rl.rl_enable_depth_mask()

    def on_destroy(self):
        super().on_destroy()
        release_assets()
