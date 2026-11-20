"""Animador dos personagens com esqueleto: transições suaves e camadas por parte do corpo.

O raylib só mistura dois clipes de corpo inteiro. Trocar de clipe de um quadro para o outro
(parado/andando, salto/aterrissagem) ou mistura um disparo de corpo inteiro por cima da caminhada
(as pernas congelam a cada tiro) dá os "pulos" de pose. Aqui cada personagem tem um ``Animator``
com estado próprio:

* os pesos de Idle/Walk/Run seguem a velocidade com suavização exponencial, e Walk e Run tocam no
  mesmo ciclo de passos (o ciclo avança pela distância percorrida);
* ações (Fire, Reload, Melee, Land...) entram e saem com envelope, e uma ação reiniciada antes do fim
  ainda some aos poucos por baixo da nova;
* cada clipe controla uma parte do corpo (``layers`` no JSON): ``upper`` = tronco, braços e cabeça
  (pernas continuam na locomoção), ``lower`` = quadril e pernas, ``arms`` = ombros, braços e adereços
  do peito, presos ao peito da locomoção (tronco e cabeça seguem andando), ``full`` = tudo.

As poses do raylib estão no espaço do modelo. Para misturar partes, os ossos ficam relativos ao quadril
(``hips``); depois de misturar, voltam ao espaço do modelo e vão ao raylib como um clipe de um quadro,
que faz o skinning normalmente.
"""
import math

import numpy as np
import raylib as _raw

_ffi = _raw.ffi
FPS = 60.0  # o raylib reamostra os clipes glTF a 60 quadros por segundo
DEFAULT_LAYERS = {'Fire': 'upper', 'Reload': 'upper', 'Melee': 'upper', 'Carry': 'arms', 'Wave': 'upper',
                  'Repair': 'upper'}
EVENTS = ('Melee', 'Reload', 'Fire')     # ações disparadas por tempo desde o início (prioridade nessa ordem)
DEFAULT_STRIDE = math.tau / 2.3          # metros por ciclo (antigo passo fixo da Macrófaga)
BLEND_RATE = 9.0                         # 1/s: Idle/Walk/Run chegam a ~90% do alvo em 0,25 s
LAYER_RATE = 7.0
AIR_RATE = 11.0
FADE_IN, FADE_OUT, CROSSFADE = .07, .14, .12


def smooth(a, b, x):
    if b <= a:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def approach(value, target, rate, dt):
    return target + (value - target) * math.exp(-rate * dt)


# --------------------------------------------------------------------------------------
# Quaternions (x, y, z, w) em lote
# --------------------------------------------------------------------------------------

def qmul(a, b):
    ax, ay, az, aw = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bx, by, bz, bw = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack((aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz), axis=-1)


def qconj(q):
    return q * np.array((-1.0, -1.0, -1.0, 1.0), q.dtype)


def qrot(q, v):
    u = q[..., :3]
    t = 2.0 * np.cross(u, v)
    return v + q[..., 3:4] * t + np.cross(u, t)


def nlerp(a, b, k):
    """Mistura por osso; ``k`` escalar ou (B,1)."""
    sign = np.where(np.sum(a * b, axis=-1, keepdims=True) < 0, -1.0, 1.0)
    q = a + (b * sign - a) * k
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


class Pose:
    """Quadril no espaço do modelo e demais ossos relativos ao quadril."""
    __slots__ = ('t', 'q')

    def __init__(self, t, q):
        self.t, self.q = t, q

    def blend(self, other, weight):
        """``weight`` escalar ou vetor (B,) por osso."""
        k = weight[:, None] if isinstance(weight, np.ndarray) else weight
        return Pose(self.t + (other.t - self.t) * k, nlerp(self.q, other.q, k))

    def attached(self, other, bones, anchor):
        """``other`` com os ``bones`` reposicionados para seguir o ``anchor`` desta pose (mesma posição
        relativa ao osso âncora que tinham em ``other``)."""
        inv = qconj(other.q[anchor])
        rel_t = qrot(inv, other.t[bones] - other.t[anchor])
        rel_q = qmul(inv, other.q[bones])
        aq = np.broadcast_to(self.q[anchor], rel_q.shape)
        t, q = other.t.copy(), other.q.copy()
        t[bones] = self.t[anchor] + qrot(aq, rel_t)
        q[bones] = qmul(aq, rel_q)
        return Pose(t, q)


# --------------------------------------------------------------------------------------
# Dados do esqueleto e dos clipes
# --------------------------------------------------------------------------------------

class ClipData:
    def __init__(self, name, anim, hips, loop):
        bones, frames = anim.boneCount, anim.keyframeCount
        raw = np.empty((frames, bones, 10), np.float64)
        for f in range(frames):
            raw[f] = np.frombuffer(_ffi.buffer(anim.keyframePoses[f], bones * 40), np.float32).reshape(bones, 10)
        t, q = raw[..., 0:3], raw[..., 3:7]
        q /= np.linalg.norm(q, axis=-1, keepdims=True)
        ht, hq = t[:, hips:hips + 1], q[:, hips:hips + 1]
        inv = qconj(hq)
        rel_t = qrot(np.broadcast_to(inv, q.shape), t - ht)
        rel_q = qmul(np.broadcast_to(inv, q.shape), q)
        rel_t[:, hips] = t[:, hips]
        rel_q[:, hips] = q[:, hips]
        # Hemisfério contínuo quadro a quadro (nlerp entre vizinhos sem volta longa).
        for f in range(1, frames):
            flip = np.sum(rel_q[f] * rel_q[f - 1], axis=-1) < 0
            rel_q[f][flip] *= -1
        self.name, self.loop = name, loop
        self.t, self.q = rel_t, rel_q
        self.frames = frames
        self.period = max(1, frames - 1)
        self.duration = self.period / FPS

    def sample(self, frame):
        """Pose no quadro ``frame`` (float, 60/s): cíclico se ``loop``, senão preso nas pontas."""
        if self.loop:
            frame %= self.period
        else:
            frame = min(max(frame, 0.0), self.period)
        i = int(frame)
        j = min(i + 1, self.frames - 1)
        k = frame - i
        if k < 1e-4:
            return Pose(self.t[i], self.q[i])
        return Pose(self.t[i] + (self.t[j] - self.t[i]) * k, nlerp(self.q[i], self.q[j], k))


class RigAnimation:
    """Clipes de um personagem em numpy, máscaras por parte do corpo e o clipe de um quadro que leva a
    pose pronta ao raylib."""

    def __init__(self, model, clips, meta):
        skeleton = model.skeleton
        count = skeleton.boneCount
        names = [_ffi.string(skeleton.bones[i].name).decode() for i in range(count)]
        parents = [skeleton.bones[i].parent for i in range(count)]
        self.hips = names.index('hips') if 'hips' in names else next(i for i, p in enumerate(parents) if p < 0)
        loops = set(meta.get('loops', ('Idle', 'Walk', 'Run')))
        self.clips = {name: ClipData(name, anim, self.hips, name in loops) for name, anim in clips.items()}
        self.layers = dict(DEFAULT_LAYERS, **meta.get('layers', {}))
        self.strides = {'Walk': DEFAULT_STRIDE, 'Run': DEFAULT_STRIDE, **meta.get('strides', {})}
        # Passadas medidas no Blender: Walk/Run seguem a velocidade real (senão quem chama decide).
        self.measured = 'strides' in meta

        def under(root):
            out = np.zeros(count)
            if root not in names:
                return out
            r = names.index(root)
            for i in range(count):
                j = i
                while j >= 0 and j != r:
                    j = parents[j]
                out[i] = 1.0 if j == r else 0.0
            return out
        upper = under('spine')
        lower = 1.0 - upper
        self.masks = {'upper': upper, 'lower': lower, 'full': np.ones(count)}
        # "arms": ombros, braços e o que estiver preso ao peito fora da coluna (caixa); seguem o peito da
        # pose de baixo, então tronco e cabeça continuam na locomoção.
        self.anchor = names.index('chest') if 'chest' in names else None
        if self.anchor is not None:
            arms = np.zeros(count)
            for i, p in enumerate(parents):
                if p == self.anchor and names[i] not in ('neck', 'head'):
                    arms += under(names[i])
            self.masks['arms'] = np.minimum(arms, 1.0)
            self.arm_bones = np.flatnonzero(self.masks['arms'])
        else:
            self.masks['arms'] = upper
        self.count = count
        self.model = model
        self._poses = _ffi.new('Transform[]', count)
        self._frames = _ffi.new('Transform *[1]', [self._poses])
        self._anim = _ffi.new('ModelAnimation *')
        self._anim.boneCount = count
        self._anim.keyframeCount = 1
        self._anim.keyframePoses = self._frames
        self._out = np.zeros((count, 10), np.float32)
        self._out[:, 7:10] = 1.0

    def mask(self, clip):
        return self.masks[self.layers.get(clip, 'full')]

    def layer_pose(self, base, clip, sample):
        """Pose do clipe pronta para misturar sobre ``base`` (camada ``arms`` presa ao peito da base)."""
        if self.layers.get(clip) == 'arms' and self.anchor is not None:
            return base.attached(sample, self.arm_bones, self.anchor)
        return sample

    def natural_speed(self, name):
        clip = self.clips.get(name)
        return self.strides.get(name, DEFAULT_STRIDE) / clip.duration if clip else 0.0

    def apply(self, pose):
        """Volta ao espaço do modelo e atualiza o esqueleto (e o skinning) do Model."""
        h = self.hips
        ht, hq = pose.t[h], pose.q[h]
        out = self._out
        out[:, 0:3] = ht + qrot(np.broadcast_to(hq, pose.q.shape), pose.t)
        out[:, 3:7] = qmul(np.broadcast_to(hq, pose.q.shape), pose.q)
        out[h, 0:3], out[h, 3:7] = ht, hq
        _ffi.memmove(self._poses, out.tobytes(), out.nbytes)
        _raw.UpdateModelAnimation(self.model, self._anim[0], 0.0)


# --------------------------------------------------------------------------------------
# Estado por personagem
# --------------------------------------------------------------------------------------

class _Action:
    __slots__ = ('name', 'start', 'fade_at')

    def __init__(self, name, start):
        self.name, self.start, self.fade_at = name, start, None


class Animator:
    """Estado de animação de UM personagem (não compartilhar entre atores).

    ``update`` recebe velocidade, ar/chão, eventos e camadas contínuas; ``draw`` em models.py chama
    ``apply`` antes de desenhar. Tempo em segundos (``time.perf_counter``)."""

    def __init__(self, seed=0.0):
        self.seed = seed
        self.last = None
        self.cycle = 0.0
        self.weights = {'Idle': 1.0, 'Walk': 0.0, 'Run': 0.0}
        self.air = 0.0
        self.air_start = 0.0
        self.layers = {}
        self.action = None
        self.fading = []
        self.events = {}
        self.now = 0.0

    def update(self, rig, now, speed, walk=None, run=None, airborne=None, events=None, layers=None):
        """``walk``/``run`` (0..1) forçam a mistura de locomoção; sem eles, saem da velocidade (m/s).
        ``airborne`` = segundos no ar (None no chão). ``events`` = {clipe: segundos desde o início}.
        ``layers`` = {clipe contínuo: peso alvo} (Carry, Wave, Repair...)."""
        anim = rig.anim
        first = self.last is None
        dt = 0.0 if first else min(max(now - self.last, 0.0), .1)
        self.last, self.now = now, now
        clips = anim.clips
        walk_speed = anim.natural_speed('Walk') or 1.0
        run_speed = anim.natural_speed('Run') if 'Run' in clips else 0.0
        if walk is None:
            walk = smooth(.05, max(.3, .35 * walk_speed), speed)
        if run is None:
            run = smooth(walk_speed * 1.15, max(walk_speed * 1.2, run_speed * .85), speed) if run_speed else 0.0
        if 'Run' not in clips:
            run = 0.0
        targets = {'Idle': 1 - walk, 'Walk': walk * (1 - run), 'Run': walk * run}
        for name, target in targets.items():
            self.weights[name] = target if first else approach(self.weights[name], target, BLEND_RATE, dt)
        # Ciclo dos passos: distância / passada (Walk e Run compartilham o ciclo).
        w_walk, w_run = self.weights['Walk'], self.weights['Run']
        moving = w_walk + w_run
        stride = (anim.strides['Walk'] * w_walk + anim.strides['Run'] * w_run) / moving if moving > 1e-3 \
            else anim.strides['Walk']
        natural = (clips['Walk'].duration if 'Walk' in clips else 1.0)
        rate = speed / max(stride, .05)
        rate = min(max(rate, .55 / natural * moving), 1.7 / natural)  # passos legíveis em qualquer velocidade
        self.cycle = (self.cycle + rate * dt) % 1.0

        if airborne is not None and 'Jump' in clips:
            if self.air < .02:
                self.air_start = now - airborne
            self.air = approach(self.air, 1.0, AIR_RATE, dt) if not first else 1.0
        else:
            self.air = approach(self.air, 0.0, AIR_RATE, dt)

        for name, target in (layers or {}).items():
            if name in clips:
                self.layers[name] = target if first else approach(self.layers.get(name, 0.0), target, LAYER_RATE, dt)
        for name in list(self.layers):
            if layers is None or name not in layers:
                self.layers[name] = approach(self.layers[name], 0.0, LAYER_RATE, dt)
                if self.layers[name] < 1e-3:
                    del self.layers[name]

        self.events = {}
        events = events or {}
        current = None
        for name in EVENTS:
            seconds = events.get(name)
            if name in clips and seconds is not None and 0 <= seconds < clips[name].duration:
                if current is None or seconds < current[1]:
                    current = (name, seconds)
        if current is not None:
            name, seconds = current
            start = now - seconds
            act = self.action
            if act is None or act.name != name or start > act.start + 1e-3:
                if act is not None:
                    act.fade_at = now
                    self.fading.append(act)
                self.action = _Action(name, start)
        elif self.action is not None:
            self.action.fade_at = now
            self.fading.append(self.action)
            self.action = None
        self.fading = [a for a in self.fading if now - a.fade_at < CROSSFADE]
        land = events.get('Land')
        if land is not None and 'Land' in clips and 0 <= land < clips['Land'].duration:
            self.events['Land'] = land

    def _envelope(self, clip, seconds):
        return smooth(0.0, FADE_IN, seconds) * (1 - smooth(clip.duration - FADE_OUT, clip.duration, seconds))

    def apply(self, rig):
        anim = rig.anim
        clips = anim.clips
        now = self.now
        w = self.weights
        pose = clips['Idle'].sample((now + self.seed) * FPS)
        total = w['Idle']
        for name in ('Walk', 'Run'):
            if w[name] > 1e-3 and name in clips:
                total += w[name]
                pose = pose.blend(clips[name].sample(self.cycle * clips[name].period), w[name] / total)
        if self.air > 1e-3:
            pose = pose.blend(clips['Jump'].sample((now - self.air_start) * FPS), anim.mask('Jump') * self.air)
        if 'Land' in self.events:
            clip = clips['Land']
            seconds = self.events['Land']
            pose = pose.blend(clip.sample(seconds * FPS), anim.mask('Land') * self._envelope(clip, seconds))
        for name, weight in self.layers.items():
            if weight > 1e-3:
                layer = anim.layer_pose(pose, name, clips[name].sample((now + self.seed) * FPS))
                pose = pose.blend(layer, anim.mask(name) * min(1.0, weight))
        for act in self.fading + ([self.action] if self.action else []):
            clip = clips[act.name]
            seconds = now - act.start
            weight = self._envelope(clip, seconds)
            if act.fade_at is not None:
                weight *= 1 - smooth(0.0, CROSSFADE, now - act.fade_at)
            if weight > 1e-3:
                pose = pose.blend(clip.sample(seconds * FPS), anim.mask(act.name) * weight)
        anim.apply(pose)
