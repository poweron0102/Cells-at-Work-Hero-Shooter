"""Layout do Timo (S01E09 - Timocito), escrito em coordenadas do jogo.

x = leste, y = cima, z = sul. Base das celulas ao sul (+z), ferida ao norte (-z).
Referencias em ``referencias/Timo/`` (README com o que cada quadro inspirou).

Zonas (sul -> norte):
  z  62..78  Dormitorio dos timocitos (base das celulas), duas saidas com anteparos
  z  46..60  Rua do portao (deposito das hemacias a leste)
  z  16..46  Campo de treino: terra batida, alambrado com arame farpado, pista de obstaculos,
             torre de observacao (reconhecimento)
  z -26..16  Labirinto do exame final: muros de concreto, grama, arbustos, poste de alto-falante
  z -60..-26 Patio da escola (biblioteca = edificio C), caixa-d'agua
  z -80..-60 Capsula do timo rompida: cratera de tecido onde as bacterias entram
A oeste, a trilha da floresta (refeitorio = edificio A, plataforma de observacao); a leste, o
corredor dos galpoes (ginasio = edificio B, arquibancada voltada para o labirinto).
"""
import math
from distrito_geo import *  # noqa: F401,F403

X0, X1, Z0, Z1 = -50, 50, -80, 78
MAZE = (-30, 30, -26, 16)
PIT = (-14, 14, -76, -60)
PIT_FLOOR = -2.5
WALL_H, OUTER_H, WALL_T = 2.8, 3.2, .5

CONCRETE = (226, 222, 210)
CONCRETE_D = (196, 192, 182)
GRASS = (150, 184, 112)
DIRT_C = (214, 174, 112)
DIRT_D = (190, 150, 96)
TRAIL_C = (200, 170, 124)
DORM = (236, 222, 196)
TEAL_RAIL = (52, 130, 140)
CHAIN = (128, 134, 138)


def build(g, only=None):
    sections = [ground, dormitory, gate_street, field, west_trail, east_lane, maze, north_plaza, capsule_breach,
                boundary, perimeter]
    for fn in sections:
        if only and fn.__name__ not in only:
            continue
        fn(g)
    g.flush_facades()
    g.flush_overlays()
    return markers(g)


# ---------------------------------------------------------------------------
def oxygen_sign(g, x, y, z, n, along='z'):
    """Placa branca com a marca vermelha de entrega de oxigenio (como no Bairro Arterial)."""
    if along == 'z':
        g.box((x+n*.1, y, z), (.1, 2.2, 5), WHITE, collide=False)
        g.box((x+n*.2, y, z), (.1, 1.4, 1.4), RED_ARCH, collide=False)
        g.keep_clear((x-.4, y-1.3, z-2.8), (x+.4, y+1.3, z+2.8))
    else:
        g.box((x, y, z+n*.1), (5, 2.2, .1), WHITE, collide=False)
        g.box((x, y, z+n*.2), (1.4, 1.4, .1), RED_ARCH, collide=False)
        g.keep_clear((x-2.8, y-1.3, z-.4), (x+2.8, y+1.3, z+.4))


def ground(g):
    g.zone('chao')
    side = {'north': ASHLAR, 'south': ASHLAR, 'east': ASHLAR, 'west': ASHLAR, 'top': FLAGSTONE}
    px0, px1, pz0, pz1 = PIT
    # Chao do mapa com o buraco da cratera.
    for lo, hi in (((X0, -3, pz1), (X1, 0, Z1)), ((X0, -3, Z0), (X1, 0, pz0)),
                   ((X0, -3, pz0), (px0, 0, pz1)), ((px1, -3, pz0), (X1, 0, pz1))):
        g.bounds(lo, hi, STONE, FLAGSTONE, top=PAVING, pats=side)
    # Acabamentos do piso (o de maior prioridade recorta os outros).
    g.overlay(X0, 46, X1, 61, (214, 208, 198), FLAGSTONE, 2)       # rua do portao
    g.overlay(-30, 16, 30, 46, DIRT_C, DIRT, 3)                    # campo de treino
    g.overlay(-42, -40, -30, 61, TRAIL_C, DIRT, 3)                 # trilha da floresta
    g.overlay(X0, -40, -42, 46, (138, 168, 104), LEAF, 1)          # chao da floresta
    g.overlay(MAZE[0], MAZE[2], MAZE[1], MAZE[3], GRASS, LEAF, 4)  # grama do labirinto
    g.overlay(30, -40, 38, 46, (206, 200, 190), FLAGSTONE, 3)      # corredor dos galpoes
    g.overlay(X0, -60, X1, -26, PAVING2, FLAGSTONE, 2)             # patio da escola


def dormitory(g):
    """Dormitorio dos timocitos (S01E09 09:24): predio creme de varios andares com sacadas.
    O terreo e a estacao das celulas: duas portas para o norte e anteparos na frente."""
    g.zone('base_celulas')
    x0, x1, z0, z1, h = -24, 24, 62, 78, 8
    doors = [(-16, -12), (12, 16)]
    xs = [x0]+[d for pair in doors for d in pair]+[x1]
    for i in range(0, len(xs), 2):
        g.bounds((xs[i], 0, z0), (xs[i+1], h, z0+1), DORM, PLASTER)
    for a, b in doors:
        g.bounds((a, 3.4, z0), (b, h, z0+1), DORM, PLASTER)
        g.box(((a+b)/2, 3.7, z0-.7), (b-a+1.2, .12, 1.6), TEAL, collide=False)
    for x in (x0, x1-1):
        g.bounds((x, 0, z0+1), (x+1, h, z1), DORM, PLASTER)
    g.bounds((x0+1, 0, z1-1), (x1-1, h, z1), DORM, PLASTER)
    # Andares de cima (so fachada; ninguem sobe): o predio das sacadas do episodio.
    g.bounds((x0, h, z0), (x1, 22, z1), DORM, PLASTER, top=CREAM2, pats={'top': ROOF})
    g.solid((x0, 0, z0), (x1, 22, z1))
    g.facade(x0, x1, z0, h, 22-h, -1, 'x', style='balcony', wall=DORM, accent=(206, 196, 176), start_floor=0,
             laundry=True, crowd=True)
    # Placa do dormitorio.
    g.box((0, 6.2, z0-.15), (18, 1.6, .3), TEAL, collide=False)
    g.box((0, 6.2, z0-.36), (12, 1.0, .12), WHITE, collide=False)
    g.keep_clear((-9, 5, z0-1), (9, 7.4, z0+.5))
    # Interior: piso de madeira, armarios, beliches, pilares.
    g.overlay(x0+1, z0+1, x1-1, z1-1, (206, 160, 104), PLANK, 6)
    for x in range(-20, 21, 4):
        g.box((x, 1.1, z1-1.5), (1.6, 2.2, .8), (186, 196, 200), METAL)
    for x in (-19, 19):
        for dz in (0, 4):
            g.box((x, .45, 67+dz), (2.2, .9, 1.0), (120, 100, 80), PLANK)
            g.box((x, 1.85, 67+dz), (2.2, .12, 1.0), (120, 100, 80), PLANK, collide=False)
    for x in (-8, 8):
        g.bench(x, 0, 70)
        g.box((x, 4, 67), (.8, 8, .8), CREAM2, PLASTER)
    # Anteparos na frente das saidas (sem tiro direto para dentro da base).
    for a, b in doors:
        cx = (a+b)/2
        g.bounds((cx-4, 0, 56.6), (cx+4, 3.0, 57.4), CONCRETE_D, PLASTER)
        g.planter(cx, 3.0, 57, 7.6, .7)
    # Alas vizinhas do dormitorio (fora da area jogavel).
    g.block(X0, x0, 64, Z1, 20, wall=DORM, faces=('north',), crowd=True)
    g.block(x1, X1, 64, Z1, 20, wall=DORM, faces=('north',), crowd=True)


def gate_street(g):
    """Rua do portao: portao de pedra com grade (S01E09 07:54), postes e o deposito das hemacias."""
    g.zone('rua_portao')
    # Portao do campo: dois pilares de pedra e as folhas de grade abertas.
    for x in (-4, 10):
        g.bounds((x-.8, 0, 45.2), (x+.8, 3.6, 46.8), (196, 186, 170), ASHLAR)
        g.box((x, 3.8, 46), (2.0, .4, 2.0), (170, 160, 146), ASHLAR, collide=False)
        g.lamp(x, 3.6, 46, .9)
    for x, sgn in ((-3.2, 1), (9.2, -1)):
        for k in range(7):
            g.box((x, 1.3, 46.6+k*.5), (.05, 2.6, .05), IRON, collide=False)
        g.box((x, 2.5, 48.1), (.06, .08, 3.0), IRON, collide=False)
        g.box((x, .3, 48.1), (.06, .08, 3.0), IRON, collide=False)
    # Alambrado do campo (com o portao e as passagens laterais).
    g.fence((-30, 0, 46), (-4.8, 0, 46))
    g.fence((10.8, 0, 46), (30, 0, 46))
    # Postes de luz e bancos ao longo da rua.
    for x in (-40, -22, 22, 40):
        g.lamp(x, 0, 60.2)
    for x in (-30, 30):
        g.bench(x, 0, 60.4, 0)
    # Deposito das hemacias (galpao a leste): porta voltada para oeste.
    sx0, sx1, sz0, sz1, h = 38, 50, 48, 60, 6
    g.bounds((sx0, 0, sz0), (sx1, h, sz0+.6), (222, 196, 160), PLASTER)
    g.bounds((sx0, 0, sz1-.6), (sx1, h, sz1), (222, 196, 160), PLASTER)
    g.bounds((sx1-.6, 0, sz0+.6), (sx1, h, sz1-.6), (222, 196, 160), PLASTER)
    g.bounds((sx0, 0, sz0+.6), (sx0+.6, h, 51.5), (222, 196, 160), PLASTER)
    g.bounds((sx0, 0, 56.5), (sx0+.6, h, sz1-.6), (222, 196, 160), PLASTER)
    g.bounds((sx0, 3.6, 51.5), (sx0+.6, h, 56.5), (222, 196, 160), PLASTER)
    g.bounds((sx0, h, sz0), (sx1, h+.4, sz1), CREAM2, PLASTER, top=TERRACOTTA, pats={'top': ROOF})
    g.solid((sx0, 0, sz0), (sx1, h+.4, sz1))
    g.box((sx0-.7, 3.9, 54), (1.6, .12, 6.2), RED_ARCH, collide=False)
    oxygen_sign(g, sx0, 4.8, 54, -1)
    g.overlay(sx0+.6, sz0+.6, sx1-.6, sz1-.6, (230, 236, 238), TILE, 6)
    for z in (49.6, 58.4):
        for x in range(41, 49, 2):
            g.oxygen_box(x, 0, z)
            g.oxygen_box(x, .6, z, .1)


def field(g):
    """Campo de treino (S01E09 06:42, 06:54, 08:30): terra batida, pneus, muros de escalada,
    rastejo sob arame farpado, sacos de areia e a torre de observacao."""
    g.zone('campo')
    # Alambrados laterais com uma passagem de cada lado.
    g.fence((-30, 0, 16.5), (-30, 0, 27))
    g.fence((-30, 0, 33), (-30, 0, 46))
    g.fence((30, 0, 16.5), (30, 0, 29))
    g.fence((30, 0, 35), (30, 0, 46))
    # Muros de escalada (madeira, 2,4 m) com degraus de apoio.
    for x, z in ((-12, 30.5), (18, 22), (-20, 19.5)):
        g.box((x, 1.2, z), (4.2, 2.4, .3), WOOD, PLANK)
        for k in range(3):
            g.box((x-1.4+k*1.4, .4+k*.7, z+.35), (.5, .12, .4), (150, 110, 70), PLANK, collide=False)
        for s in (-1, 1):
            g.box((x+s*2.2, 1.3, z), (.24, 2.6, .5), (150, 110, 70), PLANK)
    # Linhas de pneus.
    for i in range(6):
        for j in range(2):
            g.tire(13+i*1.1, 0, 41+j*1.1)
    for i in range(5):
        g.tire(-24+i*1.1, 0, 26)
    # Rastejo sob arame farpado: estacas baixas e fios (nao bloqueiam tiros).
    for x in range(-24, -13, 2):
        for z in (38, 41):
            g.box((x, .4, z), (.08, .8, .08), (150, 110, 70), PLANK, collide=False)
        g.tube([(x, .7, 38), (x, .7, 41)], .012, IRON, seg=4, caps=False)
    for z in (38, 39.5, 41):
        g.tube([(-24, .7, z), (-14, .7, z)], .012, IRON, seg=4, caps=False)
    # Sacos de areia (cobertura na altura do peito).
    for x0, x1, z in ((8, 13, 30), (-7, -2.5, 23), (20, 26, 37), (12, 17, 18.5)):
        n = int((x1-x0)/.9)
        for i in range(n):
            g.box((x0+.45+i*.9, .28, z), (.88, .56, .55), SAND, collide=False)
            g.box((x0+.9+i*.9, .82, z), (.86, .52, .52), SAND, collide=False) if i < n-1 else None
        g.collider((x0, 0, z-.3), (x0+n*.9, 1.1, z+.3))
    # Mesa com galao de agua (S01E09 11:12): descanso do treino.
    g.box((22, .8, 26), (2.4, .1, 1.0), (200, 204, 208), METAL)
    g.cylinder((21.4, .85, 26), .3, .7, (120, 180, 230), GLASS, seg=10)
    for dx in (-1.1, 1.1):
        g.box((22+dx, .4, 26), (.08, .8, .9), (150, 156, 160), METAL, collide=False)
    # Torre de observacao do instrutor (posto de reconhecimento).
    g.lattice_tower(-16, 0, 24, h=9, w=3.4, color=(196, 74, 64))
    g.box((-16, .05, 24), (4.6, .1, 4.6), (180, 176, 168), FLAGSTONE, collide=False)
    # Postes de alto-falante e arvores nos cantos.
    g.speaker_pole(-27, 0, 44, 6.5)
    g.speaker_pole(27, 0, 18.5, 6.5)
    for x, z in ((-26, 20), (26, 44), (-27.5, 36), (27.5, 24)):
        g.tree(x, 0, z, 1.1)


def west_trail(g):
    """Trilha da floresta (S01E09 10:48): caminho de terra entre arvores, com alambrado.
    Refeitorio (edificio A) e plataforma de observacao sobre o labirinto."""
    g.zone('trilha_oeste')
    # Arvores densas a oeste da trilha (deixando a plataforma e o refeitorio livres).
    rng = g.rng
    spots = []
    for z in range(-38, 60, 4):
        for x in (-48.5, -45, -43.5):
            if 15 <= z <= 37 or -22 <= z <= 9:
                continue  # refeitorio e plataforma
            if x == -43.5 and z % 8:
                continue
            spots.append((x+rng.uniform(-.6, .6), z+rng.uniform(-1, 1)))
    for x, z in spots:
        g.tree(x, 0, z, rng.uniform(1.0, 1.35))
    for z in range(-36, 58, 7):
        if not (15 <= z <= 37):
            g.bush(-42.6, 0, z+rng.uniform(0, 2), .8)
    # Refeitorio (edificio A): porta leste e porta sul.
    x0, x1, z0, z1, h = -50, -42, 18, 34, 7
    g.block(x0, x1, z0, z1, h, wall=(232, 214, 186), faces=('east', 'south'), style='sill', start_floor=1)
    g.door(x1, 0, 26, (1, 0), color=TEAL)
    g.door(-46, 0, z1, (0, 1), color=TEAL)
    oxygen_sign(g, x1, 4.6, 30.5, 1)
    # Plataforma de observacao (madeira, 3,2 m) com escada ao sul e ao norte.
    px0, px1, pz0, pz1, py = -48, -43, -20, 0, 3.2
    g.bounds((px0, py-.25, pz0), (px1, py, pz1), WOOD, PLANK)
    for x in (px0+.3, px1-.3):
        for z in range(pz0, pz1+1, 4):
            g.cylinder((x, 0, z), .14, py-.25, (150, 110, 70), PLANK, seg=6, collide=False)
            g.collider((x-.15, 0, z-.15), (x+.15, py-.25, z+.15))
    g.railing((px1, py, pz0), (px1, py, pz1), (150, 110, 70))
    g.railing((px0, py, pz0), (px0, py, pz1), (150, 110, 70))
    g.stairs((-45.5, 0, 7.6), (-45.5, py, pz1), 2.8, WOOD, PLANK, side_color=(170, 124, 76))
    g.stairs((-45.5, 0, -27.6), (-45.5, py, pz0), 2.8, WOOD, PLANK, side_color=(170, 124, 76))
    g.collider((px0-.1, 0, pz0-.1), (px1+.1, .01, pz0+.1))


def east_lane(g):
    """Corredor dos galpoes: ginasio (edificio B) e arquibancada de concreto voltada para o
    labirinto (S01E09 14:30: alunos sentados nos degraus atras do gradil)."""
    g.zone('corredor_leste')
    # Ginasio (edificio B): portas oeste e sul.
    x0, x1, z0, z1, h = 38, 50, 14, 30, 9
    g.block(x0, x1, z0, z1, h, wall=(214, 224, 226), faces=('west', 'south'), style='sill', roof_color=(110, 150, 170))
    g.door(x0, 0, 20, (-1, 0), color=RED_ARCH)
    g.door(44, 0, z1, (0, 1), color=RED_ARCH)
    oxygen_sign(g, x0, 5.2, 25.5, -1)
    # Patio entre o ginasio e o deposito: caixas e cones.
    for x, z in ((46, 36), (47.5, 41), (42, 44)):
        g.crate(x, 0, z, 1.2, .2)
    # Arquibancada: degraus subindo para leste ate 3,2 m, gradil azul na frente.
    bz0, bz1 = -24, 10
    g.stairs((38.4, 0, (bz0+bz1)/2), (46, 3.2, (bz0+bz1)/2), bz1-bz0, CONCRETE, PLASTER, step=.4,
             side_color=CONCRETE_D)
    g.bounds((46, 0, bz0), (50, 3.2, bz1), CONCRETE, PLASTER, top=CONCRETE_D)
    g.bounds((49.4, 3.2, bz0), (50, 5.0, bz1), CONCRETE_D, PLASTER)
    for z0_, z1_ in ((bz0, bz0+.6), (bz1-.6, bz1)):
        g.bounds((38.4, 0, z0_), (49.4, .01, z1_), CONCRETE_D, collide=False)
    g.railing((38.2, 0, bz0), (38.2, 0, bz1), TEAL_RAIL, h=1.0)
    g.railing((46.1, 3.2, bz0), (46.1, 3.2, bz0+2), TEAL_RAIL)
    # Gradil azul ao longo do muro leste do labirinto.
    g.railing((30.4, 0, -25.5), (30.4, 0, -9), TEAL_RAIL, h=1.0, collide=False)
    g.railing((30.4, 0, -1), (30.4, 0, 15.5), TEAL_RAIL, h=1.0, collide=False)
    for z in (-36, 40):
        g.lamp(37.4, 0, z)


def wall(g, x0, z0, x1, z1, h=WALL_H, color=CONCRETE):
    """Muro do labirinto ao longo de uma linha da grade (de x0,z0 a x1,z1)."""
    t = WALL_T/2
    if abs(z1-z0) < 1e-6:
        g.bounds((min(x0, x1)-t, 0, z0-t), (max(x0, x1)+t, h, z0+t), color, PLASTER, top=CONCRETE_D)
    else:
        g.bounds((x0-t, 0, min(z0, z1)+t), (x0+t, h, max(z0, z1)-t), color, PLASTER, top=CONCRETE_D)


MAZE_WALLS = [
    # Corredor principal (escolta): (3,16) -> (3,7) -> (-9,7) -> (-9,-11) -> (9,-11) -> (9,-26)
    (0, 16, 0, 10), (6, 16, 6, 13), (6, 9.5, 6, 4),
    (-6, 4, -1, 4), (2.5, 4, 6, 4), (-12, 10, -6, 10), (-2.5, 10, 0, 10), (-12, 10, -12, 4),
    (-12, 4, -12, -4.5), (-12, -8, -12, -14), (-6, 4, -6, 1.5), (-6, -2, -6, -8),
    (-6, -8, 0, -8), (3.5, -8, 12, -8), (-12, -14, -3, -14), (.5, -14, 6, -14),
    (6, -14, 6, -17.5), (6, -21, 6, -26), (12, -8, 12, -10.5), (12, -14, 12, -26),
    (6, 4, 6, -.5), (6, -4, 6, -8),
    # Setor oeste.
    (-29.5, 4, -18, 4), (-24, -2, -24, -20), (-24, -14, -18, -14), (-18, 16, -18, 9.5), (-18, -20, -18, -26),
    # Setor leste.
    (12, 4, 24, 4), (18, -2, 18, -20), (24, -14, 29.5, -14), (24, 16, 24, 9.5), (18, 10, 18, 4),
]


def maze(g):
    """Labirinto do exame final (S01E09 14:30, 16:00): muros de concreto sobre grama, arbustos,
    fardos de feno, uma passagem em arco e o poste de alto-falante no meio."""
    g.zone('labirinto')
    x0, x1, z0, z1 = MAZE
    # Muro externo, com as entradas: sul (escolta e sudoeste), oeste, leste, norte (escolta e noroeste).
    for a, b in ((x0, -24), (-18, 0), (6, x1)):
        wall(g, a, z1, b, z1, OUTER_H, CONCRETE_D)
    for a, b in ((x0, -24), (-18, 6), (12, x1)):
        wall(g, a, z0, b, z0, OUTER_H, CONCRETE_D)
    for x in (x0, x1):
        wall(g, x, z1, x, -2, OUTER_H, CONCRETE_D)
        wall(g, x, -8, x, z0, OUTER_H, CONCRETE_D)
    for seg in MAZE_WALLS:
        wall(g, *seg)
    # Arbustos e feno nos cantos (nunca no meio dos corredores).
    for x, z in ((-27.5, 13.5), (-27.5, -23.5), (27.5, 13.5), (27.5, -23.5), (-20.5, -11), (21, 1), (-9, -23),
                 (15, -23), (-26.5, -8.6), (14.5, 7)):
        g.bush(x, 0, z, 1.0, collide=True)
    for x, z, ry in ((-21, 1.5, 0), (-19.8, 1.5, 0), (21.5, -17, 1.57), (15, 12.5, .2), (-3.5, -23.5, 0)):
        g.hay_bale(x, 0, z, ry)
    g.speaker_pole(0, 0, -2, 6.5)
    # Placas com setas (S01E09 16:00).
    for x, z, n in ((-6.27, -5, -1), (12.27, -18, 1), (-12.27, 7, -1)):
        g.box((x, 1.7, z), (.05, .3, .9), WHITE, collide=False)
        g.box((x+n*.03, 1.7, z), (.04, .08, .6), INK, collide=False)


INK = (40, 40, 46)


def north_plaza(g):
    """Patio da escola: biblioteca (edificio C, S01E09 05:12), caixa-d'agua e galpoes."""
    g.zone('patio_norte')
    # Escola / biblioteca (edificio C): portas sul e leste.
    x0, x1, z0, z1, h = -50, -26, -60, -40, 14
    g.block(x0, x1, z0, z1, h, wall=(238, 226, 204), faces=('south', 'east'), style='balcony', start_floor=1,
            accent=(196, 186, 168))
    g.door(-38, 0, z1, (0, 1), color=(110, 90, 70))
    g.door(x1, 0, -50, (1, 0), color=(110, 90, 70))
    oxygen_sign(g, -32.5, 4.6, z1, 1, along='x')
    g.box((-38, 6.6, z1+.15), (10, 1.2, .3), (110, 90, 70), collide=False)
    g.keep_clear((-43.5, 5.8, z1-.5), (-32.5, 7.4, z1+.5))
    # Arvores e bancos do patio.
    for x, z in ((-20, -30), (20, -30), (-20, -55), (20, -54)):
        g.tree(x, 0, z, 1.2)
        g.planter(x, 0, z+2.4, 2.2, .7)
    for x in (-10, 14):
        g.bench(x, 0, -30)
    # Caixa-d'agua e galpoes a nordeste.
    g.water_tower(36, 0, -44, 10, 3.2)
    g.block(40, X1, -60, -50, 6, wall=(222, 196, 160), faces=('west', 'south'), style='shutter',
            roof_color=(150, 150, 150))
    for x, z in ((33, -54), (34.5, -56.5)):
        g.crate(x, 0, z, 1.3, .3)
    g.lamp(-14, 0, -40)
    g.lamp(16, 0, -40)


def capsule_breach(g):
    """Capsula do timo rompida ao norte: cratera de tecido (entrada bacteriana), anteparos,
    andaime e o muro da capsula aberto ao meio."""
    g.zone('ferida')
    px0, px1, pz0, pz1 = PIT
    g.bounds((-8, PIT_FLOOR-1, pz0), (8, PIT_FLOOR, pz1), WOUND, TISSUE)
    for xs, xe in ((px0, -8), (8, px1)):
        lo, hi = (-8, px0) if xs < 0 else (8, px1)
        g.ramp((lo, PIT_FLOOR, -68), (hi, 0, -68), 7, SAND, DIRT, thick=.2)
        for z0_, z1_ in ((pz0, -71.5), (-64.5, pz1)):
            g.bounds((xs, -3, z0_), (xe, 0, z1_), (122, 84, 80), TISSUE, top=SAND, pats={'top': DIRT})
    rng = g.rng
    # Anteparos de destrocos que protegem a entrada.
    g.box((0, -1.0, -63.4), (8, 3.4, 1.4), (150, 120, 112), TISSUE, ry=.05)
    g.box((-5.5, -1.4, -65), (3.0, 2.4, 1.2), (150, 120, 112), TISSUE, ry=.5)
    g.box((5.5, -1.4, -65), (3.0, 2.4, 1.2), (150, 120, 112), TISSUE, ry=-.5)
    for _ in range(18):
        x, z = rng.uniform(-7, 7), rng.uniform(pz0+1, -68)
        g.sphere((x, PIT_FLOOR, z), rng.uniform(.4, 1.0), FLESH, TISSUE, seg=7, rings=4, squash=.6)
    for _ in range(18):
        x = rng.uniform(px0-3, px1+3)
        z = rng.uniform(-60, -58)
        s = rng.uniform(.5, 1.2)
        g.box((x, s*.3, z), (s*1.4, s*.6, s), CONCRETE_D, PLASTER, ry=rng.uniform(0, 3), collide=False)
    # Rede de reparo parcial e barreiras do lado da escola.
    g.face([(-8, .05, -60.5), (8, .05, -60.5), (8, -1.2, -63.0), (-8, -1.2, -63.0)], NET_C, NET, (0, 1, 0))
    for x in range(-12, 13, 3):
        g.barrier(x, 0, -58.5, 0, 2.6)
    for x in (-14, -9, 9, 14):
        g.cone(x, 0, -57)
    # Andaime a leste da cratera (nivel de cima) com escada para o sul.
    sx0, sx1, sz0, sz1 = 18, 30, -68, -58
    g.bounds((sx0, 3.8, sz0), (sx1, 4.1, sz1), WOOD, PLANK)
    for x in range(sx0, sx1+1, 3):
        for z in (sz0, sz1):
            g.cylinder((x, 0, z), .1, 6.2, SKY_BLUE, METAL, seg=6)
            g.collider((x-.12, 0, z-.12), (x+.12, 3.8, z+.12))
    for y in (2, 6):
        for z in (sz0, sz1):
            g.tube([(sx0, y, z), (sx1, y, z)], .07, SKY_BLUE, METAL, seg=5)
    g.railing((sx0, 4.1, sz0), (sx1, 4.1, sz0), SKY_BLUE)
    g.railing((sx1, 4.1, sz0), (sx1, 4.1, sz1), SKY_BLUE)
    g.railing((sx0, 4.1, sz0), (sx0, 4.1, sz1-3.2), SKY_BLUE)
    g.stairs((27, 0, -48.6), (27, 4.1, sz1), 2.6, WOOD, PLANK, side_color=(190, 140, 76))
    for x, z in ((21, -64), (24, -61.5)):
        g.crate(x, 4.1, z, .9, .2)
    # Muro da capsula (limite norte), aberto sobre a cratera e com o tecido aparecendo atras.
    for a, b in ((X0, -16), (16, X1)):
        g.bounds((a, -3, Z0-1.2), (b, 9, Z0), (214, 206, 190), ASHLAR, top=(196, 188, 172))
    for x0_, x1_ in ((-16, -9), (9, 16)):
        g.bounds((x0_, -3, Z0-1.2), (x1_, 4.5, Z0), (190, 150, 140), TISSUE, top=(170, 120, 112))
    g.bounds((-9, -3, Z0-6), (9, 1.5, Z0-1.2), (150, 90, 96), TISSUE, top=(160, 100, 104))
    for _ in range(10):
        g.sphere((rng.uniform(-8, 8), 1.2, Z0-rng.uniform(1.5, 5)), rng.uniform(.8, 1.6), FLESH, TISSUE, seg=7,
                 rings=4, squash=.7)


def boundary(g):
    g.zone('limites')
    H = 40
    g.collider((X0-1, -4, Z0), (X0, H, Z1))
    g.collider((X1, -4, Z0), (X1+1, H, Z1))
    g.collider((X0, -4, Z0-1), (X1, H, Z0))
    g.collider((X0, -4, Z1), (X1, H, Z1+1))


RING = 16


def perimeter(g):
    """Fora da area jogavel: floresta a oeste, predios da escola a leste, dormitorios ao sul e,
    ao norte, o tecido alem da capsula. A montanha listrada fica a noroeste, no horizonte."""
    g.zone('perimetro')
    rng = g.rng
    # Chao externo (abaixo do chao jogavel, sem z-fight).
    for lo, hi in (((X0-120, -3.2, Z0-160), (X0, -.05, Z1+120)), ((X1, -3.2, Z0-160), (X1+120, -.05, Z1+120)),
                   ((X0, -3.2, Z1), (X1, -.05, Z1+120)), ((X0, -3.2, Z0-160), (X1, -.05, Z0-1.2))):
        g.bounds(lo, hi, (150, 170, 120), LEAF, collide=False, skip=('bottom', 'south'))
    # Floresta a oeste (copas densas que fecham o horizonte).
    for z in range(int(Z0)-10, int(Z1)+10, 5):
        for k in range(3):
            x = X0-3-k*5+rng.uniform(-1.5, 1.5)
            g.tree(x, 0, z+rng.uniform(-2, 2), rng.uniform(1.5, 2.3))
    # Escola a leste e dormitorios ao sul (blocos fechados com fachadas).
    a = Z0-RING
    while a < Z1+RING-.1:
        b = min(Z1+RING, a+rng.uniform(12, 18))
        h = rng.uniform(14, 26)
        g.bounds((X1, -3, a), (X1+RING, h, b), rng.choice((DORM, CREAM, (226, 232, 230))), PLASTER, collide=False,
                 top=CREAM2, skip=('bottom',))
        g.solid((X1, -3, a), (X1+RING, h, b))
        g.facade(a, b, X1, -3, h+3, -1, 'z', style=rng.choice(('balcony', 'sill')), start_floor=2, laundry=False)
        a = b
    a = X0
    while a < X1-.1:
        b = min(X1, a+rng.uniform(12, 18))
        h = rng.uniform(16, 26)
        g.bounds((a, -3, Z1), (b, h, Z1+RING), DORM, PLASTER, collide=False, top=CREAM2, skip=('bottom',))
        g.solid((a, -3, Z1), (b, h, Z1+RING))
        g.facade(a, b, Z1, -3, h+3, -1, 'x', style='balcony', start_floor=2, laundry=True)
        a = b
    # Alem da capsula: tecido rosado e montanhas.
    for x in range(int(X0)-20, int(X1)+21, 9):
        g.sphere((x+rng.uniform(-3, 3), -2, Z0-12-rng.uniform(0, 8)), rng.uniform(6, 10), (206, 150, 150), TISSUE,
                 seg=9, rings=5, squash=.6)
    g.mountain(-78, -150, 62, 88)
    g.mountain(80, -200, 58, 58, base=(212, 184, 146))
    g.mountain(-175, -40, 48, 46, base=(196, 176, 136))


# ---------------------------------------------------------------------------
def markers(g):
    P = {}
    for i, x in enumerate((-4, 0, 4)):
        P[f'spawn_cells.{i}'] = (x, 0, 71)
        P[f'spawn_bacteria.{i}'] = (x, PIT_FLOOR, -72 if x else -74)
    escort = [(0, 0, 56), (3, 0, 50), (3, 0, 30), (3, 0, 16), (3, 0, 7), (-9, 0, 7), (-9, 0, -11), (9, 0, -11),
              (9, 0, -26), (9, 0, -34), (4, 0, -42), (0, 0, -50), (0, 0, -56)]
    for i, p in enumerate(escort):
        P[f'escort.{i:02}'] = p
    P['wound'] = (0, PIT_FLOOR, -68)
    P['recon'] = (-16, 0, 24)
    nodes = {
        'depot': (44, 0, 54), 'depot_out': (35, 0, 54), 'S': (26, 0, 53), 'G': (3, 0, 53), 'W': (-36, 0, 53),
        'F': (3, 0, 40), 'Fw': (-26, 0, 30), 'Fe': (26, 0, 32), 'Tw': (-36, 0, 30), 'A_e': (-40.5, 0, 26),
        'Ta': (-36, 0, 40), 'A_s': (-46, 0, 35.6), 'Tm': (-36, 0, -5), 'Tn': (-36, 0, -32),
        'Se': (34, 0, 47), 'E1': (34, 0, 34), 'B_s': (44, 0, 31.6), 'Eb': (34, 0, 20), 'B_w': (36.4, 0, 20),
        'E2': (34, 0, -5), 'E3': (34, 0, -34), 'N': (16, 0, -34), 'Nw': (-16, 0, -34),
        'C_s': (-38, 0, -38.4), 'C_e': (-24.4, 0, -50),
    }
    edges = [('depot', 'depot_out'), ('depot_out', 'S'), ('S', 'G'), ('G', 'W'), ('G', 'F'), ('F', 'Fw'),
             ('F', 'Fe'), ('Fw', 'Tw'), ('Tw', 'A_e'), ('W', 'Ta'), ('Ta', 'Tw'), ('Ta', 'A_s'), ('Tw', 'Tm'),
             ('Tm', 'Tn'), ('S', 'Se'), ('Se', 'E1'), ('Fe', 'E1'), ('E1', 'B_s'), ('E1', 'Eb'), ('Eb', 'B_w'),
             ('Eb', 'E2'), ('E2', 'E3'), ('E3', 'N'), ('N', 'Nw'), ('Nw', 'Tn'), ('Tn', 'C_s'), ('Nw', 'C_e')]
    for k, v in nodes.items():
        P[f'rbc.{k}'] = v
    hints = [(-21, 0, -20), (21, 0, -20), (21, 0, 10), (-21, 0, 10), (-46, 0, -28), (44, 0, 40), (34, 0, -18),
             (44, 0, -42), (-18, 0, -46), (20, 0, -48), (-22, 0, -68), (24, 0, -70), (24, 0, 21), (-25, 0, 42),
             (-44, 0, 52)]
    for i, h in enumerate(hints):
        P[f'colony.{i:02}'] = h
    return {
        'mode': 'escort',
        'points': P,
        'rbc_edges': edges,
        'destinations': {'A': ['A_e', 'A_s'], 'B': ['B_s', 'B_w'], 'C': ['C_s', 'C_e']},
        'cells_base': [-24, 60, 24, 78],
        'bounds': [X0, Z0, X1, Z1],
        'nav_ceilings': [9.0, 5.6, 2.9, .5, -1.4],
        'ambient_spots': [list(s) for s in getattr(g, 'spots', [])],
        'extra': {'wound_radius': 7.0, 'recon_light': 11.6, 'background': [236, 230, 210]},
    }
