"""Coração: batimento cardíaco e valvas (modo ``convoy``).

Puro Python e determinístico: o estado das valvas sai do relógio da partida
(``MatchState.elapsed``, replicado pelo servidor), da lista de valvas emperradas e da posição
do comboio. Cada par calcula sozinho, sem RPC por batida.

Ritmo (``balance.json``): um ciclo de ``heart_period`` segundos começa pela sístole
(``heart_systole`` s) e segue na diástole. Como no coração de verdade, as valvas se alternam:

* ``av`` (tricúspide, entre átrio e ventrículo): abre na diástole, fecha na sístole;
* ``semilunar`` (pulmonar, na saída do ventrículo): abre na sístole, fecha na diástole.

O comboio segura aberta a valva em que está passando (do batente até 2 m depois dela).
Uma colônia a até ``valve_jam_radius`` m da valva a emperra fechada (endocardite): nem o
comboio passa até as células destruírem a colônia.
"""
import math
from .catalog import BALANCE

HOLD_BEFORE = 1.5   # m antes da valva em que o comboio ja esta no vao (segura a valva)
HOLD_AFTER = 2.0    # m depois da valva ate o fim do vao
STOP_BEFORE = 2.0   # m antes da valva onde o comboio espera quando ela esta fechada


def beat(elapsed):
    """(sistole?, fracao do ciclo 0..1, segundos ate a proxima troca de fase)."""
    period = BALANCE['heart_period']
    systole = BALANCE['heart_systole']
    t = elapsed % period
    if t < systole:
        return True, t/period, systole-t
    return False, t/period, period-t


def rhythm_open(kind, elapsed):
    systole, _, _ = beat(elapsed)
    return systole if kind == 'semilunar' else not systole


def valve_progress(valve, path):
    """Distancia ao longo do caminho do comboio em que ele cruza a valva."""
    best, best_d = 0.0, math.inf
    pts = path.points
    for i in range(1, len(pts)):
        a, b = pts[i-1], pts[i]
        dx, dz = b[0]-a[0], b[2]-a[2]
        L2 = dx*dx+dz*dz or 1e-9
        p = valve['pos']
        t = max(0.0, min(1.0, ((p[0]-a[0])*dx+(p[2]-a[2])*dz)/L2))
        d = math.hypot(a[0]+dx*t-p[0], a[2]+dz*t-p[2])
        if d < best_d:
            best_d, best = d, path.lengths[i-1]+t*math.sqrt(L2)
    return best


def jammed_valves(valves, colonies):
    radius = BALANCE['valve_jam_radius']
    return [v['id'] for v in valves
            if any(math.hypot(c['pos'][0]-v['pos'][0], c['pos'][2]-v['pos'][2]) <= radius for c in colonies)]


def held(valve, escort, progress):
    """O comboio esta no vao desta valva (e a mantem aberta)."""
    return progress-HOLD_BEFORE <= escort <= progress+HOLD_AFTER


def is_open(valve, elapsed, jammed, escort, progress, sealed=False):
    if valve['id'] in jammed:
        return False
    if not sealed and held(valve, escort, progress):
        return True
    return rhythm_open(valve.get('kind', 'av'), elapsed)


def convoy_block(valves, progress_of, elapsed, jammed, escort):
    """Id da valva fechada logo a frente do comboio (que o faz esperar), ou -1."""
    for v in valves:
        p = progress_of[v['id']]
        if p-STOP_BEFORE-.05 <= escort < p-HOLD_BEFORE and not is_open(v, elapsed, jammed, escort, p):
            return v['id']
    return -1


def max_advance(valves, progress_of, elapsed, jammed, escort):
    """Ate onde o comboio pode ir neste instante (para no batente da proxima valva fechada)."""
    limit = math.inf
    for v in valves:
        p = progress_of[v['id']]
        if escort < p-HOLD_BEFORE and not is_open(v, elapsed, jammed, escort, p):
            limit = min(limit, p-STOP_BEFORE)
    return limit
