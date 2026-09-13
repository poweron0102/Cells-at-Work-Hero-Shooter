"""Gameplay RPCs built on the native EasyCells3D networking components.

NetworkManager owns transport/dispatch. PeerCommands owns client requests.
ArenaNetwork owns replicated match state. NetworkTransform owns actor positions.
"""
import math
import time
from EasyCells3D.NetworkComponents import NetworkComponent, NetworkManager, Rpc, SendTo
from EasyCells3D.NetworkComponents.NetworkComponent import Protocol
from .catalog import HEROES, CELLS, BACTERIA, can_select

SESSION_ID = 100
COMMAND_ID_BASE = 1000
TRANSFORM_ID_BASE = 100_000


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


class PeerCommands(NetworkComponent):
    """One channel per TCP peer; the engine checks require_owner before each RPC."""
    def __init__(self, session, peer_id):
        super().__init__(identifier=COMMAND_ID_BASE + peer_id, owner=peer_id)
        self.session = session

    @Rpc(send_to=SendTo.SERVER, require_owner=True, protocol=Protocol.TCP)
    def join(self, name):
        self.session.join_peer(self.owner, name)

    @Rpc(send_to=SendTo.SERVER, require_owner=True, protocol=Protocol.TCP)
    def choose_hero(self, hero):
        self.session.choose_for_peer(self.owner, hero)

    @Rpc(send_to=SendTo.SERVER, require_owner=True, protocol=Protocol.TCP)
    def submit_input(self, command):
        session = self.session
        slot = session.slot_for_peer(self.owner)
        if slot is not None and session.status == "playing":
            session.commands[slot] = clean_command(command)
            session.command_times[slot] = time.monotonic()


class ArenaNetwork(NetworkComponent):
    def __init__(self, manager, name="Cell worker"):
        super().__init__(identifier=SESSION_ID, owner=0)
        self.manager = manager
        self.roster = {}
        self.status = "lobby"
        self.commands = {}
        self.command_times = {}
        self.latest = None
        self.arena = None
        self.error = ""
        self.name = name[:20]
        self.channels = {}
        self.timer = self.join_timer = 0
        self.closed = False
        self.last_receive = time.monotonic()
        if self.is_server:
            self.roster[0] = dict(owner=0, hero="neutrophil", team=CELLS, name=self.name, bot=False)

    @property
    def is_server(self):
        return self.manager.is_server

    @property
    def id(self):
        return self.manager.id

    @property
    def ip(self):
        return self.manager.ip

    @property
    def port(self):
        return self.manager.port

    @property
    def local_slot(self):
        return self.slot_for_peer(self.id)

    def slot_for_peer(self, peer_id):
        return next((slot for slot, p in self.roster.items() if p["owner"] == peer_id and not p["bot"]), None)

    def init(self):
        super().init()
        if self.is_server:
            self.ensure_channel(0)

    def ensure_channel(self, peer_id):
        if peer_id not in self.channels:
            item = self.item.CreateChild()
            item.name = f"Peer commands / {peer_id}"
            self.channels[peer_id] = item.AddComponent(PeerCommands(self, peer_id))
        return self.channels[peer_id]

    def choose(self, hero):
        if self.id >= 0:
            self.ensure_channel(self.id).choose_hero(hero)

    def input(self, command):
        if self.id >= 0:
            self.ensure_channel(self.id).submit_input(command)

    def command(self, slot):
        if time.monotonic() - self.command_times.get(slot, 0) > .35:
            return {}
        return self.commands.get(slot, {})

    @Rpc(send_to=SendTo.CLIENTS, require_owner=True, protocol=Protocol.TCP)
    def receive_match_state(self, roster, status, state):
        self.roster, self.status, self.latest = roster, status, state
        self.last_receive = time.monotonic()

    @Rpc(send_to=SendTo.CLIENTS, require_owner=True, protocol=Protocol.TCP)
    def receive_error(self, message):
        self.error = message
        self.last_receive = time.monotonic()

    def join_peer(self, peer_id, name):
        if not self.is_server or self.slot_for_peer(peer_id) is not None:
            return
        if self.status != "lobby" or len(self.roster) >= 6:
            self.manager.call_rpc_on_client(peer_id, self.receive_error, "Sala cheia ou partida em andamento.")
            return
        cells = sum(p["team"] == CELLS for p in self.roster.values())
        bacteria = sum(p["team"] == BACTERIA for p in self.roster.values())
        team = CELLS if cells <= bacteria else BACTERIA
        slots = range(3) if team == CELLS else range(3, 6)
        slot = next(s for s in slots if s not in self.roster)
        hero = next(h for h in HEROES if can_select(h, team, self.roster))
        name = "".join(c for c in str(name)[:20] if c.isascii() and c.isprintable()) or "Worker"
        self.roster[slot] = dict(owner=peer_id, hero=hero, team=team, name=name, bot=False)

    def choose_for_peer(self, peer_id, hero):
        slot = self.slot_for_peer(peer_id)
        if not self.is_server or slot is None or not isinstance(hero, str) or hero not in HEROES:
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

    def loop(self):
        if self.closed:
            return
        if self.is_server:
            # Inspect connection lifecycle only; NetworkManager reads and routes all packets.
            clients = self.manager.transports[Protocol.TCP].clients
            for peer_id in range(1, len(clients)):
                if clients[peer_id] is not None:
                    self.ensure_channel(peer_id)
            for slot, player in list(self.roster.items()):
                peer_id = player["owner"]
                if peer_id > 0 and (peer_id >= len(clients) or clients[peer_id] is None):
                    if self.status == "lobby":
                        del self.roster[slot]
                    else:
                        player.update(bot=True, owner=-slot-1, name=f"BOT {slot+1}")
                        self.commands.pop(slot, None)
            for peer_id in list(self.channels):
                if peer_id > 0 and (peer_id >= len(clients) or clients[peer_id] is None):
                    self.channels.pop(peer_id).item.Destroy()
            self.timer -= self.game.delta_time
            if self.timer <= 0:
                self.timer = .05 if self.status == "playing" else .2
                state = self.arena.serialize_state() if self.arena else self.latest
                self.receive_match_state(self.roster, self.status, state)
        else:
            self.join_timer -= self.game.delta_time
            if self.id >= 0 and self.local_slot is None and self.join_timer <= 0 and not self.error:
                self.ensure_channel(self.id).join(self.name)
                self.join_timer = .5
            if time.monotonic() - self.last_receive > 7:
                self.error = "Sem resposta do servidor. Volte ao menu e tente conectar novamente."

    def on_destroy(self):
        if self.closed:
            return
        self.closed = True
        super().on_destroy()
        if NetworkManager.instance is self.manager:
            NetworkManager.instance = None


def connect(game, ip, port, host, name):
    item = game.CreateItem()
    item.name = "Network session"
    item.destroy_on_load = False
    try:
        manager = item.AddComponent(NetworkManager(ip=ip, port=port, is_server=host))
        session = item.AddComponent(ArenaNetwork(manager, name))
    except OSError:
        item.Destroy()
        raise
    game.session = session
    return session


def disconnect(game):
    if getattr(game, "session", None):
        game.session.item.Destroy()
        game.session = None
