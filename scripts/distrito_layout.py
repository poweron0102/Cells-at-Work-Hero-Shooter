"""Layout do Bairro Arterial (PLANO_MAPA.md), escrito em coordenadas do jogo.

x = leste, y = cima, z = sul. Base das celulas ao sul (+z), ferida ao norte (-z).

Zonas (sul -> norte):
  z  76..92  Estacao de servico das celulas, duas saidas protegidas
  z  36..72  Avenida arterial (x -10..10) entre blocos altos com sacadas
  z  28..36  Rua transversal sul (bifurcacao S)
  z   8..28  Praca da ponte: chafariz-coracao, torre trelicada (reconhecimento)
  z  -6..6   Canal raso; pontes oeste (escadas), central (escolta) e leste
  z -26..-18 Rua Norte (O a oeste, L a leste)
  z -52..-44 Rua da Obra (N no centro)
  z -94..-52 Obra da ferida: cratera/entrada bacteriana, andaimes, tunel
Edificios de oxigenio: A (sudoeste), B (leste), C (noroeste).
"""
import math
from distrito_geo import *  # noqa: F401,F403

X0, X1, Z0, Z1 = -62, 62, -94, 92
CANAL = (-6, 6)
CANAL_FLOOR = -2.4
WATER_Y = -1.95
PIT = (-16, 16, -88, -68)
PIT_FLOOR = -2.5

# Rampas do canal: (x alto, x baixo, margem) — margem +1 = sul, -1 = norte.
CANAL_RAMPS = [(-55, -47, 1), (-16, -8, 1), (18, 26, 1), (-26, -18, -1), (16, 8, -1), (52, 44, -1)]
BRIDGES = {'oeste': (-40, 4, 2.6), 'central': (0, 10, 1.0), 'leste': (40, 6, .9)}


def build(g, only=None):
    sections = [ground, canal, bridges, base, avenue, cross_and_plaza, west_side, east_side,
                north_center, north_west, north_east, wound_site, boundary, perimeter, skyline]
    for fn in sections:
        if only and fn.__name__ not in only:
            continue
        fn(g)
    g.flush_overlays()
    return markers(g)


# ---------------------------------------------------------------------------
def ground(g):
    g.zone('chao')
    side = {'north': ASHLAR, 'south': ASHLAR, 'east': ASHLAR, 'west': ASHLAR, 'top': FLAGSTONE}
    # Southern ground, bank to the station.
    g.bounds((X0, -3, 6), (X1, 0, Z1), STONE, FLAGSTONE, top=PAVING, pats=side)
    # Northern ground with a hole for the rupture pit.
    px0, px1, pz0, pz1 = PIT
    for lo, hi in (((X0, -3, pz1), (X1, 0, -6)), ((X0, -3, Z0), (X1, 0, pz0)),
                   ((X0, -3, pz0), (px0, 0, pz1)), ((px1, -3, pz0), (X1, 0, pz1))):
        g.bounds(lo, hi, STONE, FLAGSTONE, top=PAVING2, pats=side)


def canal(g):
    g.zone('canal')
    g.bounds((X0, CANAL_FLOOR-1, CANAL[0]), (X1, CANAL_FLOOR, CANAL[1]), STONE_D, ASHLAR, top=(184, 176, 156))
    # Water: shallow and walkable (players wade at knee height).
    g.face([(X0-60, WATER_Y, CANAL[0]), (X1+60, WATER_Y, CANAL[0]), (X1+60, WATER_Y, CANAL[1]), (X0-60, WATER_Y, CANAL[1])],
           WATER_C, WATER, (0, 1, 0))
    for xh, xl, bank in CANAL_RAMPS:
        z = CANAL[1]-1.5 if bank > 0 else CANAL[0]+1.5
        g.ramp((xl, CANAL_FLOOR, z), (xh, 0, z), 3, STONE, ASHLAR, thick=.1)
        # landing at the top so the ramp always connects to the bank
        side = 1 if xh > xl else -1
        g.bounds((min(xh, xh+side*3), -1.2, z-1.5), (max(xh, xh+side*3), 0, z+1.5), STONE, ASHLAR, top=PAVING, pats={'top': FLAGSTONE})
        # low wall on the open side of the ramp
        zz = z-1.5*bank
        xe = xh-.3*side
        g.ramp((xl, CANAL_FLOOR+.5, zz), (xe, .5-.3*(.5+2.4)/abs(xh-xl), zz), .25, STONE_D, ASHLAR, thick=.6, collide=False)
    # Coping stones and bollards along the banks, leaving gaps at ramps and bridges.
    blocked = [(b[0]-b[1]/2-3, b[0]+b[1]/2+3) for b in BRIDGES.values()]
    for z, bank in ((CANAL[1], 1), (CANAL[0], -1)):
        g.bounds((X0, 0, z if bank > 0 else z-.5), (X1, .12, z+.5 if bank > 0 else z), (238, 230, 212), collide=False)
        x = X0+3
        while x < X1-2:
            ok = all(not (a <= x <= b) for a, b in blocked)
            ok = ok and all(not (min(xh, xl)-2 <= x <= max(xh, xl)+2) or b2 != bank for xh, xl, b2 in CANAL_RAMPS if abs(xh-x) < 3)
            if ok:
                g.bollard(x, 0, z+.35*bank)
            x += 3.2
    # Tunnel mouths where the canal leaves the district.
    for x, n in ((X0, -1), (X1, 1)):
        g.arch_wall((x, CANAL_FLOOR, 0), 16, 9, 1.2, 9, 6, 'z', BRICK_C, BRICK, intrados=BRICK_D)
        for i in range(10):
            zz = -4.2+i*.93
            g.box((x, CANAL_FLOOR+2.4, zz), (.1, 4.8, .08), IRON, collide=False)
        g.collider((x-.3, CANAL_FLOOR, -6), (x+.3, 6, 6))
        # The canal keeps going into a dark brick culvert beyond the grate.
        out = x+n*14
        lo, hi = min(x, out), max(x, out)
        g.bounds((lo, CANAL_FLOOR-1, -4.5), (hi, CANAL_FLOOR, 4.5), STONE_D, ASHLAR, collide=False)
        for zz in (-4.5, 4.5):
            g.bounds((lo, CANAL_FLOOR, zz-.4 if zz < 0 else zz), (hi, CANAL_FLOOR+3.6, zz if zz < 0 else zz+.4),
                     BRICK_D, BRICK, collide=False)
        steps = 10
        for i in range(steps):
            a0, a1 = math.pi*i/steps, math.pi*(i+1)/steps
            p0 = (-math.cos(a0)*4.5, CANAL_FLOOR+3.6+math.sin(a0)*2.4)
            p1 = (-math.cos(a1)*4.5, CANAL_FLOOR+3.6+math.sin(a1)*2.4)
            g.face([(lo, p0[1], p0[0]), (hi, p0[1], p0[0]), (hi, p1[1], p1[0]), (lo, p1[1], p1[0])], BRICK_D, BRICK,
                   (0, -1, -(p0[0]+p1[0])/2), smooth=True)
        g.bounds((min(out, out-n*.5), CANAL_FLOOR, -4.5), (max(out, out-n*.5), CANAL_FLOOR+6.2, 4.5), DARK, collide=False)


def bridges(g):
    g.zone('pontes')
    for name, (x, w, deck) in BRIDGES.items():
        z0, z1 = CANAL
        body = BRICK_C if name != 'leste' else STONE
        pat = BRICK if name != 'leste' else ASHLAR
        height = deck-CANAL_FLOOR-(.02 if name != 'oeste' else 0)
        g.arch_wall((x, CANAL_FLOOR, 0), z1-z0, height, w, 6, 3, 'z', body, pat, intrados=BRICK_D if pat == BRICK else STONE_D)
        rail_y = deck
        if name == 'oeste':
            # Footbridge with long stairs on both banks (reference: brick bridge with iron rail).
            g.stairs((x, 0, 12.5), (x, deck, z1), w, BRICK_C, BRICK, side_color=BRICK_D)
            g.stairs((x, 0, -12.5), (x, deck, z0), w, BRICK_C, BRICK, side_color=BRICK_D)
            for s in (-1, 1):
                xx = x+s*(w/2-.08)
                g.railing((xx, 0, 12.5), (xx, deck, z1), ornate=True)
                g.railing((xx, deck, z1), (xx, deck, z0), ornate=True)
                g.railing((xx, deck, z0), (xx, 0, -12.5), ornate=True)
        else:
            run = 3.5 if name == 'central' else 3
            g.ramp((x, 0, z1+run), (x, deck, z1), w, PAVING, FLAGSTONE, thick=deck)
            g.ramp((x, 0, z0-run), (x, deck, z0), w, PAVING, FLAGSTONE, thick=deck)
            g.bounds((x-w/2, deck-.02, z0), (x+w/2, deck, z1), PAVING, FLAGSTONE, collide=False)
            for s in (-1, 1):
                xx = x+s*(w/2-.1)
                if name == 'central':
                    g.railing((xx, 0, z1+run), (xx, deck, z1), ornate=True)
                    g.railing((xx, deck, z1), (xx, deck, z0), ornate=True)
                    g.railing((xx, deck, z0), (xx, 0, z0-run), ornate=True)
                else:
                    g.bounds((xx-.2, 0, z0-run), (xx+.2, deck+.9, z1+run), STONE, ASHLAR)
            if name == 'leste':
                # Blue steel arches over the deck (reference: blue pergola trusses).
                for zz in (-4.5, 0, 4.5):
                    g.arch_rib((x, deck+.9, zz), w-.4, 3.2, .16, BLUE_STEEL, 'x', 14, METAL)
                for s in (-1, 1):
                    g.tube([(x+s*(w/2-.2), deck+.9, -5.5), (x+s*(w/2-.2), deck+.9, 5.5)], .12, BLUE_STEEL, METAL)
                g.tube([(x, deck+4.1, -5.5), (x, deck+4.1, 5.5)], .14, BLUE_STEEL, METAL)
        if name == 'central':
            # Lamps at the four corners of the escort bridge.
            for sx in (-1, 1):
                for sz in (-1, 1):
                    g.lamp(x+sx*(w/2-.4), deck if abs(sz*5.6) < 6 else 0, sz*5.6, 3.6)


def base(g):
    g.zone('base_celulas')
    x0, x1, z0, z1, h = -24, 24, 76, 92, 8
    doors = [(-16, -12), (12, 16)]
    # North wall with two doorways.
    xs = [x0]+[d for pair in doors for d in pair]+[x1]
    for i in range(0, len(xs), 2):
        g.bounds((xs[i], 0, z0), (xs[i+1], h, z0+1), CREAM, PLASTER)
    for a, b in doors:
        g.bounds((a, 3.4, z0), (b, h, z0+1), CREAM, PLASTER)
        g.box(((a+b)/2, 3.7, z0-.7), (b-a+1.2, .12, 1.6), RED_ARCH, collide=False)
    for x in (x0, x1-1):
        g.bounds((x, 0, z0), (x+1, h, z1), CREAM, PLASTER)
    g.bounds((x0, 0, z1-1), (x1, h, z1), CREAM, PLASTER)
    g.bounds((x0, h, z0), (x1, h+.6, z1), CREAM2, PLASTER, top=TERRACOTTA, pats={'top': ROOF})
    # Station sign band: red with white panel.
    g.box((0, 6.2, z0-.15), (20, 1.6, .3), RED_ARCH, collide=False)
    g.box((0, 6.2, z0-.36), (12, 1.0, .12), WHITE, collide=False)
    g.box((0, 6.2, z0-.47), (1.2, .8, .1), RED_ARCH, collide=False)
    g.box((0, 6.2, z0-.56), (.26, .62, .08), WHITE, collide=False)
    g.box((0, 6.2, z0-.56), (.62, .26, .08), WHITE, collide=False)
    # Interior: tiled floor, lockers, benches, pillars.
    g.overlay(x0+1, z0+1, x1-1, z1-1, (230, 236, 238), TILE, 6)
    for x in range(-20, 21, 4):
        g.box((x, 1.1, z1-1.5), (1.6, 2.2, .8), (196, 210, 214), METAL)
    for x in (-8, 8):
        g.bench(x, 0, 82)
        g.box((x, 4, 80), (.8, 8, .8), CREAM2, PLASTER)
    # Protective baffles in front of both exits (no straight shots into the station).
    for a, b in doors:
        cx = (a+b)/2
        g.bounds((cx-4, 0, 71.6), (cx+4, 3.0, 72.4), CREAM2, PLASTER)
        g.planter(cx, 3.0, 72, 7.6, .7)
    # Out-of-bounds blocks beside the station.
    g.block(-62, -24, 72, 92, 22, faces=('north',), crowd=True)
    g.block(24, 62, 72, 92, 22, faces=('north',), crowd=True)


def avenue(g):
    g.zone('avenida')
    z0, z1 = 36, 72
    # Wooden plank floor of the artery.
    g.overlay(-10, z0, 10, z1+4, OCHRE, PLANK, 3)
    # West block with a pass-through arcade (alley z 51..56), east block (alley z 42..47).
    for (x0, x1, alley, face) in ((-36, -10, (51, 56), 'east'), (10, 36, (42, 47), 'west')):
        faces = (face, 'west' if face == 'east' else 'east')
        # Avenue-facing balconies start above the low walkway (floor 2).
        g.block(x0, x1, z0, alley[0], 26, faces=faces+('north',), start_floor=1, crowd=True, face_start={face: 2})
        g.block(x0, x1, alley[1], 70, 26, faces=faces+('south',), start_floor=1, crowd=True, face_start={face: 2})
        g.bounds((x0, 4.5, alley[0]), (x1, 26, alley[1]), CREAM, PLASTER)
        g.bounds((x0, 4.3, alley[0]), (x1, 4.5, alley[1]), WOOD, PLANK, collide=False)
        g.overlay(x0, alley[0], x1, alley[1], TILE_C, TILE, 5)
        for x in range(x0+3, x1-1, 5):
            g.lamp(x, 0, alley[0]+.6, 3.4)
        # arcade ground floor along the avenue: shop fronts
        fx = x1 if face == 'east' else x0
        n = 1 if face == 'east' else -1
        for z in range(z0+4, 60, 6):
            if alley[0]-2.5 < z < alley[1]+2.5:
                continue
            # Shop fronts stay inside the block; the walkway above works as their awning.
            g.box((fx+n*.06, 1.6, z), (.12, 2.6, 4.0), (250, 214, 160), WINDOW, collide=False)
            g.box((fx+n*.35, 2.95, z), (.7, .12, 4.2), g.rng.choice((RED_ARCH, TEAL, SKY_BLUE, YELLOW)), collide=False)
    # Low walkways along both facades (y 4.2), reachable by stairs at both ends.
    for side in (-1, 1):
        xin, xout = side*10, side*7.6
        lo, hi = (min(xin, xout), 4.0, 38), (max(xin, xout), 4.3, 62)
        g.bounds(lo, hi, WOOD, PLANK)
        g.railing((xout, 4.3, 38), (xout, 4.3, 62), WOOD)
        g.railing((xout, 4.3, 38), (xin, 4.3, 38), WOOD)
        for z in range(40, 62, 6):
            g.box((side*8, 2.0, z), (.25, 4.0, .25), IRON)
        xm = side*8.8
        g.stairs((xm, 0, 71), (xm, 4.3, 62), 2.4, WOOD, PLANK, side_color=(190, 140, 76))
        g.railing((side*7.55, 0, 71), (side*7.55, 4.3, 62), WOOD)
    # Red arch ribs of the covered artery, plus the hanging "Artery" lantern.
    for z in range(38, 72, 4):
        g.arch_rib((0, 26, z), 20, 7, .28, RED_ARCH, 'x', 18, METAL)
    for x in (-6, 0, 6):
        yy = 26+7*math.sqrt(max(0, 1-(x/10)**2))-.05
        g.tube([(x, yy, 38), (x, yy, 70)], .12, RED_ARCH, METAL, seg=6)
    for z in range(38, 72, 4):
        for s in (-1, 1):
            g.box((s*10.2, 26.3, z), (.9, .6, .9), (180, 70, 66), METAL, collide=False)
    g.tube([(0, 33, 52), (0, 21, 52)], .05, IRON, seg=4)
    g.cylinder((0, 15, 52), 1.6, 6, RED_ARCH, PLASTER, seg=16)
    g.cylinder((0, 14.6, 52), 1.7, .4, DARK, seg=16)
    g.cylinder((0, 21, 52), 1.7, .4, DARK, seg=16)
    g.cylinder((0, 16.2, 52), 1.62, 1.0, WHITE, seg=16, caps=False)
    # Street life: carts, oxygen boxes, benches, lamps.
    rng = g.rng
    for z in range(48, 70, 7):
        for s in (-1, 1):
            g.lamp(s*6.5, 0, z, 3.6)
    for i in range(10):
        x, z = rng.uniform(-5.6, 5.6), rng.uniform(47, 66)
        if abs(x) < 2.5:
            continue
        k = rng.random()
        if k < .4:
            g.oxygen_box(x, 0, z, rng.uniform(0, 3))
        elif k < .7:
            g.cart(x, 0, z, rng.uniform(0, 3))
        else:
            g.crate(x, 0, z, .9, rng.uniform(0, 1))
    # RBC oxygen depot: an open stall between the escort lane and the walkway posts.
    for zz in (39.2, 44.8):
        for xx in (3.2, 6.8):
            g.box((xx, 1.4, zz), (.14, 2.8, .14), IRON)
    g.box((5, 2.9, 42), (4.4, .14, 6.4), RED_ARCH, collide=False)
    g.box((5, 3.05, 42), (4.0, .16, 6.0), WHITE, collide=False)
    for z in (39.8, 40.9, 43.1, 44.2):
        g.oxygen_box(6.2, 0, z)
        g.oxygen_box(6.2, .6, z)


def cross_and_plaza(g):
    g.zone('praca')
    # Tiled plaza floor with pastel tiles (reference: the square with painted arrows).
    g.overlay(-28, 8, 28, 28, TILE_C, TILE, 2)
    g.overlay(-44, 28, 44, 36, PAVING, FLAGSTONE, 2)
    for (x, z, ry) in ((-14, 31, 0), (16, 33, math.pi), (8, 12, math.pi/2)):
        g.box((x, .045, z), (4, .02, .6), WHITE, collide=False, ry=ry, skip=('bottom',))
        g.box((x+math.sin(ry+math.pi/2)*2, .05, z+math.cos(ry+math.pi/2)*2), (1.4, .02, 1.4), WHITE, collide=False,
              ry=ry+math.pi/4, skip=('bottom',))
    # Heart-pump fountain monument (blocks the base-to-base sightline).
    g.cylinder((0, 0, 20), 4.2, .7, STONE, ASHLAR, seg=24, collide=True)
    g.cylinder((0, .72, 20), 3.8, .03, WATER_C, WATER, seg=24)
    g.cylinder((0, 0, 20), 1.4, 3.2, CREAM2, PLASTER, seg=16, collide=True)
    g.sphere((0, 4.6, 20), 1.9, RED_ARCH, PLASTER, seg=14, rings=9, squash=1.05)
    for a in range(4):
        ang = a*math.tau/4+.4
        g.tube([(math.cos(ang)*1.2, 5.5, 20+math.sin(ang)*1.2), (math.cos(ang)*2.2, 7.4, 20+math.sin(ang)*2.2),
                (math.cos(ang)*3.4, 7.8, 20+math.sin(ang)*3.4)], .32, SALMON if a % 2 else SKY_BLUE, PLASTER, seg=8)
    # Lattice tower (landmark + reconnaissance post at its base).
    tx, tz = -15, 18
    legs = [(-4, -4), (4, -4), (-4, 4), (4, 4)]
    top = 24
    for lx, lz in legs:
        g.tube([(tx+lx, 0, tz+lz), (tx+lx*.35, top, tz+lz*.35)], .38, SALMON, METAL, seg=8)
        g.cylinder((tx+lx, 0, tz+lz), .7, .5, SALMON, METAL, seg=10, collide=True)
        g.collider((tx+lx-.4, 0, tz+lz-.4), (tx+lx+.4, 6, tz+lz+.4))
    for y in (5, 10, 15, 20):
        f = 1-y/top*.65
        corners = [(tx+lx*f, y, tz+lz*f) for lx, lz in ((-4, -4), (4, -4), (4, 4), (-4, 4), (-4, -4))]
        g.tube(corners, .2, SALMON, METAL, seg=6, caps=False)
    g.bounds((tx-2, top-.2, tz-2), (tx+2, top+.3, tz+2), SALMON, METAL, collide=False)
    g.tube([(tx, top, tz), (tx, top+6, tz)], .1, IRON, seg=6)
    g.sphere((tx, top+6.6, tz), .8, WHITE, seg=12, rings=8)
    g.sphere((tx, top+6.6, tz+.5), .45, DARK, seg=10, rings=6)
    # Recon console: two approaches, low cover around.
    g.bounds((tx-1, 0, tz-.6), (tx+1, 1.2, tz+.6), (196, 210, 214), METAL, top=SKY_BLUE)
    g.box((tx, 1.6, tz-.3), (1.6, .9, .1), (60, 90, 110), GLASS, collide=False)
    for s in (-1, 1):
        g.bounds((tx-3.5, 0, tz+s*3.4-.3), (tx+3.5, 1.0, tz+s*3.4+.3), (110, 70, 50), PLANK)
    # Blue pergola arches (east of the plaza).
    for z in range(10, 27, 4):
        g.arch_rib((16, 0, z), 7, 5.5, .22, BLUE_STEEL, 'x', 16, METAL)
        for s in (-1, 1):
            g.collider((16+s*3.5-.25, 0, z-.25), (16+s*3.5+.25, 3, z+.25))
    for s in (-1, 0, 1):
        yy = 5.5*math.sqrt(1-(s*2.5/3.5)**2)
        g.tube([(16+s*2.5, yy, 10), (16+s*2.5, yy, 26)], .16, BLUE_STEEL, METAL)
    # Wooden fences, benches, lamps, planters, trees.
    for (x0, z0, x1, z1) in ((-26, 25, -20, 25), (-26, 25, -26, 14), (22, 10, 27, 10)):
        g.railing((x0, 0, z0), (x1, 0, z1), (110, 64, 50), h=.9, gap=.5)
    for (x, z) in ((-24, 11), (24, 26), (-6, 27), (8, 27), (-8, 10), (8, 10)):
        g.lamp(x, 0, z, 4.4)
    for (x, z) in ((-22, 26), (26, 12), (-4, 26.5), (4, 26.5)):
        g.planter(x, 0, z)
    for (x, z) in ((-24.6, 9.5), (-24.2, 20)):
        g.tree(x, 0, z, .9)
    g.planter(25, 0, 29.5)
    for (x, z, r) in ((-8, 24, 0), (8, 24, 0), (22, 20, math.pi/2)):
        g.bench(x, 0, z, r)
    # Corner shop buildings with a terrace at y 4 (upper level over the plaza).
    for x0, x1 in ((-36, -28), (28, 36)):
        g.bounds((x0, 0, 12), (x1, 4, 28), PEACH, PLASTER, top=PAVING, pats={'top': FLAGSTONE})
        face = 'east' if x0 < 0 else 'west'
        fx = x1 if x0 < 0 else x0
        n = 1 if x0 < 0 else -1
        for z in (15, 20, 25):
            g.box((fx+n*.05, 1.5, z), (.1, 2.3, 3.0), (250, 214, 160), WINDOW, collide=False)
            g.box((fx+n*.8, 2.9, z), (1.6, .1, 3.4), RED_ARCH if x0 < 0 else TEAL, collide=False)
        rail_x = x1-.1 if x0 < 0 else x0+.1
        g.railing((rail_x, 4, 12), (rail_x, 4, 24.5), IRON)
        g.railing((x0+.1, 4, 12), (x1-.1, 4, 12), IRON)
        xm = (x0+x1)/2
        g.railing((x0+.1, 4, 28), (xm-1.4, 4, 28), IRON)
        g.railing((xm+1.4, 4, 28), (x1-.1, 4, 28), IRON)
        # stairs up from the plaza (south end)
        g.stairs((xm, 0, 36.0), (xm, 4, 28.06), 2.4, STONE, FLAGSTONE, side_color=STONE_D)
        g.planter((x0+x1)/2, 4, 18, 3, .7)
        g.bench((x0+x1)/2, 4, 22, math.pi/2)


def west_side(g):
    g.zone('oeste')
    # Building A (oxygen destination), doors east and north.
    g.block(-62, -44, 12, 34, 14, wall=MINT, faces=('east', 'north'), style='sill', accent=WHITE)
    g.door(-44, 0, 23, (1, 0), color=SKY_BLUE)
    g.door(-52, 0, 12, (0, -1), color=SKY_BLUE)
    g.box((-43.9, 9, 23), (.1, 2.2, 6), WHITE, collide=False)
    g.box((-43.8, 9, 23), (.1, 1.4, 1.4), RED_ARCH, collide=False)
    for z in (17, 29):
        g.oxygen_box(-42.8, 0, z)
    # Western back block (backdrop) along the WS street.
    g.block(-62, -44, 34, 72, 24, faces=('east',), style='balcony', crowd=True)
    # South cross street dressing
    for x in (-42, -38):
        g.lamp(x, 0, 34, 4.2)
    g.tree(-40.5, 0, 42, .8)
    g.planter(-37.5, 0, 46)
    for i in range(4):
        g.crate(-43, 0, 60+i*1.1, 1.0, .2*i)


def east_side(g):
    g.zone('leste')
    g.block(44, 62, 35, 72, 24, faces=('west',), style='balcony', crowd=True)
    # SE yard (colony-friendly courtyard) enclosed by low walls with two openings.
    g.bounds((44, 0, 10), (45, 2.6, 18), CREAM2, BRICK)
    g.bounds((44, 0, 25), (45, 2.6, 34), CREAM2, BRICK)
    g.bounds((44, 0, 34), (62, 2.6, 35), CREAM2, BRICK)
    g.bounds((61, 0, 10), (62, 2.6, 35), CREAM2, BRICK)
    for (x, z, s) in ((50, 30, 1.4), (52, 30, 1.0), (56, 14, 1.4), (58, 22, 1.2), (49, 13, 1)):
        g.crate(x, 0, z, s, .3)
    g.bounds((53, 0, 18), (60, 3, 24), (110, 150, 190), METAL, top=(96, 130, 170))
    g.tree(48, 0, 22, .9)
    for x in (38, 42):
        g.lamp(x, 0, 34, 4.2)
    for i in range(3):
        g.cart(42.5, 0, 52+i*2, .3)


def north_center(g):
    g.zone('norte_centro')
    # Arcaded shophouses facing the canal: ground floor is an open hall with pillars.
    for x0, x1, gap in ((-36, -8, (-24, -20)), (8, 36, (20, 24))):
        g.bounds((x0, 3.6, -18), (x1, 8, -10), PEACH, PLASTER, top=TERRACOTTA, pats={'top': ROOF})
        g.facade(x0, x1, -10, 3.6, 4.6, 1, 'x', style='shutter', start_floor=0)
        g.facade(x0, x1, -18, 3.6, 4.6, -1, 'x', style='shutter', start_floor=0)
        for x in range(x0+4, x1-3, 4):
            for z in (-17.6, -10.4):
                g.box((x, 1.8, z), (.8, 3.6, .8), CREAM2, PLASTER)
        g.overlay(x0+.4, -17.8, x1-.4, -10.2, TILE_C, TILE, 4)
        for x in range(x0+2, x1-1, 6):
            g.box((x, .45, -14), (1.6, .9, .7), WOOD, PLANK)
            g.oxygen_box(x+.2, .9, -14)
        g.bounds((x0, 0, -18), (x0+.4, 3.6, -10), PEACH, PLASTER)
        g.bounds((x1-.4, 0, -18), (x1, 3.6, -10), PEACH, PLASTER)
    # Central street to the works, with a wooden walkway on the east facade.
    g.overlay(-8, -44, 8, -9, PAVING2, FLAGSTONE, 3)
    g.block(-36, -8, -44, -26, 18, faces=('east', 'south', 'north'), style='balcony', crowd=True)
    g.block(10.5, 36, -44, -26, 18, faces=('west', 'south', 'north'), style='sill', wall=CREAM2, face_start={'west': 2})
    g.bounds((8, 4.0, -42), (10.5, 4.3, -27.5), WOOD, PLANK)
    g.railing((8.05, 4.3, -42), (8.05, 4.3, -27.5), WOOD)
    g.railing((8.05, 4.3, -42), (10.5, 4.3, -42), WOOD)
    g.stairs((9.25, 0, -19), (9.25, 4.3, -27.5), 2.4, WOOD, PLANK, side_color=(190, 140, 76))
    g.railing((8.05, 0, -19), (8.05, 4.3, -27.5), WOOD)
    for z in (-30, -36, -41):
        g.box((8.2, 2, z), (.25, 4, .25), IRON)
    # Street furniture
    for (x, z) in ((-6, -20), (6, -34), (-6, -40), (6, -24)):
        g.lamp(x, 0, z, 4.2)
    g.barrier(-3, 0, -31, math.pi/2)
    g.crate(5.5, 0, -32, 1.0, .4)
    g.crate(5.8, 1.0, -32.1, .7, .7)
    g.planter(-6.5, 0, -27, 1.4, .7)
    # Rua Norte & Rua da Obra floors
    g.overlay(-44, -26, 44, -18, PAVING, FLAGSTONE, 2)
    g.overlay(-44, -52, 62, -44, SAND, FLAGSTONE, 2)


def north_west(g):
    g.zone('noroeste')
    # Depot with a recess (recuo) toward the WS street.
    g.block(-62, -48, -24, -9, 9, wall=CREAM2, faces=('east', 'north'), style='shutter', accent=TEAL)
    g.bounds((-48, 0, -24), (-46, 4, -22), WOOD, PLANK)
    for (x, z, s) in ((-47, -12, 1.2), (-46.5, -13.4, .8), (-45.8, -11.4, 1.0)):
        g.crate(x, 0, z, s, .2)
    # Courtyard (pátio) with a tree and benches, between the depot and building C.
    g.overlay(-62, -38, -44, -24, PAVING2, FLAGSTONE, 3)
    g.tree(-56, 0, -31, 1.3)
    g.bench(-50, 0, -27)
    g.bench(-58, 0, -35, math.pi/2)
    g.planter(-47, 0, -36)
    g.laundry(-61, -50, 3.2, -25)
    # Building C: oxygen destination, doors south (courtyard) and east (Rua da Obra).
    g.block(-62, -44, -62, -38, 16, wall=(232, 214, 236), faces=('east', 'south'), style='sill', accent=WHITE)
    g.door(-53, 0, -38, (0, 1), color=SKY_BLUE)
    g.door(-44, 0, -50, (1, 0), color=SKY_BLUE)
    g.box((-43.9, 10, -50), (.1, 2.2, 6), WHITE, collide=False)
    g.box((-43.8, 10, -50), (.1, 1.4, 1.4), RED_ARCH, collide=False)
    g.block(-62, -44, -94, -62, 20, faces=('east',), style='shutter', wall=(206, 196, 180))
    for (x, z) in ((-42, -30), (-38, -40), (-42, -56)):
        g.lamp(x, 0, z, 4.2)


def north_east(g):
    g.zone('nordeste')
    # Building B: oxygen destination, doors west (ES street) and north (Rua da Obra).
    g.block(44, 62, -42, -12, 14, wall=(246, 222, 170), faces=('west', 'north', 'south'), style='sill', accent=WHITE)
    g.door(44, 0, -30, (-1, 0), color=SKY_BLUE)
    g.door(52, 0, -42, (0, -1), color=SKY_BLUE)
    g.box((43.9, 9, -30), (.1, 2.2, 6), WHITE, collide=False)
    g.box((43.8, 9, -30), (.1, 1.4, 1.4), RED_ARCH, collide=False)
    g.overlay(44, -12, 62, -9, PAVING2, FLAGSTONE, 3)
    for i in range(3):
        g.oxygen_box(46+i, 0, -10.5)
    g.block(44, 62, -94, -52, 20, faces=('west', 'south'), style='shutter', wall=(206, 196, 180))
    for (x, z) in ((42, -16), (38, -36), (42, -50)):
        g.lamp(x, 0, z, 4.2)


def wound_site(g):
    g.zone('obra_ferida')
    px0, px1, pz0, pz1 = PIT
    # Pit: tissue floor with the dark net-like grid of the rupture.
    g.bounds((-10, PIT_FLOOR-1, pz0), (10, PIT_FLOOR, -70), WOUND, TISSUE)
    for xs, xe in ((px0, -10), (10, px1)):
        lo = -10 if xs < 0 else 10
        hi = px0 if xs < 0 else px1
        g.ramp((lo, PIT_FLOOR, -78), (hi, 0, -78), 8, SAND, DIRT, thick=.2)
        for z0, z1 in ((pz0, -82), (-74, -70)):
            g.bounds((xs, -3, z0), (xe, 0, z1), (122, 84, 80), TISSUE, top=SAND, pats={'top': DIRT})
    g.bounds((px0, -3, -70), (px1, 0, pz1), (122, 84, 80), TISSUE, top=SAND, pats={'top': DIRT})
    # Torn pavement edges and debris shields (protect the bacterial entrance).
    rng = g.rng
    g.box((0, -1.0, -73.4), (9, 3.4, 1.4), (150, 120, 112), TISSUE, ry=.05)
    g.box((-6.5, -1.4, -75), (3.4, 2.4, 1.2), (150, 120, 112), TISSUE, ry=.5)
    g.box((6.5, -1.4, -75), (3.4, 2.4, 1.2), (150, 120, 112), TISSUE, ry=-.5)
    for _ in range(26):
        x = rng.uniform(px0-3, px1+3)
        z = rng.choice((rng.uniform(-70, -66), rng.uniform(pz0-3, pz0)))
        s = rng.uniform(.5, 1.4)
        g.box((x, s*.3, z), (s*1.4, s*.6, s), PAVING2, FLAGSTONE, ry=rng.uniform(0, 3), collide=s > 1.1)
    for _ in range(14):
        x, z = rng.uniform(-9, 9), rng.uniform(pz0+1, -76)
        g.sphere((x, PIT_FLOOR, z), rng.uniform(.4, 1.1), FLESH, TISSUE, seg=7, rings=4, squash=.6)
    # Platelet repair: partial clot net over the south lip, sandbags, cones, barriers.
    g.face([(-9, .05, -66.5), (9, .05, -66.5), (9, -1.2, -70.5), (-9, -1.2, -70.5)], NET_C, NET, (0, 1, 0))
    for x in range(-12, 13, 3):
        g.barrier(x, 0, -63.5, 0, 2.6)
    for x in (-14, -9, 9, 14):
        g.cone(x, 0, -62)
    for i in range(6):
        g.box((-13+i*.9, .25, -60.5), (.85, .5, .5), SAND, collide=False)
    # Scaffolding platform (upper level) west of the pit.
    sx0, sx1, sz0, sz1 = -36, -22, -72, -60
    g.bounds((sx0, 3.8, sz0), (sx1, 4.1, sz1), WOOD, PLANK)
    for x in range(sx0, sx1+1, 3):
        for z in (sz0, sz1):
            g.cylinder((x, 0, z), .1, 6.2, SKY_BLUE, METAL, seg=6)
    for y in (2, 6):
        for z in (sz0, sz1):
            g.tube([(sx0, y, z), (sx1, y, z)], .07, SKY_BLUE, METAL, seg=5)
    g.railing((sx0, 4.1, sz0), (sx1, 4.1, sz0), SKY_BLUE)
    g.railing((sx0, 4.1, sz0), (sx0, 4.1, sz1), SKY_BLUE)
    g.railing((sx1, 4.1, sz0), (sx1, 4.1, sz1-3), SKY_BLUE)
    g.stairs((-25, 0, -50.5), (-25, 4.1, -60), 2.6, WOOD, PLANK, side_color=(190, 140, 76))
    g.collider((sx0-.2, 0, sz0-.2), (sx1+.2, .01, sz0+.2))
    for (x, z) in ((-33, -66), (-29, -63), (-31, -69)):
        g.crate(x, 0, z, 1.2, .3)
        g.crate(x, 4.1, z+1, .9, .1)
    # Ladders and materials (reference: platelets carrying ladders).
    for i in range(5):
        g.box((-40+i*.5, 1.2, -58), (.1, 2.4, 1.6), (172, 150, 110), PLANK, collide=False, ry=.3)
    # Maintenance tunnel: brick vault through a block (east of the pit).
    tx0, tx1 = 16, 36
    g.bounds((tx0, 0, -72), (tx1, 7, -66), BRICK_C, BRICK, top=TERRACOTTA, pats={'top': ROOF})
    g.bounds((tx0, 0, -58), (tx1, 7, -52), BRICK_C, BRICK, top=TERRACOTTA, pats={'top': ROOF})
    g.bounds((tx0, 5, -66), (tx1, 7, -58), BRICK_C, BRICK, top=TERRACOTTA, pats={'top': ROOF})
    steps = 12
    for i in range(steps):
        a0, a1 = math.pi*i/steps, math.pi*(i+1)/steps
        z0_, y0_ = -62-math.cos(a0)*4, 1+math.sin(a0)*4
        z1_, y1_ = -62-math.cos(a1)*4, 1+math.sin(a1)*4
        g.face([(tx0, y0_, z0_), (tx1, y0_, z0_), (tx1, y1_, z1_), (tx0, y1_, z1_)], BRICK_D, BRICK,
               (0, 1-(y0_+y1_)/2, -62-(z0_+z1_)/2), smooth=True)
    for x in (tx0, tx1):
        g.arch_wall((x, 0, -62), 20, 7.4, .8, 7.7, 5, 'z', BRICK_C, BRICK, collide=False, intrados=BRICK_D)
    g.overlay(tx0, -66, tx1, -58, (196, 176, 140), DIRT, 4)
    for x in range(tx0+3, tx1-2, 5):
        g.barrier(x, 0, -65.0, 0, 2.2)
        g.lamp(x+2, 0, -59.8, 2.6)
    g.crate(26, 0, -62, 2.6, 0, (150, 112, 70))
    g.crate(26, 2.6, -62, 2.0, .1, (150, 112, 70))
    g.crate(34, 0, -60, 1.2, .3)
    # Red construction cranes (landmarks visible from far away).
    for (cx, cz, h, ang) in ((30, -84, 26, 2.3), (-30, -86, 22, .6)):
        for lx, lz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            g.tube([(cx+lx, 0, cz+lz), (cx+lx*.7, h, cz+lz*.7)], .12, (214, 70, 60), METAL, seg=5)
        for y in range(2, h, 3):
            g.box((cx, y, cz), (2.2, .18, 2.2), (240, 236, 230) if (y//3) % 2 else (214, 70, 60), collide=False)
        g.collider((cx-1.2, 0, cz-1.2), (cx+1.2, h, cz+1.2))
        L = 18
        ex, ez = cx+math.cos(ang)*L, cz+math.sin(ang)*L
        g.tube([(cx-math.cos(ang)*5, h, cz-math.sin(ang)*5), (ex, h, ez)], .3, (214, 70, 60), METAL, seg=6)
        g.box((cx-math.cos(ang)*5, h-.6, cz-math.sin(ang)*5), (2, 1.6, 2), DARK, collide=False)
        g.tube([(ex, h, ez), (ex, h-9, ez)], .04, IRON, seg=4)
        g.box((ex, h-9.6, ez), (1.6, 1.0, 1.6), WOOD, PLANK, collide=False)


def boundary(g):
    g.zone('limites')
    H = 40
    g.collider((X0-1, -4, Z0), (X0, H, Z1))
    g.collider((X1, -4, Z0), (X1+1, H, Z1))
    g.collider((X0, -4, Z0-1), (X1, H, Z0))
    g.collider((X0, -4, Z1), (X1, H, Z1+1))


VESSELS = (((-170, -10, 60), (170, -10, -40), 70, 3.5, (242, 230, 200)),
           ((-170, -10, -150), (170, -10, -70), 80, 4.5, (238, 206, 190)))
RING = 16  # depth of the closed perimeter row outside the playable area


def vessel_points():
    out = []
    for a, b, hgt, r, col in VESSELS:
        pts = [(a[0]+(b[0]-a[0])*i/24, a[1]+math.sin(math.pi*i/24)*hgt, a[2]+(b[2]-a[2])*i/24) for i in range(25)]
        out.append((pts, r, col))
    return out


def clear_of_vessels(x0, z0, x1, z1, h):
    """Highest roof that keeps a building clear of the sky vessels (0 if it must be skipped)."""
    top = h
    for pts, r, _ in vessel_points():
        for i in range(len(pts)-1):
            for k in range(5):
                t = k/4
                px = pts[i][0]+(pts[i+1][0]-pts[i][0])*t
                py = pts[i][1]+(pts[i+1][1]-pts[i][1])*t
                pz = pts[i][2]+(pts[i+1][2]-pts[i][2])*t
                if x0-r-2 <= px <= x1+r+2 and z0-r-2 <= pz <= z1+r+2:
                    top = min(top, py-r-3)
    return top


def perimeter(g):
    """Continuous row of buildings just outside the boundary: no street ends in the void."""
    g.zone('perimetro')
    rng = g.rng
    sides = (('west', X0-RING, X0, Z0-RING, Z1+RING, 'z'), ('east', X1, X1+RING, Z0-RING, Z1+RING, 'z'),
             ('south', X0, X1, Z1, Z1+RING, 'x'), ('north', X0, X1, Z0-RING, Z0, 'x'))
    for name, x0, x1, z0, z1, along in sides:
        a, end = (z0, z1) if along == 'z' else (x0, x1)
        while a < end-.1:
            w = min(end-a, rng.uniform(10, 17))
            if end-(a+w) < 6:
                w = end-a
            b = a+w
            if along == 'z':
                bx0, bx1, bz0, bz1 = x0, x1, a, b
            else:
                bx0, bx1, bz0, bz1 = a, b, z0, z1
            damaged = name == 'north'
            h = rng.uniform(16, 30) if not damaged else rng.uniform(10, 22)
            h = max(8, clear_of_vessels(bx0, bz0, bx1, bz1, h))
            canal_span = along == 'z' and bz0 < CANAL[1]+2 and bz1 > CANAL[0]-2
            y0 = 3.9 if canal_span else -3
            wall = rng.choice((CREAM, CREAM2, PEACH, (236, 216, 184), MINT)) if not damaged else rng.choice(((206, 186, 172), (196, 170, 160)))
            if canal_span:
                # Building over the culvert: sits on top of the tunnel vault.
                g.bounds((bx0, y0, bz0), (bx1, h, bz1), wall, PLASTER, collide=False, top=CREAM2)
                for zz0, zz1 in ((bz0, min(bz1, CANAL[0]-.5)), (max(bz0, CANAL[1]+.5), bz1)):
                    if zz1 > zz0:
                        g.bounds((bx0, -3, zz0), (bx1, y0, zz1), wall, PLASTER, collide=False)
            else:
                g.bounds((bx0, -3, bz0), (bx1, h, bz1), wall, PLASTER, collide=False, top=CREAM2, skip=('bottom',))
            face = {'west': ('z', bz0, bz1, bx1, 1), 'east': ('z', bz0, bz1, bx0, -1),
                    'south': ('x', bx0, bx1, bz0, -1), 'north': ('x', bx0, bx1, bz1, 1)}[name]
            style = rng.choice(('balcony', 'sill', 'shutter')) if not damaged else 'shutter'
            g.facade(face[1], face[2], face[3], -3 if not canal_span else y0, h-(-3 if not canal_span else y0), face[4], face[0],
                     style=style, start_floor=2, laundry=not damaged, crowd=not damaged)
            if damaged:
                # Torn tops and rubble: the district ripped open next to the rupture.
                for _ in range(3):
                    cx, cz = rng.uniform(bx0+1, bx1-1), rng.uniform(bz0+1, bz1-1)
                    g.box((cx, h+rng.uniform(.5, 2.5), cz), (rng.uniform(2, 5), rng.uniform(1.5, 4), rng.uniform(2, 5)),
                          (130, 96, 90), TISSUE, collide=False, ry=rng.uniform(0, 3))
                g.bounds((bx0, -3, bz1-.01), (bx1, 2.2, bz1+.6), (150, 110, 104), TISSUE, collide=False)
            a = b


def skyline(g):
    g.zone('horizonte')
    rng = g.rng
    placed = []
    # Taller towers beyond the perimeter row (not collidable, never overlapping).
    for side in range(4):
        for i in range(10):
            for _ in range(8):
                t = (i+.5)/10
                if side in (0, 1):
                    x = X0-30+(X1-X0+60)*t+rng.uniform(-5, 5)
                    z = (Z0-RING-12-rng.uniform(0, 30)) if side == 0 else (Z1+RING+10+rng.uniform(0, 30))
                else:
                    z = Z0-30+(Z1-Z0+60)*t+rng.uniform(-5, 5)
                    x = (X0-RING-10-rng.uniform(0, 30)) if side == 2 else (X1+RING+10+rng.uniform(0, 30))
                w, d = rng.uniform(14, 22), rng.uniform(12, 18)
                rect = (x-w/2, z-d/2, x+w/2, z+d/2)
                if any(not (rect[2]+2 < o[0] or o[2]+2 < rect[0] or rect[3]+2 < o[1] or o[3]+2 < rect[1]) for o in placed):
                    continue
                h = clear_of_vessels(*rect, rng.uniform(30, 62))
                if h < 22:
                    continue
                placed.append(rect)
                wall = rng.choice((CREAM, CREAM2, PEACH, (236, 216, 184), MINT))
                g.bounds((rect[0], -3, rect[1]), (rect[2], h, rect[3]), wall, PLASTER, collide=False, top=CREAM2)
                face = {0: 'south', 1: 'north', 2: 'east', 3: 'west'}[side]
                fx = {'south': ('x', rect[0], rect[2], rect[3], 1), 'north': ('x', rect[0], rect[2], rect[1], -1),
                      'east': ('z', rect[1], rect[3], rect[2], 1), 'west': ('z', rect[1], rect[3], rect[0], -1)}[face]
                g.facade(fx[1], fx[2], fx[3], -3, h, fx[4], fx[0], style='balcony' if rng.random() < .5 else 'sill',
                         floor_h=3.4, start_floor=2, laundry=False)
                break
    # Giant vessel arches crossing the sky (reference: cream vessel over the street).
    for pts, r, col in vessel_points():
        g.tube(pts, r, col, PLASTER, seg=12)


# ---------------------------------------------------------------------------
def markers(g):
    P = {}
    for i, x in enumerate((-4, 0, 4)):
        P[f'spawn_cells.{i}'] = (x, 0, 86)
        P[f'spawn_bacteria.{i}'] = (x, PIT_FLOOR, -84 if x else -86)
    escort = [(0, 0, 66), (0, 0, 52), (0, 0, 38), (-6, 0, 28), (-6.5, 0, 20), (-4, 0, 12), (0, 0, 9.5), (0, 1, 5),
              (0, 1, -5), (0, 0, -9.5), (0, 0, -18), (3, 0, -28), (0, 0, -40), (0, 0, -52), (0, 0, -64.5)]
    for i, p in enumerate(escort):
        P[f'escort.{i:02}'] = p
    P['wound'] = (0, PIT_FLOOR, -78)
    P['recon'] = (-12.2, 0, 18)
    nodes = {
        'depot': (5, 0, 42), 'S': (0, 0, 32), 'SW': (-40, 0, 31), 'A_e': (-42, 0, 23), 'WBs': (-40, 0, 13.5),
        'WSb': (-45, 0, 10), 'A_n': (-52, 0, 10), 'WB': (-40, 2.6, 0), 'WBn': (-40, 0, -13.5), 'O': (-40, 0, -22),
        'court': (-48, 0, -31), 'C_s': (-53, 0, -36.5), 'WN': (-40, 0, -48), 'C_e': (-42, 0, -50),
        'P': (-6.5, 0, 20), 'P2': (6.5, 0, 20), 'Pw': (-27, 0, 10), 'Pw2': (-37, 0, 11.5), 'Pe': (27, 0, 9.5),
        'MBs': (0, 0, 10), 'MB': (0, 1, 0), 'MBn': (0, 0, -10), 'NC': (0, 0, -22), 'NS': (2, 0, -34),
        'N': (0, 0, -48), 'L': (40, 0, -22), 'B_w': (42, 0, -30), 'EN': (40, 0, -48), 'B_n': (52, 0, -46),
        'SE': (40, 0, 31), 'ESs': (40, 0, 13), 'EB': (40, .9, 0), 'EBn': (40, 0, -13),
    }
    edges = [('depot', 'S'), ('S', 'SW'), ('SW', 'A_e'), ('A_e', 'WBs'), ('WBs', 'WSb'), ('WSb', 'A_n'), ('WBs', 'WB'),
             ('WB', 'WBn'), ('WBn', 'O'), ('O', 'court'), ('court', 'C_s'), ('O', 'WN'), ('WN', 'C_e'),
             ('S', 'P'), ('S', 'P2'), ('P', 'MBs'), ('P2', 'MBs'), ('P', 'Pw'), ('Pw', 'Pw2'), ('Pw2', 'WBs'),
             ('P2', 'Pe'), ('Pe', 'ESs'), ('MBs', 'MB'), ('MB', 'MBn'), ('MBn', 'NC'), ('NC', 'O'), ('NC', 'L'),
             ('NC', 'NS'), ('NS', 'N'), ('N', 'WN'), ('N', 'EN'), ('EN', 'B_n'), ('L', 'B_w'), ('B_w', 'EN'),
             ('L', 'EBn'), ('EBn', 'EB'), ('EB', 'ESs'), ('ESs', 'SE'), ('SE', 'S')]
    for k, v in nodes.items():
        P[f'rbc.{k}'] = v
    hints = [(-53, 0, -30), (-8, CANAL_FLOOR, -1.5), (8, CANAL_FLOOR, 1.5), (52, 0, 26), (-30, 0, -54),
             (31, 0, -63.5), (-26, CANAL_FLOOR, 0), (26, CANAL_FLOOR, 0), (-46, 0, -16), (52, 0, 14),
             (-20, 0, 32), (20, 0, -48), (-32, 4, 20), (-14, 0, -48)]
    for i, h in enumerate(hints):
        P[f'colony.{i:02}'] = h
    return {
        'points': P,
        'rbc_edges': edges,
        'destinations': {'A': ['A_e', 'A_n'], 'B': ['B_w', 'B_n'], 'C': ['C_s', 'C_e']},
        'cells_base': [-24, 66, 24, 94],
        'bounds': [X0, Z0, X1, Z1],
        'nav_ceilings': [9.0, 5.6, 2.9, .5, -1.4],
        'canal': [CANAL[0], CANAL[1], CANAL_FLOOR],
        'ambient_spots': [list(s) for s in getattr(g, 'spots', [])],
    }
