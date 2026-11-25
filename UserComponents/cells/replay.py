"""Replays: gravação no anfitrião e reprodução em 3ª pessoa.

Gravação (``ReplayRecorder``, só no anfitrião, quando o lobby marcou "Gravar replay"):
o arquivo guarda exatamente o que um cliente *espectador* receberia do anfitrião — todo
broadcast e todo repasse "para todos menos o remetente" (``NetworkManager.taps``). Isso já
inclui o que o próprio anfitrião e os bots fazem. Somam-se dados que a rede não replica:
o pitch (mira vertical) de cada herói a 10 Hz — os clientes o informam só ao anfitrião
enquanto a partida é gravada (``Combatant.report_aim``).

Formato ``.replay``: gzip com uma sequência de pickles (protocolo 5)
  1. cabeçalho ``dict(format, version, created, host, roster, status, balance, map)``
  2. um bloco por quadro com novidades: ``(t, [pacote_em_pickle, ...], {slot: pitch} | None)``
  3. fim: ``("end", t, resultado)`` (ausente se o jogo caiu; o leitor aproveita o que houver)
Ao lado, ``<nome>.json`` resume a partida para a lista de replays.
A leitura usa um unpickler restrito: só tipos básicos e os vetores da engine.

Reprodução (``ReplayDirector``): a cena do replay monta a arena como um cliente sem herói
(``ReplayNetwork`` faz o papel do NetworkManager) e reinjeta os pacotes no tempo certo;
os mesmos componentes visuais do jogo desenham tudo.
"""
import copy
import gzip
import hashlib
import io
import json
import math
import pickle
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pyray as rl
from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3, Quaternion
from EasyCells3D.NetworkComponents import NetworkManager, NetworkTransform
from EasyCells3D.NetworkComponents.NetworkComponent import OP_RPC, OP_VAR
from . import settings

REPLAY_DIR = Path("replays")
EXTENSION = ".replay"
FORMAT = "cells-at-work-replay"
VERSION = 1
PICKLE = 5
SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0)
AIM_RATE = .1
FLUSH_EVERY = 2.0  # segundos: o que já foi gravado sobrevive a uma queda do jogo
SPECTATOR_ID = -7  # nenhum herói pertence a este id: no replay ninguém é "local"
ARENA_ID = 200
STREAMS = ("sync_transform", "sync_minion", "sync_focus")  # estado contínuo: no avanço rápido só o último vale


def balance_hash():
    try:
        return hashlib.sha1(Path("Assets/balance.json").read_bytes()).hexdigest()[:12]
    except OSError:
        return ""


# -- leitura segura -------------------------------------------------------------------------
_ALLOWED = {("EasyCells3D.Geometry", "Vec3"), ("EasyCells3D.Geometry", "Vec2"),
            ("EasyCells3D.Geometry", "Quaternion")}


class _SafeUnpickler(pickle.Unpickler):
    """Replays podem vir de outra pessoa: nada de reconstruir classes arbitrárias."""

    def find_class(self, module, name):
        if (module, name) in _ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"tipo nao permitido em replay: {module}.{name}")


def _load_next(stream):
    return _SafeUnpickler(stream).load()


def _loads(data):
    return _SafeUnpickler(io.BytesIO(data)).load()


@dataclass
class ReplayData:
    path: Path
    header: dict
    chunks: list            # [(t, [pacote], {slot: pitch} | None)]
    duration: float
    result: dict | None
    complete: bool
    kills: list = field(default_factory=list)  # [(t, vitima, autor)] para as marcas da linha do tempo
    skipped: int = 0        # pacotes que não puderam ser lidos

    @property
    def same_balance(self):
        return not self.header.get("balance") or self.header.get("balance") == balance_hash()


def load_replay(path):
    """Lê um ``.replay`` inteiro; arquivos cortados (queda do jogo) valem até onde der."""
    path = Path(path)
    chunks, kills = [], []
    result, complete, skipped, last_t = None, False, 0, 0.0
    with gzip.open(path, "rb") as stream:
        header = _load_next(stream)
        if not isinstance(header, dict) or header.get("format") != FORMAT:
            raise ValueError("Arquivo não é um replay de Cells at Work.")
        if header.get("version", 0) > VERSION:
            raise ValueError("Replay gravado por uma versão mais nova do jogo.")
        while True:
            try:
                record = _load_next(stream)
            except (EOFError, OSError, zlib.error, pickle.UnpicklingError, ValueError):
                break
            if record and record[0] == "end":
                last_t = max(last_t, float(record[1]))
                result, complete = record[2], True
                break
            t, raw, aims = record
            packets = []
            for blob in raw:
                try:
                    packet = _loads(blob)
                except (pickle.UnpicklingError, EOFError, ValueError, TypeError, AttributeError):
                    skipped += 1
                    continue
                packets.append(packet)
                if packet[0] == OP_RPC and packet[1] == ARENA_ID and packet[2] == "eliminated":
                    victim, source = packet[3][0], packet[3][1]
                    kills.append((t, victim, source))
            chunks.append((float(t), packets, aims))
            last_t = max(last_t, float(t))
    return ReplayData(path, header, chunks, last_t, result, complete, kills, skipped)


# -- lista de arquivos ----------------------------------------------------------------------
def meta_path(path):
    return Path(path).with_suffix(".json")


def read_meta(path):
    path = Path(path)
    try:
        meta = json.loads(meta_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = None
    if not isinstance(meta, dict):
        try:
            with gzip.open(path, "rb") as stream:
                header = _load_next(stream)
        except Exception:
            return None
        if not isinstance(header, dict) or header.get("format") != FORMAT:
            return None
        meta = dict(created=header.get("created", ""), host=header.get("host", ""),
                    roster=_roster_meta(header.get("roster", {})), duration=None, complete=False,
                    map=header.get("map", "bairro"))
    meta["path"] = str(path)
    try:
        meta["size"] = path.stat().st_size
    except OSError:
        meta["size"] = 0
    return meta


def list_replays():
    if not REPLAY_DIR.exists():
        return []
    files = sorted(REPLAY_DIR.glob("*" + EXTENSION), key=lambda p: p.stat().st_mtime, reverse=True)
    return [m for m in (read_meta(p) for p in files) if m is not None]


def delete_replay(path):
    for target in (Path(path), meta_path(path)):
        try:
            target.unlink()
        except OSError:
            pass


def _roster_meta(roster):
    return {str(slot): dict(hero=p.get("hero"), team=p.get("team"), name=p.get("name"), bot=p.get("bot"))
            for slot, p in roster.items()}


# -- gravação -------------------------------------------------------------------------------
class ReplayRecorder(Component):
    """Grava a partida do anfitrião enquanto a cena da arena existir."""

    def __init__(self, session, arena):
        self.session, self.arena = session, arena
        self.file = None
        self.path = None
        self.pending = []
        self.start = 0.0
        self.last_t = 0.0
        self.aim_clock = 0.0
        self.flush_clock = 0.0

    def init(self):
        manager = self.session.manager
        if not manager.is_server:
            return
        REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        stem = now.strftime("%Y-%m-%d_%H-%M-%S")
        self.path = REPLAY_DIR / f"{stem}{EXTENSION}"
        n = 2
        while self.path.exists():
            self.path = REPLAY_DIR / f"{stem}_{n}{EXTENSION}"
            n += 1
        self.created = now.isoformat(timespec="seconds")
        self.header = dict(format=FORMAT, version=VERSION, created=self.created, host=self.session.name,
                           roster=copy.deepcopy(self.session.roster.value), status=self.session.status,
                           balance=balance_hash(), map=self.session.map_key)
        self.file = gzip.open(self.path, "wb", compresslevel=6)
        pickle.dump(self.header, self.file, protocol=PICKLE)
        self.start = self.game.run_time
        manager.taps.append(self.capture)
        self.write_meta()
        print(f"[Replay] gravando em {self.path.resolve()}")

    def capture(self, packet, protocol):
        # Serializa já: quem enviou pode alterar o objeto depois (ex.: dicionários do elenco).
        try:
            self.pending.append(pickle.dumps(packet, protocol=PICKLE))
        except Exception:
            pass

    def loop(self):
        if self.file is None:
            return
        dt = self.game.delta_time
        self.last_t = max(self.last_t, self.game.run_time - self.start)
        aims = None
        self.aim_clock += dt
        if self.aim_clock >= AIM_RATE:
            self.aim_clock = 0.0
            aims = {slot: round(float(a.pitch), 3) for slot, a in self.arena.actors.items()}
        if self.pending or aims:
            pickle.dump((round(self.last_t, 4), self.pending, aims), self.file, protocol=PICKLE)
            self.pending = []
        self.flush_clock += dt
        if self.flush_clock >= FLUSH_EVERY:
            self.flush_clock = 0.0
            self.file.flush(zlib.Z_SYNC_FLUSH)
        if self.session.status == "results":
            self.finish()

    def finish(self):
        if self.file is None:
            return
        try:
            if self.pending:
                pickle.dump((round(self.last_t, 4), self.pending, None), self.file, protocol=PICKLE)
                self.pending = []
            pickle.dump(("end", round(self.last_t, 4), self.session.result), self.file, protocol=PICKLE)
        finally:
            self.file.close()
            self.file = None
            if self.capture in self.session.manager.taps:
                self.session.manager.taps.remove(self.capture)
        self.write_meta(final=True)
        self.game.last_replay = self.path
        print(f"[Replay] salvo: {self.path.resolve()} ({self.last_t:.0f} s)")

    def write_meta(self, final=False):
        result = self.session.result if final else None
        meta = dict(created=self.created, host=self.header["host"], roster=_roster_meta(self.header["roster"]),
                    duration=round(self.last_t, 2), complete=bool(final and result),
                    balance=self.header["balance"], map=self.header.get("map", "bairro"))
        if result:
            meta["winner"] = result.get("state", {}).get("winner")
            meta["score"] = {str(k): [v.get("kills", 0), v.get("deaths", 0)]
                             for k, v in result.get("actors", {}).items()}
        try:
            meta_path(self.path).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def on_destroy(self):
        self.finish()


# -- reprodução -----------------------------------------------------------------------------
class ReplayNetwork(Component):
    """Faz o papel do NetworkManager no replay: um espectador que só recebe (e nada envia)."""
    is_server = False

    def __init__(self):
        self.id = SPECTATOR_ID
        self.ip, self.port = "replay", 0
        self.error = ""
        self.taps = []
        self.connect_callbacks = []
        self.disconnect_callbacks = []
        self.previous = NetworkManager.instance
        NetworkManager.instance = self

    def send_to_server(self, packet, protocol):
        pass

    def send_to_client(self, packet, client_id, protocol):
        pass

    def broadcast(self, packet, protocol):
        pass

    def tap(self, packet, protocol):
        pass

    def on_destroy(self):
        if NetworkManager.instance is self:
            NetworkManager.instance = None


@dataclass
class ReplayState:
    """O que sobrevive às recargas da cena (voltar no tempo remonta a arena do zero)."""
    data: ReplayData
    seek_to: float = 0.0
    speed: float = 1.0
    paused: bool = False
    follow: int | None = None
    free: bool = False
    ui: bool = True


def open_replay(game, data, state=None):
    """Cria a sessão de espectador do replay (substitui qualquer sessão de rede)."""
    from .session import Session, disconnect
    disconnect(game)
    item = game.CreateItem()
    item.name = "Replay session"
    item.destroy_on_load = False
    net = item.AddComponent(ReplayNetwork())
    session = item.AddComponent(Session(net, data.header.get("host") or "Replay"))
    session.roster._value = copy.deepcopy(data.header.get("roster", {}))
    session.map._value = data.header.get("map", "bairro")  # replays antigos: so havia o Bairro Arterial
    session.status = data.header.get("status", "playing")
    session.joined = True
    game.session = session
    if state is None:
        state = ReplayState(data)
        roster = session.roster.value
        state.follow = min(roster) if roster else None
    game.replay = state
    return state


def close_replay(game, to="replay"):
    """Sai da reprodução: ``to='replay'`` volta à lista, ``'menu'`` ao menu."""
    from .session import disconnect
    game.replay = None
    game.time_scale = 1.0
    game.audio_listener = None
    disconnect(game)
    game.new_game(to)


def restart_at(game, seconds):
    """Voltar no tempo: remonta a cena e avança até ``seconds``."""
    state = game.replay
    state.seek_to = max(0.0, seconds)
    open_replay(game, state.data, state)
    game.new_game("replay")


def wrap_angle(a):
    return (a + math.pi) % math.tau - math.pi


class ReplayDirector(Component):
    """Relógio do replay, injeção dos pacotes, avanço rápido e câmeras (seguir/livre)."""

    def __init__(self, arena, camera, state):
        self.arena, self.camera, self.state = arena, camera, state
        self.data = state.data
        self.chunks = state.data.chunks
        self.index = 0
        self.clock = 0.0
        self.pending_seek = state.seek_to
        self.health = {}
        self.cam_pos = None
        self.cam_yaw = 0.0
        self.cam_pitch = -.2
        self.finished = False

    def init(self):
        self.game.audio_listener = self.listener

    def on_destroy(self):
        if getattr(self.game, "audio_listener", None) == self.listener:
            self.game.audio_listener = None

    # -- tempo ------------------------------------------------------------------------------
    @property
    def duration(self):
        return self.data.duration

    def loop(self):
        state = self.state
        real_dt = min(.1, rl.get_frame_time() if rl.is_window_ready() else self.game.delta_time)
        if self.pending_seek is not None:
            target, self.pending_seek = self.pending_seek, None
            self.fast_forward(target)
        if rl.is_window_ready():
            self.handle_input(real_dt)
        self.game.time_scale = 0.0 if state.paused else state.speed
        if not state.paused:
            self.clock = min(self.duration, self.clock + self.game.delta_time)
        self.play_until(self.clock)
        self.finished = self.clock >= self.duration - 1e-6
        if self.finished and not state.paused:
            state.paused = True
        self.track_hurt()
        self.update_camera(real_dt)

    def play_until(self, t):
        chunks = self.chunks
        while self.index < len(chunks) and chunks[self.index][0] <= t:
            _, packets, aims = chunks[self.index]
            self.index += 1
            self.apply(packets)
            self.apply_aims(aims)

    def apply(self, packets):
        for packet in packets:
            NetworkManager.process_packet(packet, 0, None)

    def apply_aims(self, aims):
        if aims:
            for slot, pitch in aims.items():
                actor = self.arena.actors.get(slot)
                if actor is not None:
                    actor.pitch = pitch

    def seek(self, seconds):
        seconds = max(0.0, min(self.duration, seconds))
        self.finished = False
        if seconds + 1e-6 < self.clock:
            restart_at(self.game, seconds)  # levanta NewGame: a cena é remontada
        self.fast_forward(seconds)

    def fast_forward(self, target):
        """Avança até ``target`` sem desenhar: eventos em ordem (com o envelhecimento dos efeitos
        entre eles) e, das trilhas contínuas (posições, variáveis, snapshot), só o último valor."""
        target = max(self.clock, min(self.duration, target))
        chunks = self.chunks
        latest, aims = {}, {}
        waiting, previous = 0.0, self.clock
        while self.index < len(chunks) and chunks[self.index][0] <= target:
            t, packets, chunk_aims = chunks[self.index]
            self.index += 1
            waiting += t - previous
            previous = t
            events = []
            for packet in packets:
                op, target_id, name, args = packet
                if op == OP_VAR:
                    latest[("var", target_id)] = packet
                elif name in STREAMS:
                    latest[(target_id, name, args[0] if name == "sync_minion" else None)] = packet
                elif target_id == ARENA_ID and name == "sync":
                    latest[("snapshot",)] = packet
                else:
                    events.append(packet)
            if chunk_aims:
                aims.update(chunk_aims)
            if events:
                self.age(waiting)
                waiting = 0.0
                self.apply(events)
        self.age(waiting + target - previous)
        self.apply(latest.values())
        self.apply_aims(aims)
        self.clock = target
        self.settle()

    def age(self, dt):
        """O que ``Arena.loop``/``Combatant.loop`` fariam com o tempo, sem física nem desenho."""
        if dt <= 0:
            return
        arena = self.arena
        for collection in (arena.tracers, arena.effects, arena.zones):
            for value in list(collection):
                value["life"] -= dt
                if value["life"] <= 0:
                    collection.remove(value)
        for zone in arena.zones:
            zone["age"] = zone.get("age", 0.0) + dt
        for ident, wall in list(arena.walls.items()):
            wall["life"] -= dt
            if wall["life"] <= 0:
                arena.remove_wall(ident)
        for minion in arena.minions.values():
            minion["age"] = minion.get("age", 0.0) + dt
            minion["recoil"] = 0.0
            minion["hurt"] = 0.0
        arena.rbc_view.update(dt)
        arena.state.elapsed += dt
        for actor in arena.actors.values():
            for key in actor.TIMERS:
                value = getattr(actor, key, 0)
                if isinstance(value, (int, float)) and value:
                    setattr(actor, key, max(0, value - dt))
            actor.tick_fx(dt)
            actor.action = max(0.0, actor.action - dt * 2.5)

    def settle(self):
        """Depois de um salto: sem interpolação pendente, sem projéteis no ar e sem som acumulado."""
        arena = self.arena
        for actor in arena.actors.values():
            sync = actor.GetComponent(NetworkTransform)
            if sync is not None and sync._target_position is not None:
                actor.transform.position = sync._target_position
                sync._target_position = None
            actor.fire_time = -1.0
        arena.projectiles.clear()
        arena.spits.clear()
        for value in arena.effects + arena.tracers:
            value["_heard"] = True
        from .audio import AudioFeedback
        for item in self.game.item_list:
            audio = item.GetComponent(AudioFeedback)
            if audio is not None:
                audio.tracked = {}
        self.health = {}
        self.cam_pos = None

    def track_hurt(self):
        """A rede não replica o "levou dano" (é do dono); no replay ele vem da queda de vida."""
        for slot, actor in self.arena.actors.items():
            health = actor.health.value
            before = self.health.get(slot)
            if before is not None and health < before - .01 and actor.alive:
                actor.hurt = .25
            self.health[slot] = health

    # -- controles --------------------------------------------------------------------------
    def toggle_pause(self):
        state = self.state
        if self.finished:
            state.paused = False
            self.seek(0.0)
            return
        state.paused = not state.paused

    def set_speed(self, speed):
        self.state.speed = speed

    def step_speed(self, direction):
        speeds = list(SPEEDS)
        current = min(range(len(speeds)), key=lambda i: abs(speeds[i] - self.state.speed))
        self.state.speed = speeds[max(0, min(len(speeds) - 1, current + direction))]

    def follow(self, slot):
        if slot in self.arena.actors:
            self.state.follow = slot
            self.state.free = False
            self.cam_pos = None

    def cycle(self, direction=1):
        slots = sorted(self.arena.actors)
        if not slots:
            return
        current = self.state.follow if self.state.follow in slots else slots[0]
        self.follow(slots[(slots.index(current) + direction) % len(slots)])

    def toggle_free(self):
        self.state.free = not self.state.free
        if not self.state.free:
            self.cam_pos = None

    def handle_input(self, dt):
        k = rl.KeyboardKey
        shift = rl.is_key_down(k.KEY_LEFT_SHIFT) or rl.is_key_down(k.KEY_RIGHT_SHIFT)
        if rl.is_key_pressed(k.KEY_SPACE):
            self.toggle_pause()
        if rl.is_key_pressed(k.KEY_RIGHT):
            self.seek(self.clock + (15 if shift else 5))
        if rl.is_key_pressed(k.KEY_LEFT):
            self.seek(self.clock - (15 if shift else 5))
        if rl.is_key_pressed(k.KEY_UP):
            self.step_speed(1)
        if rl.is_key_pressed(k.KEY_DOWN):
            self.step_speed(-1)
        for i, key in enumerate((k.KEY_ONE, k.KEY_TWO, k.KEY_THREE, k.KEY_FOUR, k.KEY_FIVE, k.KEY_SIX)):
            if rl.is_key_pressed(key):
                self.follow(i)
        if rl.is_key_pressed(k.KEY_TAB):
            self.cycle(-1 if shift else 1)
        if rl.is_key_pressed(k.KEY_C):
            self.toggle_free()
        if rl.is_key_pressed(k.KEY_H):
            self.state.ui = not self.state.ui
        if rl.is_key_pressed(k.KEY_ESCAPE):
            close_replay(self.game)

    # -- câmera -----------------------------------------------------------------------------
    def listener(self):
        if self.camera is None:
            return None
        return self.camera.transform.position.to_tuple, self.cam_yaw

    def update_camera(self, dt):
        if self.camera is None:
            return
        if self.state.free:
            if self.cam_pos is None:
                self.follow_camera(dt)  # a câmera livre parte de onde a de seguir estaria
            self.free_camera(dt)
        else:
            self.follow_camera(dt)
        self.camera.transform.rotation = (Quaternion.from_axis_angle(Vec3(0, 1, 0), -self.cam_yaw)
                                          * Quaternion.from_axis_angle(Vec3(1, 0, 0), self.cam_pitch))

    def follow_camera(self, dt):
        actor = self.arena.actors.get(self.state.follow)
        if actor is None:
            self.cycle()
            return
        yaw = actor.yaw
        pitch = max(-.9, min(.75, actor.pitch * .8 - .12))
        if self.cam_pos is None:
            self.cam_yaw, self.cam_pitch = yaw, pitch
        else:
            k = min(1.0, dt * 9)
            self.cam_yaw += wrap_angle(yaw - self.cam_yaw) * k
            self.cam_pitch += (pitch - self.cam_pitch) * k
        yaw, pitch = self.cam_yaw, self.cam_pitch
        back = Vec3(-math.sin(yaw) * math.cos(pitch), -math.sin(pitch) * .6, math.cos(yaw) * math.cos(pitch))
        right = Vec3(math.cos(yaw), 0, math.sin(yaw))
        pivot = actor.transform.position + Vec3(0, 1.15, 0) + right * .5
        want = pivot + back * 3.6
        delta = want - pivot
        world = self.game.physics_world
        hit = world.raycast(pivot, delta, delta.magnitude(), 1) if world is not None else None
        if hit is not None:
            want = hit.point - delta.normalize() * .3
        if self.cam_pos is None or (want - self.cam_pos).magnitude() > 12:
            self.cam_pos = want
        else:
            self.cam_pos = self.cam_pos + (want - self.cam_pos) * min(1.0, dt * 14)
        self.camera.transform.position = self.cam_pos

    def free_camera(self, dt):
        if self.cam_pos is None:
            self.cam_pos = Vec3(*self.camera.transform.position.to_tuple)
        if rl.is_window_ready():
            k = rl.KeyboardKey
            if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                delta = rl.get_mouse_delta()
                sens = .0028 * settings.get("mouse_sensitivity")
                flip = -1 if settings.get("invert_y") else 1
                self.cam_yaw = (self.cam_yaw + delta.x * sens) % math.tau
                self.cam_pitch = max(-1.5, min(1.5, self.cam_pitch - delta.y * sens * flip))
            yaw, pitch = self.cam_yaw, self.cam_pitch
            forward = Vec3(math.sin(yaw) * math.cos(pitch), math.sin(pitch), -math.cos(yaw) * math.cos(pitch))
            right = Vec3(math.cos(yaw), 0, math.sin(yaw))
            move = Vec3(0, 0, 0)
            down = rl.is_key_down
            if down(k.KEY_W):
                move = move + forward
            if down(k.KEY_S):
                move = move - forward
            if down(k.KEY_D):
                move = move + right
            if down(k.KEY_A):
                move = move - right
            if down(k.KEY_E):
                move = move + Vec3(0, 1, 0)
            if down(k.KEY_Q):
                move = move - Vec3(0, 1, 0)
            speed = 30 if down(k.KEY_LEFT_SHIFT) else 10
            if move.magnitude() > 0:
                self.cam_pos = self.cam_pos + move.normalize() * (speed * dt)
        self.camera.transform.position = self.cam_pos
