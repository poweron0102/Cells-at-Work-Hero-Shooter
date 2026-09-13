"""LAN session over the engine's NetworkManager/TcpTransport.

The host accepts input, never client positions, health or objective progress.
TCP keeps peer identity consistent; no independent UDP handshake is involved.
"""
import math
import time
from EasyCells3D.NetworkComponents import NetworkManager
from EasyCells3D.NetworkComponents.NetworkComponent import Protocol
from .catalog import HEROES, CELLS, BACTERIA, can_select

VERSION = 1


def clean_command(data):
    if not isinstance(data, dict):
        return {}
    out = {}
    for key in ("x", "z", "yaw", "pitch"):
        value = data.get(key, 0)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return {}
        out[key] = max(-1, min(1, value)) if key in ("x", "z") else (
            max(-1.45, min(1.45, value)) if key == "pitch" else value % math.tau)
    for key in ("fire", "secondary", "ability", "ultimate", "interact", "jump", "sprint", "reload"):
        out[key] = data.get(key) is True
    return out


class ArenaNetwork(NetworkManager):
    def __init__(self, ip, port, is_server, name="Cell worker"):
        self.roster = {}
        self.status = "lobby"
        self.commands = {}
        self.command_times = {}
        self.latest = None
        self.arena = None
        self.error = ""
        self.name = name[:20]
        self.sent_hello = False
        self.timer = 0
        self.closed = False
        self.last_receive = time.monotonic()
        self.start_time = time.monotonic()
        super().__init__(ip, port, is_server, enable_udp=False)
        if is_server:
            self.roster[0] = dict(owner=0, hero="neutrophil", team=CELLS, name=self.name, bot=False)

    @property
    def local_slot(self):
        return next((slot for slot, p in self.roster.items() if p["owner"] == self.id and not p["bot"]), None)

    def send(self, packet):
        packet["v"] = VERSION
        if self.is_server:
            self.process_packet(packet, 0)
        elif self.id >= 0:
            self.send_to_server(packet, Protocol.TCP)

    def choose(self, hero):
        self.send({"kind": "choose", "hero": hero})

    def input(self, command):
        self.send({"kind": "input", "data": command})

    def command(self, slot):
        if time.monotonic() - self.command_times.get(slot, 0) > .35:
            return {}
        return self.commands.get(slot, {})

    def start(self, fill_bots=False):
        if not self.is_server or self.status != "lobby":
            return
        if len(self.roster) < 6 and not fill_bots:
            self.error = "O 3v3 precisa de 6 jogadores. Use treino para completar com bots."
            return
        for slot in range(6):
            if slot in self.roster:
                continue
            team = CELLS if slot < 3 else BACTERIA
            hero = next(h for h in HEROES if can_select(h, team, self.roster))
            self.roster[slot] = dict(owner=-slot-1, hero=hero, team=team, name=f"BOT {slot+1}", bot=True)
        self.status = "playing"
        self.commands.clear()

    def process_packet(self, packet, sender_id):
        if not isinstance(packet, dict) or packet.get("v") != VERSION:
            return
        kind = packet.get("kind")
        if not self.is_server:
            if sender_id != 0:
                return
            self.last_receive = time.monotonic()
            if kind == "snapshot":
                self.roster = packet["roster"]
                self.status = packet["status"]
                self.latest = packet.get("arena")
            elif kind == "error":
                self.error = packet["text"]
            return
        slot = next((s for s, p in self.roster.items() if p["owner"] == sender_id and not p["bot"]), None)
        if kind == "hello":
            if slot is not None:
                return
            if self.status != "lobby" or len(self.roster) >= 6:
                self.send_to_client({"v": VERSION, "kind": "error", "text": "Sala cheia ou partida em andamento."}, sender_id, Protocol.TCP)
                return
            cells = sum(p["team"] == CELLS for p in self.roster.values())
            bacteria = sum(p["team"] == BACTERIA for p in self.roster.values())
            team = CELLS if cells <= bacteria else BACTERIA
            slots = range(3) if team == CELLS else range(3, 6)
            slot = next(s for s in slots if s not in self.roster)
            hero = next(h for h in HEROES if can_select(h, team, self.roster))
            name = str(packet.get("name", "Worker"))[:20]
            name = "".join(c for c in name if c.isascii() and c.isprintable()) or "Worker"
            self.roster[slot] = dict(owner=sender_id, hero=hero, team=team, name=name, bot=False)
        elif slot is not None and kind == "input" and self.status == "playing":
            self.commands[slot] = clean_command(packet.get("data"))
            self.command_times[slot] = time.monotonic()
        elif slot is not None and kind == "choose":
            hero = packet.get("hero")
            if not isinstance(hero, str) or hero not in HEROES:
                return
            team = HEROES[hero].team
            if self.status == "lobby":
                if not can_select(hero, team, self.roster, exclude=slot):
                    return
                if team != self.roster[slot]["team"]:
                    target = next((s for s in (range(3) if team == CELLS else range(3, 6)) if s not in self.roster), None)
                    if target is None:
                        return
                    self.roster[target] = self.roster.pop(slot)
                    slot = target
                self.roster[slot].update(hero=hero, team=team)
            elif self.status == "playing" and self.arena:
                actor = self.arena.actors[slot]
                state = self.arena.state
                if not actor.alive and can_select(hero, actor.team, self.roster, state.recognition, state.infected, slot):
                    self.roster[slot]["hero"] = hero

    def loop(self):
        if self.closed:
            return
        # Bound work per peer to avoid a fast sender consuming the whole frame.
        transport = self.transports[Protocol.TCP]
        if self.is_server:
            for cid in range(1, len(transport.clients)):
                for _ in range(32):
                    packet = transport.read(cid)
                    if packet is None:
                        break
                    self.process_packet(packet, cid)
            for slot, player in list(self.roster.items()):
                cid = player["owner"]
                if cid > 0 and (cid >= len(transport.clients) or transport.clients[cid] is None):
                    if self.status == "lobby":
                        del self.roster[slot]
                    else:
                        player.update(bot=True, owner=-slot-1, name=f"BOT {slot+1}")
                        self.commands.pop(slot, None)
            self.timer -= self.game.delta_time
            if self.timer <= 0:
                self.timer = .05 if self.status == "playing" else .2
                packet = dict(v=VERSION, kind="snapshot", roster=self.roster, status=self.status,
                              arena=self.arena.snapshot() if self.arena else self.latest)
                self.broadcast(packet, Protocol.TCP)
        else:
            if self.id >= 0 and not self.sent_hello:
                self.send({"kind": "hello", "name": self.name})
                self.sent_hello = True
            for _ in range(64):
                packet = transport.read()
                if packet is None:
                    break
                self.process_packet(packet, 0)
            if time.monotonic() - self.last_receive > 7:
                self.error = "Sem resposta do servidor. Volte ao menu e tente conectar novamente."

    def on_destroy(self):
        if self.closed:
            return
        self.closed = True
        super().on_destroy()
        if NetworkManager.instance is self:
            NetworkManager.instance = None


def connect(game, ip, port, host, name):
    item = game.CreateItem()
    item.name = "Network session"
    item.destroy_on_load = False
    try:
        network = item.AddComponent(ArenaNetwork(ip, port, host, name))
    except OSError:
        item.Destroy()
        raise
    game.session = network
    return network


def disconnect(game):
    if getattr(game, "session", None):
        game.session.item.Destroy()
        game.session = None
