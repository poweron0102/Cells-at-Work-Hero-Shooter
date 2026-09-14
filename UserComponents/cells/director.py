"""Physiological events affect both teams and never award a victory."""

EVENTS = ("coagulation", "blood_flow", "inflammation", "fever")
LABELS = {"coagulation": "COAGULACAO: plaquetas fecharao a passagem central",
          "blood_flow": "FLUXO SANGUINEO: corrente nas rotas laterais",
          "inflammation": "INFLAMACAO: tecido central reduz movimento",
          "fever": "FEBRE: regeneracao suspensa para ambos os times"}


class StressDirector:
    def __init__(self, arena):
        self.arena = arena

    def tick(self, dt):
        a, s = self.arena, self.arena.state
        if s.winner:
            return
        if s.event_warning > 0:
            s.event_warning = max(0, s.event_warning-dt)
            if s.event_warning == 0:
                s.event_time = 12
        elif s.event_time > 0:
            s.event_time = max(0, s.event_time-dt)
            if s.event_time == 0:
                s.event = ""
                s.next_event = max(14, 42-s.stress*.25)
        else:
            s.next_event -= dt
            if s.next_event <= 0:
                s.event = EVENTS[s.event_index % len(EVENTS)]
                s.event_index += 1
                s.event_warning = 4
                s.announce(LABELS[s.event])
        closing = s.event == "coagulation" and s.event_time > 0
        if closing and not a.gate.enable:
            # Clear the announced gate volume before enabling its collider.
            for actor in a.actors.values():
                p = actor.transform.position
                if actor.local and actor.alive and abs(p.x) < 3.6 and abs(p.z-7) < 1.1:
                    from EasyCells3D.Geometry import Vec3
                    actor.body.teleport(Vec3(p.x, p.y, 5.6 if p.z < 7 else 8.4))
        a.gate.enable = closing
