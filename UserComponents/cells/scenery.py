"""Batched city architecture inspired by Cellular-Odyssey-2's district renderer."""
import math
import pyray as rl
from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3
from .art import MeshBuilder, color, tint, CREAM, INK, TEAL, GOLD
from .layout import WIDTH, LENGTH, SOLIDS, RAMPS


class DistrictScenery(Renderable3D):
    def __init__(self):
        self.models = []

    def _build(self):
        mesh = MeshBuilder()
        def box(p, s, c):
            nonlocal mesh
            mesh.box(Vec3(*p), Vec3(*s), c)
            if len(mesh.vertices) > 150000:
                self.models.append(mesh.upload())
                mesh = MeshBuilder()
        # Paving variation and seams are actual geometry, baked once into batches.
        for x in range(-48, 48, 4):
            for z in range(-60, 60, 4):
                road = abs(x+2) < 7 or 22 < abs(x+2) < 32 or abs(z+2) < 8
                shade = color(167, 173, 158) if road else color(216, 201, 172)
                box((x+2, -.08, z+2), (3.97, .16, 3.97), tint(shade, 1 if (x+z)%8 else .965))
        for x in (-28, 0, 28):
            for z in range(-54, 57, 6):
                box((x, .015, z), (.16, .025, 2), CREAM)
        for solid in SOLIDS:
            if solid.name == 'Perimeter':
                continue
            p, s, c = solid.position, solid.size, color(*solid.tint)
            box(p, s, c)
            x, y, z = p
            w, h, d = s
            if solid.facade:
                self._facade(box, p, s, c)
            elif solid.name == 'Oxygen freight':
                box((x, y+.3, z), (w+.03, .16, d+.03), GOLD)
                box((x, y, z+d/2+.025), (w*.6, .65, .04), CREAM)
                for dx in (-1.2, 1.2):
                    box((x+dx, y, z), (.15, h+.04, d+.06), INK)
            elif 'gallery' in solid.name.lower() or 'bridge' in solid.name.lower() or 'landing' in solid.name:
                for offset in (-d/2+.15, d/2-.15):
                    box((x, solid.top+.018, z+offset), (w, .03, .18), GOLD)
                for dx in range(math.ceil(-w/2)+1, math.floor(w/2), 2):
                    box((x+dx, solid.top+.014, z), (.04, .02, d-.4), CREAM)
        # Distant facades form a city skyline behind the collision boundary.
        for side in (-1, 1):
            for z in range(-54, 55, 12):
                h = 15 + ((z+54)//12 % 3)*4
                p, size = (side*52, h/2, z), (8, h, 12)
                c = color(176, 158, 137) if z%24 else color(155, 177, 161)
                box(p, size, c)
                self._facade(box, p, size, c)
        for side in (-1, 1):
            for x in range(-42, 43, 12):
                h = 12 + (abs(x)//12 % 3)*3
                p, size = (x, h/2, side*64), (12, h, 8)
                c = color(184, 152, 134)
                box(p, size, c)
                self._facade(box, p, size, c)
        # Ribbed access ramps: fine visual steps over a continuous physical slope.
        for ramp in RAMPS:
            for i in range(64):
                t = (i+.5)/64
                z = ramp.start_z+(ramp.end_z-ramp.start_z)*t
                h = ramp.height*t
                box((ramp.x, h/2, z), (ramp.width, h, .25), tint(TEAL, 1 if i%2 else .9))
                for dx in (-ramp.width/2+.12, ramp.width/2-.12):
                    box((ramp.x+dx, h+.02, z), (.18, .035, .25), GOLD)
        if mesh.vertices:
            self.models.append(mesh.upload())

    @staticmethod
    def _facade(box, p, s, c):
        x, y, z = p
        w, h, d = s
        roof = y+h/2
        box((x, roof-.1, z), (w+.08, .24, d+.08), CREAM)
        box((x, .22, z), (w+.08, .44, d+.08), tint(c, .75))
        for floor in range(1, int(h)-1, 3):
            box((x, floor-.12, z), (w+.08, .14, d+.08), CREAM)
            for side in (-1, 1):
                for dx in range(-int(w/2)+2, int(w/2), 3):
                    zz = z+side*(d/2+.025)
                    box((x+dx, floor+1, zz), (1.5, 1.55, .06), INK)
                    box((x+dx, floor+1, zz+side*.04), (1.28, 1.3, .045), color(101, 145, 139))
                    box((x+dx, floor+1, zz+side*.07), (.09, 1.3, .035), CREAM)
                for dz in range(-int(d/2)+2, int(d/2), 3):
                    xx = x+side*(w/2+.025)
                    box((xx, floor+1, z+dz), (.06, 1.55, 1.5), INK)
                    box((xx+side*.04, floor+1, z+dz), (.045, 1.3, 1.28), color(101, 145, 139))
                    box((xx+side*.07, floor+1, z+dz), (.035, 1.3, .09), CREAM)
        for side in (-1, 1):
            xx, zz = x+side*(w/2-.25), z+d/2+.14
            box((xx, h/2, zz), (.23, h, .25), TEAL)
            for yy in range(1, int(h), 2):
                box((xx, yy, zz), (.33, .16, .33), GOLD)
        # Door and service plaque add human scale without implying an open interior.
        box((x, 1.1, z+d/2+.08), (1.8, 2.2, .1), TEAL)
        box((x, 2.65, z+d/2+.1), (2.5, .5, .12), GOLD)
        box((x+.55, 1.05, z+d/2+.16), (.08, .28, .06), CREAM)

    def render(self):
        if not self.models:
            self._build()
        for model in self.models:
            rl.draw_model(model, rl.Vector3(0, 0, 0), 1, rl.WHITE)

    def on_destroy(self):
        super().on_destroy()
        for model in self.models:
            rl.unload_model(model)
        self.models.clear()
