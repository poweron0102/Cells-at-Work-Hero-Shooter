"""Optional training opponents use the same input and combat path as humans."""
import math
from EasyCells3D.Geometry import Vec3
from .catalog import CELLS, POINTS, CORE_POSITIONS


class BotBrain:
    def __init__(self, arena):
        self.arena = arena
        self.paths = {}
        self.next_path = {}

    def command(self, actor):
        arena = self.arena
        state = arena.state
        position = actor.transform.position
        enemies = sorted((a for a in arena.actors.values() if a.team != actor.team and a.alive),
                         key=lambda a: (a.transform.position-position).magnitude())
        enemy = next((a for a in enemies if (a.transform.position-position).magnitude() < 28 and arena.visible(actor, a)), None)
        if actor.hero == "macrophage" and arena.samples:
            target = Vec3(*min(arena.samples, key=lambda s: (Vec3(*s["pos"])-position).magnitude())["pos"])
        elif state.phase == 0:
            choices = [i for i in range(3) if state.capture[i] < 100]
            i = choices[actor.slot % len(choices)] if choices else 1
            x, z = POINTS[i]
            target = Vec3(x, 1, z)
        else:
            choices = [i for i, hp in enumerate(state.cores) if hp > 0]
            i = choices[actor.slot % len(choices)] if choices else 0
            x, z = CORE_POSITIONS[i]
            target = Vec3(x, 1, z + (4 if actor.team != CELLS else 7))
        if state.elapsed >= self.next_path.get(actor.slot, 0):
            self.paths[actor.slot] = arena.navigator.path(position, target)
            self.next_path[actor.slot] = state.elapsed + 1.5
        path = self.paths.get(actor.slot, [])
        while path and (Vec3(path[0].x, position.y, path[0].z)-position).magnitude() < 1:
            path.pop(0)
        waypoint = path[0] if path else target
        move = waypoint-position
        aim = enemy.transform.position-position if enemy else move
        fire = bool(enemy)
        if not enemy and actor.team == CELLS and state.phase >= 1:
            i = min((i for i, hp in enumerate(state.cores) if hp > 0),
                    key=lambda i: (Vec3(CORE_POSITIONS[i][0], 1, CORE_POSITIONS[i][1])-position).magnitude(), default=None)
            if i is not None:
                core = Vec3(CORE_POSITIONS[i][0], 1.1, CORE_POSITIONS[i][1])
                hit = arena.game.physics_world.raycast(position+Vec3(0, .56, 0), core-position-Vec3(0, .56, 0), 32, 1|8)
                if hit and hit.body is arena.core_bodies[i]:
                    aim, fire = core-position-Vec3(0, .56, 0), True
        yaw = math.atan2(aim.x, -aim.z)
        pitch = math.atan2(aim.y, max(.01, math.hypot(aim.x, aim.z)))
        # Modest deterministic aim error leaves room for a human player to react.
        if enemy:
            yaw += math.sin(state.elapsed*2+actor.slot)*.035
        forward_x, forward_z = math.sin(yaw), -math.cos(yaw)
        length = max(.001, math.hypot(move.x, move.z))
        moving = (target-position).magnitude() > 2.0 and not (enemy and (enemy.transform.position-position).magnitude() < 9)
        return dict(yaw=yaw, pitch=pitch, x=(move.x*math.cos(yaw)+move.z*math.sin(yaw))/length if moving else 0,
                    z=(move.x*forward_x+move.z*forward_z)/length if moving else 0,
                    fire=fire, interact=True, sprint=not fire, reload=actor.weapon.ammo == 0,
                    ability=bool(enemy) and actor.hero not in ("neutrophil", "killer_t", "streptococcus"),
                    ultimate=bool(enemy) and actor.health < 90,
                    jump=bool(path) and actor.controller.is_grounded and actor.body.velocity.magnitude() < .5)
