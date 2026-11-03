"""Regras compartilhadas: escolta, colonias, infeccao, antigenos e vitoria.

Puro Python (testavel sem GPU/rede). O servidor executa ``tick`` e envia
``snapshot()`` aos clientes; acoes de jogadores chegam como pedidos validados.
"""
import math
from dataclasses import dataclass, field
from .catalog import CELLS, BACTERIA, BALANCE, HEROES


class EscortPath:
    """Polyline percorrida pelas plaquetas; progresso em metros."""

    def __init__(self, points):
        self.points = [tuple(p) for p in points]
        self.lengths = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            self.lengths.append(self.lengths[-1]+math.dist(a, b))
        self.total = self.lengths[-1]

    def at(self, progress):
        progress = max(0.0, min(self.total, progress))
        for i in range(1, len(self.points)):
            if progress <= self.lengths[i] or i == len(self.points)-1:
                a, b = self.points[i-1], self.points[i]
                seg = max(1e-6, self.lengths[i]-self.lengths[i-1])
                t = (progress-self.lengths[i-1])/seg
                return tuple(a[k]+(b[k]-a[k])*t for k in range(3))
        return self.points[-1]

    def direction(self, progress):
        a, b = self.at(progress), self.at(progress+.5)
        d = (b[0]-a[0], b[2]-a[2])
        m = math.hypot(*d) or 1
        return d[0]/m, d[1]/m


def escort_blockers(path, progress, bacteria):
    """Bacterias vivas numa faixa curta a frente, na mesma passagem.

    ``bacteria`` = [(slot, (x, y, z), visible_bool)], onde ``visible`` indica
    linha de visao desobstruida ate a escolta (paredes nao bloqueiam por proximidade).
    """
    if progress >= path.total:
        return []
    head = path.at(progress)
    dx, dz = path.direction(progress)
    reach = BALANCE['escort_block_distance']
    out = []
    for slot, p, visible in bacteria:
        rx, rz = p[0]-head[0], p[2]-head[2]
        ahead = rx*dx+rz*dz
        side = abs(-rx*dz+rz*dx)
        # Feet height comparison: the actor position is the capsule centre (+.95).
        same_level = abs((p[1]-.95)-head[1]) <= BALANCE['escort_block_height']
        if -1.5 <= ahead <= reach and side <= 3.2 and same_level and visible:
            out.append(slot)
    return out


@dataclass
class MatchState:
    elapsed: float = 0.0
    winner: str = ""
    notice: str = "Escolte as plaquetas ate a ferida"
    notice_time: float = 6.0
    escort: float = 0.0
    escort_total: float = 150.0
    blocked_by: list = field(default_factory=list)
    wound_closed: bool = False
    recognition: float = 0.0
    colonies: list = field(default_factory=list)
    next_colony: int = 1
    resources: dict = field(default_factory=dict)
    recon: float = 0.0
    recon_by: int = -1
    reveal: float = 0.0
    recon_cooldown: float = 0.0
    bacteria_alive: int = 0
    feed: list = field(default_factory=list)

    # -- avisos -----------------------------------------------------------
    def announce(self, text, seconds=5.0):
        self.notice, self.notice_time = text, seconds
        self.feed = (self.feed+[text])[-5:]

    # -- antigenos / desbloqueios ------------------------------------------
    def antigen(self, amount):
        old = self.recognition
        self.recognition = min(100.0, self.recognition+amount)
        for hero, key in (("b_cell", "unlock_b_cell"), ("killer_t", "unlock_killer_t")):
            if old < BALANCE[key] <= self.recognition:
                self.announce(f"RESPOSTA ESPECIFICA: {HEROES[hero].name} liberado no respawn")

    # -- colonias ---------------------------------------------------------
    def colonies_of(self, slot):
        return [c for c in self.colonies if c["owner"] == slot]

    def colony(self, colony_id):
        return next((c for c in self.colonies if c["id"] == colony_id), None)

    def contribution(self, colony):
        return BALANCE['colony_base_infection']+colony["dev"]

    def infection(self):
        return sum(self.contribution(c) for c in self.colonies)

    def protection(self, colony_id):
        """Reducao de dano concedida pelas OUTRAS colonias concluidas (com teto)."""
        others = sum(1 for c in self.colonies if c["id"] != colony_id)
        target = self.colony(colony_id)
        bonus = .15 if target and target.get("fortified", 0) > 0 else 0
        weakened = .5 if target and target.get("marked", 0) > 0 else 1
        return min(BALANCE['colony_protection_cap'], others*BALANCE['colony_protection_each'])*weakened+bonus

    def build_problem(self, slot, resources):
        if self.winner:
            return "Partida encerrada"
        if len(self.colonies_of(slot)) >= BALANCE['colony_limit']:
            return f"Limite de {BALANCE['colony_limit']} colonias"
        if resources < BALANCE['colony_cost']:
            return f"Precisa de {BALANCE['colony_cost']} recursos"
        return ""

    def add_colony(self, slot, position):
        problem = self.build_problem(slot, self.resources.get(slot, 0))
        if problem:
            return None
        self.resources[slot] = self.resources.get(slot, 0)-BALANCE['colony_cost']
        colony = dict(id=self.next_colony, owner=slot, pos=tuple(position), hp=float(BALANCE['colony_health']),
                      dev=0.0, fortified=0.0, marked=0.0)
        self.next_colony += 1
        self.colonies.append(colony)
        self.announce("NOVA COLONIA bacteriana estabelecida")
        return colony

    def develop(self, slot, colony_id):
        colony = self.colony(colony_id)
        if not colony or self.resources.get(slot, 0) <= 0 or colony["dev"] >= BALANCE['colony_dev_cap']:
            return 0
        amount = min(self.resources[slot], math.ceil((BALANCE['colony_dev_cap']-colony["dev"])/BALANCE['colony_dev_per_resource']))
        self.resources[slot] -= amount
        colony["dev"] = min(BALANCE['colony_dev_cap'], colony["dev"]+amount*BALANCE['colony_dev_per_resource'])
        return amount

    def repair(self, colony_id, amount):
        colony = self.colony(colony_id)
        if colony:
            colony["hp"] = min(float(BALANCE['colony_health']), colony["hp"]+amount)

    def damage_colony(self, colony_id, amount):
        """Retorna True se a colonia foi destruida. Protecao nao cura nem altera vida perdida."""
        colony = self.colony(colony_id)
        if not colony or self.winner:
            return False
        colony["hp"] = max(0.0, colony["hp"]-amount*(1-self.protection(colony_id)))
        if colony["hp"] <= 0:
            self.colonies.remove(colony)
            self.announce("COLONIA DESTRUIDA - contribuicao de infeccao removida")
            return True
        return False

    # -- reconhecimento do mapa -----------------------------------------
    def recon_available(self):
        return self.wound_closed and self.recon_cooldown <= 0 and not self.winner

    def channel_recon(self, slot, dt, contested):
        if not self.recon_available() or contested:
            self.recon = max(0.0, self.recon-dt*2)
            return False
        self.recon_by = slot
        self.recon += dt
        if self.recon >= BALANCE['recon_channel']:
            self.recon = 0.0
            self.reveal = BALANCE['recon_reveal']
            self.recon_cooldown = BALANCE['recon_cooldown']
            self.announce("RECONHECIMENTO: colonias restantes reveladas")
            return True
        return False

    # -- relogio --------------------------------------------------------
    def tick(self, dt, blockers=(), bacteria_alive=0):
        if self.winner:
            return
        self.elapsed += dt
        self.notice_time = max(0.0, self.notice_time-dt)
        self.reveal = max(0.0, self.reveal-dt)
        self.recon_cooldown = max(0.0, self.recon_cooldown-dt)
        self.bacteria_alive = bacteria_alive
        for c in self.colonies:
            c["fortified"] = max(0.0, c.get("fortified", 0)-dt)
            c["marked"] = max(0.0, c.get("marked", 0)-dt)
        self.blocked_by = list(blockers)
        if not self.wound_closed and not self.blocked_by:
            self.escort = min(self.escort_total, self.escort+dt*BALANCE['escort_speed'])
            if self.escort >= self.escort_total:
                self.wound_closed = True
                self.announce("FERIDA FECHADA - a entrada bacteriana foi selada", 7)
        if self.infection() >= BALANCE['infection_goal']:
            self.winner = BACTERIA
        elif self.wound_closed and not self.colonies and bacteria_alive == 0:
            self.winner = CELLS

    def snapshot(self):
        return {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                for k, v in self.__dict__.items()}

    def apply(self, data):
        for k, v in data.items():
            if k == "resources":
                v = {int(s): n for s, n in v.items()}
            setattr(self, k, v)

    def serialize(self):
        return self.snapshot()
