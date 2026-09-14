"""Lobby membership, hero selection and match transitions using engine RPCs."""
from EasyCells3D.NetworkComponents import NetworkComponent, NetworkManager, NetworkVariable, Rpc, SendTo
from .catalog import HEROES, CELLS, BACTERIA, can_select


class Session(NetworkComponent):
    def __init__(self, manager, name):
        super().__init__(identifier=100, owner=0)
        self.manager, self.name = manager, name[:20]
        roster = {0: dict(owner=0, hero="neutrophil", team=CELLS, name=self.name, bot=False)} if manager.is_server else {}
        self.roster = NetworkVariable(roster, identifier=101, owner=0)
        self.status = "lobby"
        self.result = None
        self.arena = None
        self.error = ""
        self.joined = manager.is_server
        self.ready_peers = set()
        manager.disconnect_callbacks.append(self.disconnected)

    @property
    def local_slot(self):
        return self.slot_for_peer(self.manager.id)

    def slot_for_peer(self, peer_id):
        return next((slot for slot, p in self.roster.value.items() if p["owner"] == peer_id and not p["bot"]), None)

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def join(self, peer_id, name):
        if self.slot_for_peer(peer_id) is not None:
            return
        if self.status != "lobby" or len(self.roster.value) >= 6:
            self.manager.call_rpc_on_client(peer_id, self.show_error, "Sala cheia ou partida em andamento.")
            return
        roster = self.roster.value.copy()
        cells = sum(p["team"] == CELLS for p in roster.values())
        bacteria = sum(p["team"] == BACTERIA for p in roster.values())
        team = CELLS if cells <= bacteria else BACTERIA
        slot = next(s for s in (range(3) if team == CELLS else range(3, 6)) if s not in roster)
        hero = next(h for h in HEROES if can_select(h, team, roster))
        roster[slot] = dict(owner=peer_id, hero=hero, team=team, name=str(name)[:20], bot=False)
        self.roster.value = roster

    @Rpc(send_to=SendTo.CLIENTS)
    def show_error(self, message):
        self.error = message

    def choose(self, hero):
        self.choose_hero(self.manager.id, hero)

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def choose_hero(self, peer_id, hero):
        slot = self.slot_for_peer(peer_id)
        if slot is None or hero not in HEROES:
            return
        roster = {s: p.copy() for s, p in self.roster.value.items()}
        team = HEROES[hero].team
        if self.status == "lobby":
            if not can_select(hero, team, roster, exclude=slot):
                return
            if team != roster[slot]["team"]:
                target = next((s for s in (range(3) if team == CELLS else range(3, 6)) if s not in roster), None)
                if target is None:
                    return
                roster[target] = roster.pop(slot)
                slot = target
            roster[slot].update(hero=hero, team=team)
        elif self.status == "playing" and self.arena:
            actor, state = self.arena.actors[slot], self.arena.state
            if actor.alive or not can_select(hero, actor.team, roster, state.recognition, state.infected, slot):
                return
            roster[slot]["hero"] = hero
        self.roster.value = roster

    def start(self, fill_bots=False):
        if not self.manager.is_server or self.status != "lobby":
            return
        roster = self.roster.value.copy()
        if len(roster) < 6 and not fill_bots:
            self.error = "O 3v3 precisa de 6 jogadores. Use treino para completar com bots."
            return
        for slot in range(6):
            if slot not in roster:
                team = CELLS if slot < 3 else BACTERIA
                hero = next(h for h in HEROES if can_select(h, team, roster))
                roster[slot] = dict(owner=0, hero=hero, team=team, name=f"BOT {slot+1}", bot=True)
        self.roster.value = roster
        self.set_status("loading")

    @Rpc(send_to=SendTo.ALL)
    def set_status(self, status):
        self.status = status

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def ready(self, peer_id):
        self.ready_peers.add(peer_id)

    @Rpc(send_to=SendTo.ALL)
    def finish(self, result):
        self.result = result
        self.status = "results"

    def disconnected(self, peer_id):
        if not self.manager.is_server:
            self.error = "O anfitriao desconectou. Volte ao menu para entrar em outra sala."
            return
        slot = self.slot_for_peer(peer_id)
        if slot is None:
            return
        roster = self.roster.value.copy()
        if self.status == "lobby":
            del roster[slot]
        else:
            roster[slot] = dict(roster[slot], bot=True, owner=0, name=f"BOT {slot+1}")
        self.roster.value = roster

    def loop(self):
        self.error = self.error or self.manager.error
        if not self.joined and self.manager.id >= 0:
            self.joined = True
            self.join(self.manager.id, self.name)
        if self.manager.is_server and self.status == "loading":
            peers = {p["owner"] for p in self.roster.value.values()}
            if peers <= self.ready_peers:
                self.set_status("playing")

    def on_destroy(self):
        self.manager.disconnect_callbacks.remove(self.disconnected)
        super().on_destroy()


def connect(game, ip, port, host, name):
    item = game.CreateItem()
    item.name = "Lobby and connection"
    item.destroy_on_load = False
    try:
        manager = item.AddComponent(NetworkManager(ip=ip, port=port, is_server=host))
        game.session = item.AddComponent(Session(manager, name))
    except OSError:
        item.Destroy()
        raise
    return game.session


def disconnect(game):
    if getattr(game, "session", None):
        game.session.item.Destroy()
        game.session = None
