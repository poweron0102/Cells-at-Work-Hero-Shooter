"""Geometria procedural do Bairro Arterial, usada pelo build no Blender.

Todas as coordenadas deste modulo estao no espaco do JOGO (raylib/glTF):
x = leste, y = cima, z = sul. O Blender usa (x, -z, y); a conversao acontece
somente na criacao dos objetos (ver ``build_distrito.py``).

Cada face guarda cor sRGB (0-255), um ``padrao`` interpretado pelo shader do
jogo (tijolo, pedra, ladrilho, agua animada...) e se deve ser suavizada.
Faces marcadas com ``collide`` tambem geram triangulos de colisao.
"""
import math
import random

# Padroes do shader (UV.x = id + 0.5). Mantenha em sincronia com scenery.py.
PLAIN, BRICK, FLAGSTONE, TILE, PLANK, WATER, ASHLAR, PLASTER, WINDOW, METAL, DIRT, ROOF, NET, GLOW, HAZARD, LEAF, TISSUE, GLASS = range(18)

# Paleta inspirada nas referencias: creme, ocre, terracota, agua clara.
CREAM = (244, 232, 208)
CREAM2 = (236, 220, 190)
PEACH = (240, 206, 176)
OCHRE = (226, 178, 104)
WOOD = (214, 160, 88)
TERRACOTTA = (198, 104, 78)
BRICK_C = (186, 104, 80)
BRICK_D = (156, 84, 66)
RED_ARCH = (216, 94, 88)
SALMON = (234, 146, 126)
BLUE_STEEL = (132, 154, 210)
IRON = (54, 54, 64)
PAVING = (232, 220, 198)
PAVING2 = (226, 206, 186)
STONE = (206, 196, 178)
STONE_D = (168, 158, 142)
WATER_C = (170, 214, 160)
LEAF_C = (112, 164, 92)
LEAF_D = (84, 132, 76)
TRUNK = (126, 92, 66)
WHITE = (242, 242, 238)
MINT = (178, 214, 192)
SKY_BLUE = (168, 206, 226)
TILE_C = (242, 200, 164)
SAND = (214, 188, 146)
WOUND = (88, 56, 62)
FLESH = (196, 120, 128)
NET_C = (236, 172, 196)
YELLOW = (238, 198, 72)
TEAL = (88, 168, 160)
GLASS_C = (190, 222, 230)
DARK = (44, 40, 46)


def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _dot(a, b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def _norm(v):
    m = math.sqrt(_dot(v, v)) or 1
    return (v[0]/m, v[1]/m, v[2]/m)


class Group:
    def __init__(self):
        self.verts = []
        self.faces = []  # (indices, color, pattern, smooth)


class Geo:
    def __init__(self, seed=7):
        self.groups = {}
        self.current = None
        self.collision = []  # triangles [(p0, p1, p2)]
        self.rng = random.Random(seed)
        self.spots = []
        self.overlays = []
        self.zone('base')

    def zone(self, name):
        self.current_name = name
        self.current = self.groups.setdefault(name, Group())
        return self

    # -- pisos decorativos sem sobreposicao (evita z-fight) -------------------
    def overlay(self, x0, z0, x1, z1, color, pat, priority=0, y=.025):
        """Floor finish over the ground. Higher priority wins; lower ones are cut around it."""
        self.overlays.append((priority, len(self.overlays), (min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)),
                              color, pat, y, self.current_name))

    def flush_overlays(self):
        def subtract(r, h):
            ax0, az0, ax1, az1 = r
            bx0, bz0, bx1, bz1 = h
            if bx0 >= ax1 or bx1 <= ax0 or bz0 >= az1 or bz1 <= az0:
                return [r]
            out = []
            if bz0 > az0:
                out.append((ax0, az0, ax1, bz0))
            if bz1 < az1:
                out.append((ax0, bz1, ax1, az1))
            mz0, mz1 = max(az0, bz0), min(az1, bz1)
            if bx0 > ax0:
                out.append((ax0, mz0, bx0, mz1))
            if bx1 < ax1:
                out.append((bx1, mz0, ax1, mz1))
            return out
        placed = []
        previous = self.current_name
        for priority, _, rect, color, pat, y, zone in sorted(self.overlays, key=lambda o: (-o[0], o[1])):
            pieces = [rect]
            for other in placed:
                pieces = [q for piece in pieces for q in subtract(piece, other)]
            self.zone(zone)
            for x0, z0, x1, z1 in pieces:
                if x1-x0 > .01 and z1-z0 > .01:
                    self.face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], color, pat, (0, 1, 0))
            placed.append(rect)
        self.overlays = []
        self.zone(previous)

    # -- primitivas ---------------------------------------------------------
    def face(self, pts, color, pat=PLAIN, outward=None, smooth=False, collide=False, visible=True):
        """Polygon with automatic winding: its normal points along ``outward``."""
        if outward is not None:
            n = _cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0]))
            if _dot(n, outward) < 0:
                pts = list(reversed(pts))
        if visible:
            g = self.current
            base = len(g.verts)
            g.verts.extend(pts)
            g.faces.append((tuple(range(base, base+len(pts))), color, pat, smooth))
        if collide:
            for i in range(1, len(pts)-1):
                self.collision.append((pts[0], pts[i], pts[i+1]))

    def box(self, c, s, color, pat=PLAIN, collide=True, ry=0.0, skip=(), visible=True, top=None, pats=None):
        """Axis box (optionally rotated about Y). ``top``/``pats`` override per face."""
        hx, hy, hz = s[0]/2, s[1]/2, s[2]/2
        cs, sn = math.cos(ry), math.sin(ry)

        def P(x, y, z):
            return (c[0]+x*cs+z*sn, c[1]+y, c[2]-x*sn+z*cs)

        def D(x, y, z):
            return (x*cs+z*sn, y, -x*sn+z*cs)
        faces = {
            'top': ([P(-hx, hy, -hz), P(hx, hy, -hz), P(hx, hy, hz), P(-hx, hy, hz)], D(0, 1, 0)),
            'bottom': ([P(-hx, -hy, -hz), P(hx, -hy, -hz), P(hx, -hy, hz), P(-hx, -hy, hz)], D(0, -1, 0)),
            'east': ([P(hx, -hy, -hz), P(hx, hy, -hz), P(hx, hy, hz), P(hx, -hy, hz)], D(1, 0, 0)),
            'west': ([P(-hx, -hy, -hz), P(-hx, hy, -hz), P(-hx, hy, hz), P(-hx, -hy, hz)], D(-1, 0, 0)),
            'south': ([P(-hx, -hy, hz), P(hx, -hy, hz), P(hx, hy, hz), P(-hx, hy, hz)], D(0, 0, 1)),
            'north': ([P(-hx, -hy, -hz), P(hx, -hy, -hz), P(hx, hy, -hz), P(-hx, hy, -hz)], D(0, 0, -1)),
        }
        for name, (pts, n) in faces.items():
            if name in skip:
                continue
            col = top if (name == 'top' and top is not None) else color
            pt = pats.get(name, pat) if pats else pat
            self.face(pts, col, pt, n, collide=collide, visible=visible)

    def bounds(self, lo, hi, color, pat=PLAIN, **kw):
        c = tuple((lo[i]+hi[i])/2 for i in range(3))
        s = tuple(abs(hi[i]-lo[i]) for i in range(3))
        self.box(c, s, color, pat, **kw)

    def collider(self, lo, hi):
        self.bounds(lo, hi, WHITE, visible=False, collide=True)

    def cylinder(self, base, r, h, color, pat=PLAIN, seg=12, r_top=None, collide=False, caps=True, smooth=True):
        r_top = r if r_top is None else r_top
        x, y, z = base
        ring0 = [(x+math.cos(a)*r, y, z+math.sin(a)*r) for a in (i*math.tau/seg for i in range(seg))]
        ring1 = [(x+math.cos(a)*r_top, y+h, z+math.sin(a)*r_top) for a in (i*math.tau/seg for i in range(seg))]
        for i in range(seg):
            j = (i+1) % seg
            mid = ((ring0[i][0]+ring0[j][0])/2-x, 0, (ring0[i][2]+ring0[j][2])/2-z)
            self.face([ring0[i], ring0[j], ring1[j], ring1[i]], color, pat, mid, smooth=smooth, collide=collide)
        if caps:
            if r_top > 0.001:
                self.face(ring1, color, pat, (0, 1, 0), collide=collide)
            self.face(ring0, color, pat, (0, -1, 0), collide=False)

    def tube(self, pts, r, color, pat=PLAIN, seg=8, collide=False, caps=True):
        """Sweep a circle along a polyline (pipes, arches, rails)."""
        rings = []
        for i, p in enumerate(pts):
            a = pts[max(0, i-1)]
            b = pts[min(len(pts)-1, i+1)]
            t = _norm(_sub(b, a))
            up = (0, 1, 0) if abs(t[1]) < .9 else (1, 0, 0)
            u = _norm(_cross(t, up))
            v = _norm(_cross(u, t))
            rings.append([(p[0]+(u[0]*math.cos(k)+v[0]*math.sin(k))*r,
                           p[1]+(u[1]*math.cos(k)+v[1]*math.sin(k))*r,
                           p[2]+(u[2]*math.cos(k)+v[2]*math.sin(k))*r)
                          for k in (j*math.tau/seg for j in range(seg))])
        for i in range(len(pts)-1):
            for j in range(seg):
                k = (j+1) % seg
                q = [rings[i][j], rings[i][k], rings[i+1][k], rings[i+1][j]]
                cen = pts[i]
                mid = tuple((q[0][m]+q[1][m])/2-cen[m] for m in range(3))
                self.face(q, color, pat, mid, smooth=True, collide=collide)
        if caps:
            self.face(rings[0], color, pat, _sub(pts[0], pts[1]))
            self.face(rings[-1], color, pat, _sub(pts[-1], pts[-2]))

    def sphere(self, c, r, color, pat=PLAIN, seg=10, rings=6, squash=1.0, smooth=True):
        pts = []
        for i in range(rings+1):
            phi = math.pi*i/rings
            pts.append([(c[0]+r*math.sin(phi)*math.cos(t), c[1]+r*squash*math.cos(phi), c[2]+r*math.sin(phi)*math.sin(t))
                        for t in (j*math.tau/seg for j in range(seg))])
        for i in range(rings):
            for j in range(seg):
                k = (j+1) % seg
                q = [pts[i][j], pts[i][k], pts[i+1][k], pts[i+1][j]]
                mid = tuple(sum(p[m] for p in q)/4-c[m] for m in range(3))
                if i == 0:
                    self.face([q[0], q[2], q[3]], color, pat, mid, smooth)
                elif i == rings-1:
                    self.face([q[0], q[1], q[2]], color, pat, mid, smooth)
                else:
                    self.face(q, color, pat, mid, smooth)

    def arch_points(self, center, span, rise, along, steps=12, y0=None):
        """Semi-ellipse points in the vertical plane that contains ``along`` ('x' or 'z')."""
        cx, cy, cz = center
        out = []
        for i in range(steps+1):
            a = math.pi*i/steps
            d = -math.cos(a)*span/2
            y = cy+math.sin(a)*rise
            out.append((cx+d, y, cz) if along == 'x' else (cx, y, cz+d))
        return out

    def arch_rib(self, center, span, rise, r, color, along='x', steps=16, pat=PLAIN, seg=8, collide=False):
        self.tube(self.arch_points(center, span, rise, along, steps), r, color, pat, seg, collide=collide)

    def arch_wall(self, center, width, height, thick, open_w, open_h, along, color, pat=BRICK,
                  collide=True, steps=10, intrados=None):
        """Wall pierced by a round-top opening. ``along`` = axis the wall runs on.

        center = (x, ybase, z). The opening is centred, from ybase up to open_h.
        """
        cx, y0, cz = center
        spring = y0+open_h-open_w/2
        half = thick/2

        def P(d, y, n):
            return (cx+d, y, cz+n) if along == 'x' else (cx+n, y, cz+d)
        normal = (0, 0, 1) if along == 'x' else (1, 0, 0)
        neg = (0, 0, -1) if along == 'x' else (-1, 0, 0)
        # Piers on both sides of the opening.
        for sgn in (-1, 1):
            a, b = sgn*open_w/2, sgn*width/2
            lo, hi = min(a, b), max(a, b)
            for n, nn in ((half, normal), (-half, neg)):
                self.face([P(lo, y0, n), P(hi, y0, n), P(hi, y0+height, n), P(lo, y0+height, n)], color, pat, nn, collide=collide)
            end = b
            self.face([P(end, y0, -half), P(end, y0, half), P(end, y0+height, half), P(end, y0+height, -half)], color, pat,
                      (sgn, 0, 0) if along == 'x' else (0, 0, sgn), collide=collide)
            # inner jamb, below the springing line
            self.face([P(a, y0, -half), P(a, y0, half), P(a, spring, half), P(a, spring, -half)], intrados or color, pat,
                      (-sgn, 0, 0) if along == 'x' else (0, 0, -sgn), collide=collide)
        # Spandrels above the round top.
        pts = []
        for i in range(steps+1):
            ang = math.pi*i/steps
            pts.append((-math.cos(ang)*open_w/2, spring+math.sin(ang)*open_w/2))
        for i in range(steps):
            (d0, h0), (d1, h1) = pts[i], pts[i+1]
            for n, nn in ((half, normal), (-half, neg)):
                self.face([P(d0, h0, n), P(d1, h1, n), P(d1, y0+height, n), P(d0, y0+height, n)], color, pat, nn, collide=collide)
            mid = ((d0+d1)/2, (h0+h1)/2)
            inward = (0, -1, 0)
            self.face([P(d0, h0, -half), P(d1, h1, -half), P(d1, h1, half), P(d0, h0, half)], intrados or color, pat,
                      (-mid[0], -(mid[1]-spring), 0) if along == 'x' else (0, -(mid[1]-spring), -mid[0]), collide=collide)
        self.face([P(-width/2, y0+height, -half), P(width/2, y0+height, -half), P(width/2, y0+height, half), P(-width/2, y0+height, half)],
                  color, pat, (0, 1, 0), collide=collide)

    def ramp(self, p0, p1, width, color, pat=PLAIN, thick=.4, collide=True, visible=True, sides=True):
        """Sloped slab from low point p0 to high point p1 (horizontal run along x or z)."""
        dx, dz = p1[0]-p0[0], p1[2]-p0[2]
        L = math.hypot(dx, dz) or 1
        ux, uz = dx/L, dz/L
        px, pz = -uz*width/2, ux*width/2
        a = (p0[0]+px, p0[1], p0[2]+pz)
        b = (p0[0]-px, p0[1], p0[2]-pz)
        c = (p1[0]-px, p1[1], p1[2]-pz)
        d = (p1[0]+px, p1[1], p1[2]+pz)
        self.face([a, b, c, d], color, pat, (0, 1, 0), collide=collide, visible=visible)
        if sides:
            low = min(p0[1], p1[1])-thick
            for e, f in ((a, d), (b, c)):
                self.face([(e[0], low, e[2]), e, f, (f[0], low, f[2])], color, pat,
                          ((e[0]-p0[0])+(f[0]-p1[0]), 0, (e[2]-p0[2])+(f[2]-p1[2])), collide=collide, visible=visible)
            self.face([(c[0], low, c[2]), c, d, (d[0], low, d[2])], color, pat, (ux, 0, uz), collide=collide, visible=visible)

    def stairs(self, p0, p1, width, color, pat=PLAIN, step=.22, side_color=None, collide=True):
        """Visible steps plus an invisible collision ramp (the controller has no step-up)."""
        rise = p1[1]-p0[1]
        n = max(2, int(abs(rise)/step+.5))
        dx, dz = p1[0]-p0[0], p1[2]-p0[2]
        L = math.hypot(dx, dz)
        ry = math.atan2(dx, dz)
        for i in range(n):
            t0 = i/n
            cx, cz = p0[0]+dx*(t0+.5/n), p0[2]+dz*(t0+.5/n)
            top = p0[1]+rise*(i+1)/n
            h = top-(p0[1]-.3)
            self.box((cx, top-h/2, cz), (width, h, L/n+.02), side_color or color, pat, collide=False, ry=ry, top=color)
        if collide:
            self.ramp(p0, p1, width, color, visible=False)

    def railing(self, p0, p1, color=IRON, h=1.05, gap=1.1, collide=True, ornate=False):
        dx, dz = p1[0]-p0[0], p1[2]-p0[2]
        L = math.hypot(dx, dz) or 1
        n = max(1, int(L/gap))
        dy = p1[1]-p0[1]
        self.tube([(p0[0], p0[1]+h, p0[2]), (p1[0], p1[1]+h, p1[2])], .045, color, seg=6, caps=False)
        self.tube([(p0[0], p0[1]+.12, p0[2]), (p1[0], p1[1]+.12, p1[2])], .03, color, seg=5, caps=False)
        for i in range(n+1):
            t = i/n
            x, y, z = p0[0]+dx*t, p0[1]+dy*t, p0[2]+dz*t
            self.box((x, y+h/2, z), (.07, h, .07), color, collide=False)
            if ornate and i < n:
                t2 = (i+.5)/n
                xm, ym, zm = p0[0]+dx*t2, p0[1]+dy*t2, p0[2]+dz*t2
                pts = []
                for k in range(9):
                    a = k*math.tau/8
                    pts.append((xm+math.cos(a)*dx/L*.3, ym+.6+math.sin(a)*.32, zm+math.cos(a)*dz/L*.3))
                self.tube(pts, .022, color, seg=4, caps=False)
        if collide:
            ry = math.atan2(dx, dz)
            self.box(((p0[0]+p1[0])/2, (p0[1]+p1[1])/2+h/2, (p0[2]+p1[2])/2), (.15, h+abs(dy), L), color,
                     visible=False, ry=ry)

    # -- props --------------------------------------------------------------
    def tree(self, x, y, z, s=1.0):
        rng = self.rng
        self.cylinder((x, y, z), .22*s, 2.6*s, TRUNK, seg=7, r_top=.14*s)
        for _ in range(6):
            ox, oy, oz = rng.uniform(-1, 1)*s, rng.uniform(2.4, 3.8)*s, rng.uniform(-1, 1)*s
            self.sphere((x+ox, y+oy, z+oz), rng.uniform(.9, 1.3)*s, rng.choice((LEAF_C, LEAF_D)), LEAF, seg=7, rings=5)
        self.collider((x-.3*s, y, z-.3*s), (x+.3*s, y+2.4*s, z+.3*s))

    def planter(self, x, y, z, w=1.6, d=.8):
        self.box((x, y+.35, z), (w, .7, d), TERRACOTTA, PLASTER)
        for i in range(3):
            self.sphere((x+(i-1)*w/3, y+.9, z), .38, LEAF_C if i % 2 else LEAF_D, LEAF, seg=7, rings=4)

    def lamp(self, x, y, z, h=4.6):
        self.cylinder((x, y, z), .16, .5, IRON, seg=8)
        self.cylinder((x, y+.5, z), .07, h-.5, IRON, seg=6, caps=False)
        self.box((x, y+h+.25, z), (.42, .5, .42), YELLOW, GLOW, collide=False)
        self.box((x, y+h+.58, z), (.55, .12, .55), IRON, collide=False)
        self.collider((x-.15, y, z-.15), (x+.15, y+h, z+.15))

    def bollard(self, x, y, z):
        self.cylinder((x, y, z), .2, .7, WHITE, seg=8, caps=False)
        self.sphere((x, y+.7, z), .2, WHITE, seg=8, rings=4)
        self.collider((x-.2, y, z-.2), (x+.2, y+.85, z+.2))

    def crate(self, x, y, z, s=1.0, ry=0.0, color=WOOD):
        self.box((x, y+s/2, z), (s, s, s), color, PLANK, ry=ry)

    def oxygen_box(self, x, y, z, ry=0.0):
        self.box((x, y+.3, z), (.8, .6, .6), WHITE, ry=ry)
        self.box((x, y+.3, z), (.82, .14, .62), SKY_BLUE, collide=False, ry=ry)

    def barrier(self, x, y, z, ry=0.0, w=2.0):
        self.box((x, y+.75, z), (w, .3, .06), YELLOW, HAZARD, collide=False, ry=ry)
        for s in (-1, 1):
            ox, oz = math.cos(ry)*s*w*.42, -math.sin(ry)*s*w*.42
            self.box((x+ox, y+.45, z+oz), (.08, .9, .5), IRON, collide=False, ry=ry)
        self.box((x, y+.5, z), (w, 1.0, .25), YELLOW, visible=False, ry=ry)

    def cone(self, x, y, z):
        self.cylinder((x, y, z), .26, .75, TEAL, seg=8, r_top=.03, collide=False)
        self.box((x, y+.03, z), (.6, .06, .6), TEAL, collide=False)

    def bench(self, x, y, z, ry=0.0):
        self.box((x, y+.45, z), (1.8, .1, .5), WOOD, PLANK, collide=False, ry=ry)
        self.box((x, y+.22, z), (1.6, .44, .3), IRON, ry=ry)

    def cart(self, x, y, z, ry=0.0):
        self.box((x, y+.35, z), (.9, .08, .6), (150, 156, 166), collide=False, ry=ry)
        self.box((x, y+.62, z), (.7, .5, .5), WHITE, ry=ry)
        self.cylinder((x, y, z), .05, 1.1, IRON, seg=5, caps=False)

    def laundry(self, x0, x1, y, z):
        self.tube([(x0, y, z), (x1, y, z)], .02, IRON, seg=4, caps=False)
        rng = self.rng
        x = x0+.3
        while x < x1-.4:
            w = rng.uniform(.3, .6)
            col = rng.choice((WHITE, SKY_BLUE, SALMON, YELLOW, MINT, (240, 240, 250)))
            self.face([(x, y, z), (x+w, y, z), (x+w, y-rng.uniform(.4, .8), z), (x, y-.6, z)], col, PLAIN, (0, 0, 1))
            self.face([(x, y, z), (x+w, y, z), (x+w, y-rng.uniform(.4, .8), z), (x, y-.6, z)], col, PLAIN, (0, 0, -1))
            x += w+rng.uniform(.1, .4)

    # -- arquitetura --------------------------------------------------------
    def facade(self, axis_lo, axis_hi, fixed, y0, height, face_dir, along, floor_h=3.2, style='balcony',
               wall=CREAM, accent=WOOD, ground_floor=None, start_floor=1, laundry=True, crowd=False):
        """Decorate one face of a block: windows, balconies, cornices.

        along='x' -> facade spans x in [axis_lo, axis_hi] at z=fixed; face_dir = +1 (south) / -1 (north).
        along='z' -> facade spans z at x=fixed; face_dir = +1 (east) / -1 (west).
        """
        rng = self.rng
        floors = int((height-.6)/floor_h)
        span = axis_hi-axis_lo
        bays = max(1, int(span/3.6))
        bay = span/bays

        def P(a, y, out):
            return (a, y, fixed+face_dir*out) if along == 'x' else (fixed+face_dir*out, y, a)
        nrm = (0, 0, face_dir) if along == 'x' else (face_dir, 0, 0)
        for f in range(start_floor, floors):
            y = y0+f*floor_h
            # cornice band per floor
            lo, hi = P(axis_lo, y-.08, 0), P(axis_hi, y+.08, .12)
            self.bounds((min(lo[0], hi[0]), lo[1], min(lo[2], hi[2])), (max(lo[0], hi[0]), hi[1], max(lo[2], hi[2])),
                        CREAM2, collide=False)
            for b in range(bays):
                a = axis_lo+bay*(b+.5)
                # window
                w, h = bay*.42, floor_h*.5
                wy = y+floor_h*.3
                pts = [P(a-w/2, wy, .06), P(a+w/2, wy, .06), P(a+w/2, wy+h, .06), P(a-w/2, wy+h, .06)]
                self.face(pts, GLASS_C if rng.random() < .8 else (250, 226, 170), WINDOW, nrm)
                if style == 'balcony' and (b+f) % 1 == 0:
                    bw, depth = bay*.86, 1.15
                    c = P(a, y+.08, depth/2)
                    size = (bw, .16, depth) if along == 'x' else (depth, .16, bw)
                    self.box(c, size, accent, PLANK, collide=False)
                    # wooden parapet (the ochre balconies of the artery)
                    c2 = P(a, y+.6, depth-.05)
                    size2 = (bw, .9, .1) if along == 'x' else (.1, .9, bw)
                    self.box(c2, size2, accent, PLANK, collide=False)
                    for sgn in (-1, 1):
                        c3 = P(a+sgn*bw/2, y+.6, depth/2)
                        size3 = (.1, .9, depth) if along == 'x' else (depth, .9, .1)
                        self.box(c3, size3, accent, PLANK, collide=False)
                    if crowd and f >= 1 and rng.random() < .3:
                        spot = P(a+rng.uniform(-bw*.3, bw*.3), y+.16, depth*.45)
                        yaw = (math.pi if face_dir > 0 else 0.0) if along == 'x' else (math.pi/2 if face_dir > 0 else -math.pi/2)
                        self.spots.append((spot[0], spot[1], spot[2], yaw))
                    if laundry and rng.random() < .18 and along == 'x':
                        self.laundry(a-bw/2+.35, a+bw/2-.35, y+2.1, fixed+face_dir*(depth-.35))
                    if rng.random() < .12:
                        cc = P(a+bw*.3, y+.5, .5)
                        self.sphere(cc, .32, LEAF_C, LEAF, seg=6, rings=4)
                elif style == 'sill':
                    c = P(a, wy-.06, .12)
                    self.box(c, (w+.3, .12, .24) if along == 'x' else (.24, .12, w+.3), WHITE, collide=False)
                    if rng.random() < .25:
                        self.box(P(a, wy+.15, .3), (w, .3, .3) if along == 'x' else (.3, .3, w), TERRACOTTA, collide=False)
                        self.sphere(P(a, wy+.42, .32), .25, LEAF_C, LEAF, seg=6, rings=4)
                elif style == 'shutter':
                    for sgn in (-1, 1):
                        c = P(a+sgn*(w/2+.18), wy+h/2, .06)
                        self.box(c, (.32, h, .06) if along == 'x' else (.06, h, .32), TEAL, PLANK, collide=False)

    def block(self, x0, x1, z0, z1, h, wall=CREAM, pat=PLASTER, roof=ROOF, roof_color=TERRACOTTA, y0=0.0,
              faces=('north', 'south', 'east', 'west'), style='balcony', accent=WOOD, parapet=True, start_floor=1,
              crowd=False, face_start=None):
        self.bounds((x0, y0, z0), (x1, y0+h, z1), wall, pat, top=roof_color, pats={'top': roof})
        if parapet:
            for (a, b) in (((x0, z0), (x1, z0+.3)), ((x0, z1-.3), (x1, z1)), ((x0, z0), (x0+.3, z1)), ((x1-.3, z0), (x1, z1))):
                self.bounds((a[0], y0+h, a[1]), (b[0], y0+h+.8, b[1]), CREAM2, PLASTER, collide=False)
        for f in faces:
            if f == 'south':
                self.facade(x0, x1, z1, y0, h, 1, 'x', style=style, wall=wall, accent=accent, start_floor=(face_start or {}).get('south', start_floor), crowd=crowd)
            elif f == 'north':
                self.facade(x0, x1, z0, y0, h, -1, 'x', style=style, wall=wall, accent=accent, start_floor=(face_start or {}).get('north', start_floor), crowd=crowd)
            elif f == 'east':
                self.facade(z0, z1, x1, y0, h, 1, 'z', style=style, wall=wall, accent=accent, start_floor=(face_start or {}).get('east', start_floor), crowd=crowd)
            elif f == 'west':
                self.facade(z0, z1, x0, y0, h, -1, 'z', style=style, wall=wall, accent=accent, start_floor=(face_start or {}).get('west', start_floor), crowd=crowd)
        # rooftop clutter
        rng = self.rng
        for _ in range(int((x1-x0)*(z1-z0)/90)):
            x, z = rng.uniform(x0+1.5, x1-1.5), rng.uniform(z0+1.5, z1-1.5)
            k = rng.random()
            if k < .4:
                self.box((x, y0+h+.5, z), (1.2, 1, .8), (200, 204, 206), METAL, collide=False)
            elif k < .7:
                self.cylinder((x, y0+h, z), .8, 1.8, (214, 206, 190), METAL, seg=10, collide=False)
            else:
                self.box((x, y0+h+1.2, z), (2.4, 2.4, 2.4), CREAM2, PLASTER, collide=False)

    def door(self, x, y, z, normal, w=2.2, h=2.8, color=TERRACOTTA, frame=CREAM2):
        """Painted doorway on a wall with an awning (visual only)."""
        nx, nz = normal
        if nz:
            self.box((x, y+h/2, z+nz*.04), (w, h, .08), color, PLANK, collide=False)
            self.box((x, y+h+.15, z+nz*.06), (w+.5, .3, .12), frame, collide=False)
            self.box((x, y+h+.55, z+nz*.7), (w+1.2, .1, 1.4), RED_ARCH, collide=False)
        else:
            self.box((x+nx*.04, y+h/2, z), (.08, h, w), color, PLANK, collide=False)
            self.box((x+nx*.06, y+h+.15, z), (.12, .3, w+.5), frame, collide=False)
            self.box((x+nx*.7, y+h+.55, z), (1.4, .1, w+1.2), RED_ARCH, collide=False)
