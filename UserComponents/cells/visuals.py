"""Blockout renderers registered in the engine's Camera3D."""
import math
import pyray as rl
from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3
from .catalog import HEROES, CELLS, POINTS, CORE_POSITIONS


def color(rgb, alpha=255):
    return rl.Color(*rgb[:3], alpha)


class Block(Renderable3D):
    def __init__(self, size, tint):
        self.size, self.tint = size, tint

    def render(self):
        p = self.global_transform.position.to_raylib()
        rl.draw_cube_v(p, self.size.to_raylib(), color(self.tint))
        rl.draw_cube_wires_v(p, self.size.to_raylib(), color(tuple(int(v * .77) for v in self.tint)))


class CombatantVisual(Renderable3D):
    def __init__(self, actor):
        self.actor = actor

    def render(self):
        a = self.actor
        if not a.alive or a.slot == self.game.session.local_slot:
            return
        p = a.transform.position
        tint = color(HEROES[a.hero].color)
        dark = color((42, 48, 53))
        if a.team == CELLS:
            rl.draw_cube(Vec3(p.x, p.y, p.z).to_raylib(), .7, .8, .4, tint)
            rl.draw_sphere(Vec3(p.x, p.y + .63, p.z).to_raylib(), .25, color((249, 211, 185)))
            rl.draw_cube(Vec3(p.x, p.y + .86, p.z).to_raylib(), .62, .13, .52, tint)
            for dx in (-.2, .2):
                rl.draw_cube(Vec3(p.x + dx, p.y - .64, p.z).to_raylib(), .22, .55, .27, tint)
            rl.draw_cube(Vec3(p.x + .45, p.y + .1, p.z - .2).to_raylib(), .17, .18, .72, dark)
        else:
            rl.draw_sphere(p.to_raylib(), .72, tint)
            for i in range(6):
                angle = i * math.tau / 6
                tip = p + Vec3(math.cos(angle) * .95, math.sin(angle) * .55, 0)
                rl.draw_cylinder_ex(p.to_raylib(), tip.to_raylib(), .16, .035, 5, tint)
            for dx in (-.24, .24):
                rl.draw_sphere((p + Vec3(dx, .23, .59)).to_raylib(), .14, rl.WHITE)
                rl.draw_sphere((p + Vec3(dx, .23, .71)).to_raylib(), .07, dark)
        ring = color((80, 224, 189) if a.team == CELLS else (236, 155, 99))
        rl.draw_cylinder(Vec3(p.x, .035, p.z).to_raylib(), .72, .72, .025, 24, ring)
        if a.shield > 0:
            rl.draw_sphere_wires(p.to_raylib(), .95, 8, 8, color((126, 206, 244)))


class ArenaEffects(Renderable3D):
    def __init__(self, arena):
        self.arena = arena

    def render(self):
        arena = self.arena
        s = arena.state
        for i, (x, z) in enumerate(POINTS):
            tint = color((236, 128, 76) if s.capture[i] >= 100 else (76, 184, 173))
            rl.draw_cylinder(rl.Vector3(x, .015, z), 3, 3, .025, 48, tint)
            rl.draw_cylinder_wires(rl.Vector3(x, .04, z), 3.1, 3.1, .06, 32, rl.WHITE)
        if s.phase >= 1:
            for i, (x, z) in enumerate(CORE_POSITIONS):
                if s.cores[i] <= 0:
                    continue
                rl.draw_sphere(rl.Vector3(x, 1.1, z), 1.1, color((168, 88, 181)))
                rl.draw_sphere_wires(rl.Vector3(x, 1.1, z), 1.2 + .08 * math.sin(s.elapsed * 3), 8, 10, color((244, 190, 111)))
        for sample in arena.samples:
            x, y, z = sample["pos"]
            rl.draw_sphere(rl.Vector3(x, .4 + .1 * math.sin(s.elapsed * 3), z), .24, color((138, 241, 211)))
        for zone in arena.zones:
            x, y, z = zone["pos"]
            tint = (93, 160, 133) if zone["kind"] == "biofilm" else (157, 121, 189)
            rl.draw_cylinder(rl.Vector3(x, .06, z), zone["radius"], zone["radius"], .07, 32, color(tint))
            if zone["kind"] == "cloud":
                rl.draw_sphere_wires(rl.Vector3(x, 1, z), zone["radius"], 10, 12, color(tint))
        for shot in arena.tracers:
            rl.draw_line_3d(Vec3(*shot["a"]).to_raylib(), Vec3(*shot["b"]).to_raylib(), color((255, 228, 129)))
        if s.event == "coagulation" and s.event_time > 0:
            rl.draw_cube(rl.Vector3(0, 1.8, 7), 6, 3.6, .8, color((232, 184, 109)))
        # Passive platelets repair the passage; they never act as combatants.
        for x in (-4, 4):
            rl.draw_cube(rl.Vector3(x, .65, 8), .5, .8, .35, color((130, 202, 224)))
            rl.draw_sphere(rl.Vector3(x, 1.25, 8), .22, color((245, 211, 172)))
            rl.draw_cube(rl.Vector3(x, 1.45, 8), .62, .13, .5, rl.RAYWHITE)
