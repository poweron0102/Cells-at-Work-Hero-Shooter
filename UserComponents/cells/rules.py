"""Authoritative objective rules; stress never decides the winner."""
from dataclasses import dataclass, field, asdict
from .catalog import CELLS, BACTERIA, PHASE_SECONDS


@dataclass
class MatchState:
    phase: int = 0
    remaining: float = PHASE_SECONDS[0]
    elapsed: float = 0
    stress: float = 8
    recognition: float = 0
    immune_cooldown: float = 0
    capture: list = field(default_factory=lambda: [0., 0., 0.])
    cores: list = field(default_factory=lambda: [360., 360.])
    maturity: float = 0
    infected: bool = False
    winner: str = ""
    event: str = ""
    event_time: float = 0
    event_warning: float = 0
    next_event: float = 32
    event_index: int = 0
    notice: str = "Defenda as entradas A, B e C"
    notice_time: float = 6

    def announce(self, text):
        self.notice, self.notice_time = text, 5

    def antigen(self, amount):
        old = self.recognition
        self.recognition = min(100, self.recognition + amount)
        if old < 50 <= self.recognition:
            self.announce("ANTIGENO IDENTIFICADO - B Cell disponivel no respawn")

    def response(self):
        if self.immune_cooldown > 0 or self.winner:
            return False
        self.immune_cooldown = 45
        self.stress = min(100, self.stress + 16)
        return True

    def advance(self):
        self.phase += 1
        self.remaining = PHASE_SECONDS[self.phase]
        self.stress = min(100, self.stress + 12)
        self.announce("Colete amostras; impeça a colonizacao" if self.phase == 1
                      else "TECIDO INFECTADO - destrua os dois nucleos; Killer T liberado")
        if self.phase == 2:
            self.infected = True

    def tick(self, dt, presence):
        if self.winner:
            return
        self.elapsed += dt
        self.remaining -= dt
        self.immune_cooldown = max(0, self.immune_cooldown - dt)
        self.notice_time = max(0, self.notice_time - dt)
        self.stress = min(100, self.stress + dt * (.045 + (.12 * sum(c > 0 for c in self.cores) if self.phase else 0)))
        if self.phase == 0:
            for i, (cells, bacteria) in enumerate(presence):
                if self.capture[i] >= 100:
                    continue
                if bacteria and not cells:
                    self.capture[i] = min(100, self.capture[i] + dt * 7 * min(2, bacteria))
                elif cells and not bacteria:
                    self.capture[i] = max(0, self.capture[i] - dt * 4)
            if sum(c >= 100 for c in self.capture) >= 2:
                self.advance()
            elif self.remaining <= 0:
                self.winner = CELLS
        elif self.phase == 1:
            if all(c <= 0 for c in self.cores):
                self.winner = CELLS
            elif self.remaining <= 0 or self.recognition >= 50:
                self.advance()
        else:
            living = sum(c > 0 for c in self.cores)
            self.maturity = min(100, self.maturity + dt * living * .34)
            if not living:
                self.winner = CELLS
            elif self.maturity >= 100:
                self.winner = BACTERIA
            elif self.remaining <= 0:
                self.winner = CELLS

    def serialize(self):
        return asdict(self)
