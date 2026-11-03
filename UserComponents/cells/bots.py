"""Bots de treino: usam o mesmo caminho de comandos dos jogadores humanos.

Celulas: escolta, protecao de hemacias, coleta de antigenos, caca a colonias
e reconhecimento. Bacterias: bloqueio da escolta, caca a hemacias, coleta de
recursos, construcao e desenvolvimento de colonias.
"""
import math
from EasyCells3D.Geometry import Vec3
from .catalog import CELLS, HEROES, BALANCE
from .layout import COLONY_HINTS, RECON


def _v(p):
    return Vec3(p[0], p[1]+.95, p[2])


class BotBrain:
    def __init__(self, arena):
        self.arena = arena
        self.paths = {}
        self.next_path = {}
        self.goal = {}
        self.stuck = {}

    # -- objetivos --------------------------------------------------------
    def cell_goal(self, actor):
        a, s = self.arena, self.arena.state
        feet = actor.feet
        role = actor.slot % 3
        antigens = [d for d in a.drops if d['kind'] == 'antigen' and math.dist(d['pos'], feet) < 22]
        if antigens:
            return _v(min(antigens, key=lambda d: math.dist(d['pos'], feet))['pos']), 'coletar'
        resources = [d for d in a.drops if d['kind'] == 'resource' and math.dist(d['pos'], feet) < 14]
        if resources:
            return _v(resources[0]['pos']), 'destruir recurso'
        known = [c for c in s.colonies if s.reveal > 0 or math.dist(c['pos'], feet) < 30]
        if known and (role == 2 or s.wound_closed):
            return _v(min(known, key=lambda c: math.dist(c['pos'], feet))['pos']), 'colonia'
        if s.wound_closed:
            if s.recon_available() and role == 0:
                return _v(RECON), 'reconhecimento'
            spot = COLONY_HINTS[(actor.slot*5+int(s.elapsed//25)) % len(COLONY_HINTS)]
            return _v(spot), 'patrulha'
        if role == 1:
            threatened = [c for c in a.rbc_view.cells.values() if c['state'] in ('flee', 'hide')]
            if threatened:
                return _v(min(threatened, key=lambda c: math.dist(c['pos'], feet))['pos']), 'proteger'
        head = a.path.at(min(s.escort_total, s.escort+3+role*2))
        return _v(head), 'escolta'

    def bacteria_goal(self, actor):
        a, s = self.arena, self.arena.state
        feet = actor.feet
        carried = s.resources.get(actor.slot, 0)
        own = s.colonies_of(actor.slot)
        if carried >= BALANCE['colony_cost'] and len(own) < BALANCE['colony_limit']:
            free = [h for h in COLONY_HINTS
                    if all(math.dist(h, c['pos']) > 5 for c in s.colonies) and math.dist(h, feet) < 70]
            if free:
                spot = min(free, key=lambda h: math.dist(h, feet)+(actor.slot*7) % 11)
                return _v(spot), 'construir'
        if carried > 0 and s.colonies:
            target = min(s.colonies, key=lambda c: math.dist(c['pos'], feet))
            if target['dev'] < BALANCE['colony_dev_cap']:
                return _v(target['pos']), 'desenvolver'
        resources = [d for d in a.drops if d['kind'] == 'resource']
        if resources:
            return _v(min(resources, key=lambda d: math.dist(d['pos'], feet))['pos']), 'recolher'
        if actor.slot % 3 == 0 and not s.wound_closed:
            head = a.path.at(min(s.escort_total, s.escort+4))
            return _v(head), 'bloquear'
        rbcs = [c for c in a.rbc_view.cells.values() if c['state'] not in ('dead', 'inside')]
        if rbcs:
            return _v(min(rbcs, key=lambda c: math.dist(c['pos'], feet))['pos']), 'cacar'
        return _v(COLONY_HINTS[actor.slot % len(COLONY_HINTS)]), 'patrulha'

    # -- comando ----------------------------------------------------------
    def command(self, actor):
        arena = self.arena
        state = arena.state
        position = actor.transform.position
        target, intent = self.cell_goal(actor) if actor.team == CELLS else self.bacteria_goal(actor)
        self.goal[actor.slot] = intent
        enemies = sorted((a for a in arena.actors.values() if a.team != actor.team and a.alive),
                         key=lambda a: (a.transform.position-position).magnitude())
        enemy = next((a for a in enemies if (a.transform.position-position).magnitude() < 28 and arena.visible(actor, a)), None)
        if arena.navigator and state.elapsed >= self.next_path.get(actor.slot, 0):
            self.paths[actor.slot] = arena.navigator.path(position, target, HEROES[actor.hero].jump_height)
            self.next_path[actor.slot] = state.elapsed + 1.5 + actor.slot*.07
        path = self.paths.get(actor.slot, [])
        while path and Vec3(path[0].x-position.x, 0, path[0].z-position.z).magnitude() < 1.1:
            path.pop(0)
        waypoint = path[0] if path else target
        move = waypoint-position
        aim = None
        fire = False
        secondary = False
        if enemy:
            aim = enemy.transform.position-position
            fire = True
            secondary = aim.magnitude() < 2.5 and actor.hero in ('neutrophil', 'macrophage', 'killer_t', 'streptococcus')
        elif actor.team != CELLS and intent == 'cacar':
            near = [c for c in arena.rbc_view.cells.values() if c['state'] not in ('dead', 'inside')
                    and math.dist(c['pos'], actor.feet) < 20]
            if near:
                c = min(near, key=lambda c: math.dist(c['pos'], actor.feet))
                aim = Vec3(c['pos'][0], c['pos'][1]+.9, c['pos'][2])-position-Vec3(0, .56, 0)
                fire = arena.clear_line((position.x, position.y+.56, position.z), (c['pos'][0], c['pos'][1]+1, c['pos'][2]))
                secondary = actor.hero == 'streptococcus' and aim.magnitude() < 2.4
        elif actor.team == CELLS and intent == 'colonia':
            c = target
            aim = Vec3(c.x, c.y+.2, c.z)-position-Vec3(0, .56, 0)
            fire = aim.magnitude() < 30
        building = intent == 'construir' and (target-position).magnitude() < 2.2
        if aim is None:
            aim = move
        if building:
            aim = Vec3(target.x-position.x, -1.4, target.z-position.z)
        yaw = math.atan2(aim.x, -aim.z) if abs(aim.x)+abs(aim.z) > .01 else actor.yaw
        pitch = math.atan2(aim.y, max(.01, math.hypot(aim.x, aim.z)))
        if enemy:
            yaw += math.sin(state.elapsed*2+actor.slot)*.035
        forward_x, forward_z = math.sin(yaw), -math.cos(yaw)
        length = max(.001, math.hypot(move.x, move.z))
        close = 1.0 if intent in ('construir', 'desenvolver', 'coletar', 'recolher', 'reconhecimento') else 2.2
        moving = (target-position).magnitude() > close and not building
        if enemy and (enemy.transform.position-position).magnitude() < 7 and intent not in ('escolta', 'bloquear'):
            moving = moving and actor.hero in ('neutrophil', 'killer_t', 'streptococcus')
        speed = actor.body.velocity.magnitude()
        stuck = self.stuck.get(actor.slot, 0)
        stuck = stuck+1 if moving and speed < .4 else 0
        self.stuck[actor.slot] = stuck
        return dict(yaw=yaw, pitch=pitch,
                    x=(move.x*math.cos(yaw)+move.z*math.sin(yaw))/length if moving else 0,
                    z=(move.x*forward_x+move.z*forward_z)/length if moving else 0,
                    fire=fire, secondary=secondary, sprint=not fire, reload=actor.weapon.ammo == 0,
                    interact=intent == 'desenvolver' and (target-position).magnitude() < 3 and not actor.previous.get('interact'),
                    build=building,
                    ability=bool(enemy) and actor.ability_cd <= 0 and (enemy.transform.position-position).magnitude() < 12
                    and not actor.previous.get('ability'),
                    ultimate=actor.charge >= 100 and bool(enemy) and not actor.previous.get('ultimate'),
                    jump=actor.controller.is_grounded and ((bool(path) and waypoint.y > position.y+.7) or stuck > 25))
