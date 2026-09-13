"""Combat renderers registered in the engine's Camera3D."""
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
        self.model = None
        self.last_position = None
        self.phase = 0

    def on_destroy(self):
        from .model_lighting import release
        super().on_destroy()
        release()

    def render(self):
        from .models import CharacterModel
        a = self.actor
        if not a.alive or a.slot == self.game.session.local_slot:
            return
        if self.model is None or self.model.hero != a.hero:
            self.model = CharacterModel(a.hero)
        p = a.transform.position
        distance = (p-self.last_position).magnitude() if self.last_position else 0
        self.last_position = Vec3(p.x, p.y, p.z)
        self.phase += min(distance, .5)*5
        self.model.draw(p-Vec3(0, .95, 0), a.yaw, self.phase, distance > .002, a.reveal, a.shield)
        ring = color((80, 224, 189) if a.team == CELLS else (236, 155, 99))
        # Foot ring follows the actor onto roofs instead of remaining on the street.
        rl.draw_cylinder_wires((p-Vec3(0, .92, 0)).to_raylib(), .57, .57, .02, 20, ring)
        if a.shield > 0:
            rl.draw_sphere_wires(p.to_raylib(), 1.0, 8, 8, color((126, 206, 244)))


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
            rl.draw_sphere(rl.Vector3(x, y-.55 + .1 * math.sin(s.elapsed * 3), z), .24, color((138, 241, 211)))
        for zone in arena.zones:
            x, y, z = zone["pos"]
            tint = (93, 160, 133) if zone["kind"] == "biofilm" else (157, 121, 189)
            rl.draw_cylinder(rl.Vector3(x, y-.89, z), zone["radius"], zone["radius"], .07, 32, color(tint))
            if zone["kind"] == "cloud":
                rl.draw_sphere_wires(rl.Vector3(x, y, z), zone["radius"], 10, 12, color(tint))
        for shot in arena.tracers:
            rl.draw_line_3d(Vec3(*shot["a"]).to_raylib(), Vec3(*shot["b"]).to_raylib(), color((255, 228, 129)))
        if s.event == "coagulation" and s.event_time > 0:
            rl.draw_cube(rl.Vector3(0, 1.8, 7), 6, 3.6, .8, color((232, 184, 109)))
        # Reuse the imported platelet rig for the repair crew.
        from .models import CharacterModel
        if not hasattr(self, 'platelet'):
            self.platelet = CharacterModel('platelet')
        for x in (-6.5, 6.5):
            self.platelet.draw(Vec3(x, 0, 8), phase=s.elapsed, moving=False)
