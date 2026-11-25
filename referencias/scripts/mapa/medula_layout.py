"""Layout da Medula Ossea Vermelha (S01E06 - Eritroblastos e Mielocitos), em coordenadas do jogo.

x = leste, y = cima, z = sul. Base das celulas ao sul (+z), entrada bacteriana ao norte (-z).
Referencias em ``referencias/MedulaOssea/`` (README com o que cada quadro inspirou).

Modo ``training``: os eritroblastos saem do bercario (deposito) com caixinhas de O2 e fazem o
treino de entrega ate os postos de formatura A, B e C, passando pela cidade de papelao.

Zonas (sul -> norte):
  z  62..76  Alojamento dos mielocitos (base das celulas), duas saidas com anteparos
  z  30..58  Gramado: torre do relogio (reconhecimento), parquinho com casa na arvore
             e escorregador; bercario a oeste (de onde saem as criancas)
  z -30..30  Cidade de papelao do treino: piso rosa, divisorias pintadas com arvores, predios
             e setas vermelhas, carrinhos de caixas de O2
  z -46..-30 Praca norte
  z -78..-46 Corredor do vaso sanguineo (posto C) e a fratura do osso (entrada bacteriana)
A leste, a academia de tijolos com arcadas (posto B); a noroeste, o canal com ponte em arco e o
atelie (posto A).
"""
import math
from distrito_geo import *  # noqa: F401,F403

X0, X1, Z0, Z1 = -50, 50, -78, 76
TOWN = (-26, 30, -30, 30)
PIT = (4, 28, -76, -60)
PIT_FLOOR = -2.5
CANAL = (-50, -36, -24, -19)   # x0, x1, z0, z1
CANAL_FLOOR, CANAL_WATER = -1.2, -.9

BRICK_M = (176, 106, 96)       # tijolo arroxeado da academia (S01E06 02:12)
BRICK_M2 = (150, 88, 84)
ROOF_M = (130, 60, 66)
CREAM_M = (238, 226, 206)
LAWN = (128, 186, 96)
PINK_FLOOR = (238, 186, 204)
CARD = (236, 224, 150)         # papelao pintado
CARD_D = (206, 192, 120)
TREE_PAINT = (150, 200, 110)
ARROW = (214, 70, 70)
BONE = (236, 228, 206)
BONE_D = (206, 196, 172)
CART_GREEN = (86, 170, 90)
O2_BLUE = (120, 180, 224)

# Ruas da cidade de papelao: centros das ruas norte-sul (x) e leste-oeste (z), largura 5 m.
STREETS_X = (-23.5, -4.5, 14.5)
STREETS_Z = (27.5, 6.5, -13.5)
BLOCKS_X = ((-21, -7), (-2, 12), (17, 30))
BLOCKS_Z = ((9, 25), (-11, 4), (-30, -16))


def build(g, only=None):
    sections = [ground, barracks, lawn, nursery, cardboard_town, academy, canal_plaza, north_plaza, fracture,
                boundary, perimeter]
    for fn in sections:
        if only and fn.__name__ not in only:
            continue
        fn(g)
    g.flush_facades()
    g.flush_overlays()
    return markers(g)


# ---------------------------------------------------------------------------
def post_sign(g, x, y, z, n, along='z', label_color=ARROW):
    """Placa de posto de formatura: painel branco com a marca de O2."""
    if along == 'z':
        g.box((x+n*.1, y, z), (.1, 2.0, 4.4), WHITE, collide=False)
        g.box((x+n*.2, y, z), (.1, 1.2, 1.2), label_color, collide=False)
        g.box((x+n*.26, y, z), (.06, .5, .2), WHITE, collide=False)
        g.keep_clear((x-.4, y-1.2, z-2.5), (x+.4, y+1.2, z+2.5))
    else:
        g.box((x, y, z+n*.1), (4.4, 2.0, .1), WHITE, collide=False)
        g.box((x, y, z+n*.2), (1.2, 1.2, .1), label_color, collide=False)
        g.box((x, y, z+n*.26), (.2, .5, .06), WHITE, collide=False)
        g.keep_clear((x-2.5, y-1.2, z-.4), (x+2.5, y+1.2, z+.4))


def kid_cart(g, x, y, z, ry=0.0):
    """Carrinho de treino (S01E06 04:48): caixa de madeira com rodas verdes e a caixa azul de O2."""
    g.box((x, y+.45, z), (1.0, .5, .7), (196, 150, 96), PLANK, ry=ry)
    g.box((x, y+.95, z), (.7, .5, .6), O2_BLUE, collide=False, ry=ry)
    c, s = math.cos(ry), math.sin(ry)
    g.box((x+s*.31, y+.95, z+c*.31), (.3, .2, .02), WHITE, collide=False, ry=ry)
    for dx in (-.38, .38):
        for dz in (-.37, .37):
            wx, wz = x+dx*c+dz*s, z-dx*s+dz*c
            g.cylinder((wx, y, wz), .16, .04, CART_GREEN, seg=8, collide=False)
    g.box((x-c*.55, y+.9, z+s*.55), (.08, .9, .6), (196, 150, 96), PLANK, collide=False, ry=ry)


def ground(g):
    g.zone('chao')
    side = {'north': ASHLAR, 'south': ASHLAR, 'east': ASHLAR, 'west': ASHLAR, 'top': FLAGSTONE}
    px0, px1, pz0, pz1 = PIT
    cx0, cx1, cz0, cz1 = CANAL
    # Chao com dois buracos: a cratera da fratura e o canal.
    for lo, hi in (((X0, -3, pz1), (X1, 0, cz0)), ((X0, -3, cz1), (X1, 0, Z1)),
                   ((cx1, -3, cz0), (X1, 0, cz1)),
                   ((X0, -3, Z0), (X1, 0, pz0)), ((X0, -3, pz0), (px0, 0, pz1)), ((px1, -3, pz0), (X1, 0, pz1))):
        g.bounds(lo, hi, STONE, FLAGSTONE, top=PAVING, pats=side)
    g.overlay(-30, 30, 30, 58, LAWN, LEAF, 2)                       # gramado
    g.overlay(-3, 30, 3, 58, (226, 214, 196), FLAGSTONE, 3)         # caminho de pedras do gramado
    g.overlay(-30, 33.5, 30, 36.5, (226, 214, 196), FLAGSTONE, 3)   # caminho leste-oeste
    g.overlay(TOWN[0], TOWN[2], TOWN[1], TOWN[3], PINK_FLOOR, TILE, 4)  # piso rosa do treino
    g.overlay(X0, -19, -26, 30, (128, 176, 96), LEAF, 1)            # jardim oeste
    g.overlay(-32, -19, -26, 30, (222, 210, 190), FLAGSTONE, 3)     # alameda oeste
    g.overlay(30, -50, 34, 30, (214, 204, 190), FLAGSTONE, 3)       # alameda da arcada
    g.overlay(X0, -48, X1, -30, (230, 218, 200), FLAGSTONE, 2)      # praca norte


def barracks(g):
    """Alojamento dos mielocitos (neutrofilos jovens): base das celulas, de tijolo."""
    g.zone('base_celulas')
    x0, x1, z0, z1, h = -22, 22, 62, 76, 7
    doors = [(-16, -12), (12, 16)]
    xs = [x0]+[d for pair in doors for d in pair]+[x1]
    for i in range(0, len(xs), 2):
        g.bounds((xs[i], 0, z0), (xs[i+1], h, z0+1), BRICK_M, BRICK)
    for a, b in doors:
        g.bounds((a, 3.4, z0), (b, h, z0+1), BRICK_M, BRICK)
        g.box(((a+b)/2, 3.7, z0-.7), (b-a+1.2, .12, 1.6), ROOF_M, collide=False)
    for x in (x0, x1-1):
        g.bounds((x, 0, z0+1), (x+1, h, z1), BRICK_M, BRICK)
    g.bounds((x0+1, 0, z1-1), (x1-1, h, z1), BRICK_M, BRICK)
    g.bounds((x0, h, z0), (x1, 18, z1), BRICK_M, BRICK, top=ROOF_M, pats={'top': ROOF})
    g.solid((x0, 0, z0), (x1, 18, z1))
    g.facade(x0, x1, z0, h, 18-h, -1, 'x', style='sill', wall=BRICK_M, start_floor=0)
    g.box((0, 5.6, z0-.15), (16, 1.4, .3), WHITE, collide=False)
    g.box((0, 5.6, z0-.32), (1.0, .9, .1), (90, 150, 200), collide=False)
    g.keep_clear((-8, 4.6, z0-1), (8, 6.6, z0+.5))
    g.overlay(x0+1, z0+1, x1-1, z1-1, (206, 160, 104), PLANK, 6)
    for x in range(-18, 19, 4):
        g.box((x, 1.1, z1-1.5), (1.6, 2.2, .8), (220, 222, 226), METAL)
    for x in (-8, 8):
        g.bench(x, 0, 69)
        g.box((x, 3.5, 66), (.8, 7, .8), CREAM_M, PLASTER)
    for a, b in doors:
        cx = (a+b)/2
        g.bounds((cx-4, 0, 56.6), (cx+4, 3.0, 57.4), BRICK_M2, BRICK)
        g.planter(cx, 3.0, 57, 7.6, .7)
    g.block(X0, x0, 62, Z1, 18, wall=BRICK_M, pat=BRICK, roof_color=ROOF_M, faces=('north',), style='sill')
    g.block(x1, X1, 62, Z1, 18, wall=BRICK_M, pat=BRICK, roof_color=ROOF_M, faces=('north',), style='sill')


def lawn(g):
    """Gramado da academia (S01E06 02:12): torre do relogio, parquinho e arvores."""
    g.zone('gramado')
    # Torre do relogio (marco do mapa; o reconhecimento fica ao pe dela).
    tx, tz = -14, 47
    g.bounds((tx-3, 0, tz-3), (tx+3, 22, tz+3), BRICK_M, BRICK, top=BRICK_M2)
    g.solid((tx-3, 0, tz-3), (tx+3, 22, tz+3))
    for y in (6, 12, 18):
        g.box((tx, y, tz), (6.3, .3, 6.3), CREAM_M, collide=False)
    for nx, nz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        # Mostrador do relogio: placa clara com os ponteiros escuros (S01E06 02:12).
        cx, cz = tx+nx*3.0, tz+nz*3.0
        thin = lambda a, b: (a, b, .08) if nz else (.08, b, a)
        g.box((cx+nx*.05, 19.4, cz+nz*.05), thin(3.4, 3.4), (240, 226, 200), collide=False)
        g.box((cx+nx*.12, 19.4, cz+nz*.12), thin(2.6, 2.6), WHITE, collide=False)
        g.box((cx+nx*.18, 19.85, cz+nz*.18), thin(.14, 1.0), (60, 50, 50), collide=False)
        g.box((cx+nx*.2, 19.4, cz+nz*.2), thin(.8, .12), (60, 50, 50), collide=False)
    g.cylinder((tx, 22, tz), 4.4, 6.5, ROOF_M, ROOF, seg=4, r_top=.05, collide=False, smooth=False)
    g.lamp(tx+4.5, 0, tz-5.5)
    # Parquinho: casa na arvore (2,4 m) com escada ao sul e escorregador a leste.
    px, pz, py = 21, 44, 2.4
    g.bounds((px-2.5, py-.2, pz-2.5), (px+2.5, py, pz+2.5), (196, 150, 96), PLANK)
    for dx in (-2.2, 2.2):
        for dz in (-2.2, 2.2):
            g.cylinder((px+dx, 0, pz+dz), .16, py+2.6, (150, 110, 70), PLANK, seg=6, collide=False)
            g.collider((px+dx-.17, 0, pz+dz-.17), (px+dx+.17, py-.2, pz+dz+.17))
    for k in (-1, 1):
        g.face([(px-2.7, py+2.6, pz), (px+2.7, py+2.6, pz), (px+2.7, py+1.4, pz+k*2.9), (px-2.7, py+1.4, pz+k*2.9)],
               (190, 70, 70), ROOF, (0, 1, k))
    g.railing((px-2.5, py, pz-2.5), (px+2.5, py, pz-2.5), (150, 110, 70))
    g.railing((px-2.5, py, pz-2.5), (px-2.5, py, pz+2.5), (150, 110, 70))
    g.railing((px+2.5, py, pz-2.5), (px+2.5, py, pz+.5), (150, 110, 70))
    g.stairs((px-1, 0, pz+7.2), (px-1, py, pz+2.5), 1.8, (196, 150, 96), PLANK, side_color=(150, 110, 70))
    g.ramp((px+7.5, 0, pz+1.5), (px+2.5, py-.05, pz+1.5), 1.2, (226, 90, 80), PLAIN, thick=.15)
    # Arvores e bancos.
    for x, z in ((-27, 51), (-20, 55), (6, 54), (26, 54), (8, 40)):
        g.tree(x, 0, z, 1.2)
    for x in (-8, 10):
        g.bench(x, 0, 32.6, 0)
    for x, z in ((26, 33), (-6, 51)):
        kid_cart(g, x, 0, z, .4)


def nursery(g):
    """Bercario dos eritroblastos (deposito das criancas): tijolo, porta para o gramado."""
    g.zone('bercario')
    x0, x1, z0, z1, h = X0, -32, 30, 58, 9
    door = (41.5, 46.5)
    g.bounds((x0, 0, z0), (x1, h, z0+.6), BRICK_M, BRICK)
    g.bounds((x0, 0, z1-.6), (x1, h, z1), BRICK_M, BRICK)
    g.bounds((x1-.6, 0, z0+.6), (x1, h, door[0]), BRICK_M, BRICK)
    g.bounds((x1-.6, 0, door[1]), (x1, h, z1-.6), BRICK_M, BRICK)
    g.bounds((x1-.6, 3.6, door[0]), (x1, h, door[1]), BRICK_M, BRICK)
    g.bounds((x0, h, z0), (x1, h+.5, z1), BRICK_M2, BRICK, top=ROOF_M, pats={'top': ROOF})
    g.bounds((x0, h+.5, z0+4), (x1-4, h+6, z1-4), BRICK_M, BRICK, top=ROOF_M, pats={'top': ROOF}, collide=False)
    g.solid((x0, 0, z0), (x1, h+6, z1))
    g.facade(z0+4, z1-4, x1-4, h+.5, 5.5, 1, 'z', style='sill', wall=BRICK_M, start_floor=0)
    g.box((x1+.8, 3.9, 44), (1.6, .12, 6.2), ROOF_M, collide=False)
    post_sign(g, x1, 6.3, 44, 1, label_color=(240, 140, 160))
    g.overlay(x0, z0+.6, x1-.6, z1-.6, (240, 210, 216), TILE, 6)
    # Bercos e caixinhas de treino empilhadas.
    for z in (33, 36, 52, 55):
        for x in (-47, -43, -39):
            g.box((x, .45, z), (1.6, .9, 1.0), WHITE, collide=True)
            g.box((x, .95, z), (1.5, .1, .9), (250, 200, 210), collide=False)
    for x in (-46, -44.6):
        for k in range(3):
            g.box((x, .3+k*.6, 48.8), (.6, .6, .6), O2_BLUE, collide=k == 0)
    g.door(x1, 0, 36, (1, 0), color=(240, 140, 160))


def partition(g, x0, z0, x1, z1, h=2.3, low=False):
    """Divisoria de papelao pintada (S01E06 04:48, 04:54): arvores, predios desenhados e setas."""
    t = .16
    h = 1.15 if low else h
    if abs(z1-z0) < 1e-6:
        g.bounds((min(x0, x1), 0, z0-t/2), (max(x0, x1), h, z0+t/2), CARD, PLAIN, top=CARD_D)
        length, along = abs(x1-x0), 'x'
    else:
        g.bounds((x0-t/2, 0, min(z0, z1)), (x0+t/2, h, max(z0, z1)), CARD, PLAIN, top=CARD_D)
        length, along = abs(z1-z0), 'z'
    if low:
        return
    rng = random.Random(f'{x0}|{z0}|{x1}|{z1}')
    n = max(1, int(length/4.5))
    for i in range(n):
        a = (i+.5)/n
        cx, cz = x0+(x1-x0)*a, z0+(z1-z0)*a
        kind = rng.choice(('tree', 'tree', 'house', 'arrow'))
        for side in (-1, 1):
            off = t/2+.012
            def P(d, y):
                return (cx+d, y, cz+side*off) if along == 'x' else (cx+side*off, y, cz+d)
            nrm = (0, 0, side) if along == 'x' else (side, 0, 0)
            if kind == 'tree':
                g.face([P(-.12, .1), P(.12, .1), P(.12, .9), P(-.12, .9)], (150, 110, 70), PLAIN, nrm)
                pts = [P(math.cos(k*math.tau/10)*.65, 1.45+math.sin(k*math.tau/10)*.6) for k in range(10)]
                g.face(pts, TREE_PAINT, PLAIN, nrm)
            elif kind == 'house':
                g.face([P(-.8, .15), P(.8, .15), P(.8, 1.4), P(-.8, 1.4)], (196, 214, 150), PLAIN, nrm)
                g.face([P(-.95, 1.4), P(.95, 1.4), P(0, 2.05)], (170, 190, 120), PLAIN, nrm)
            else:
                d = side if along == 'x' else -side
                g.face([P(-.7*d, .95), P(.1*d, .95), P(.1*d, 1.25), P(-.7*d, 1.25)], ARROW, PLAIN, nrm)
                g.face([P(.1*d, .75), P(.75*d, 1.1), P(.1*d, 1.45)], ARROW, PLAIN, nrm)


def cardboard_town(g):
    """Cidade de papelao do treino de entrega: blocos de divisorias com portas, ruas de 5 m."""
    g.zone('cidade_papelao')
    x0, x1, z0, z1 = TOWN
    # Contorno, com as bocas das ruas abertas.
    for a, b in ((-21, -7), (-2, 12), (17, x1)):
        partition(g, a, z1, b, z1)
        partition(g, a, z0, b, z0)
    for a, b in ((9, z1), (-11, 4), (z0, -16)):
        partition(g, x0, a, x0, b)
    for a, b in ((9, 25), (-11, 4), (z0, -16)):
        partition(g, x1, a, x1, b)
    # Blocos: paredes nas bordas que dao para ruas internas, cada uma com uma porta de 3,5 m.
    for bi, (bx0, bx1) in enumerate(BLOCKS_X):
        for bj, (bz0, bz1) in enumerate(BLOCKS_Z):
            low = (bi, bj) in ((1, 1),)  # praca central com muretas (cobertura baixa)
            mx, mz = (bx0+bx1)/2, (bz0+bz1)/2
            edges = []
            if bz1 != z1:
                edges.append(('x', bz1, bx0, bx1))
            if bz0 != z0:
                edges.append(('x', bz0, bx0, bx1))
            if bx0 != x0:
                edges.append(('z', bx0, bz0, bz1))
            if bx1 != x1:
                edges.append(('z', bx1, bz0, bz1))
            for k, (axis, fixed, a, b) in enumerate(edges):
                gap = 3.5
                shift = ((bi*3+bj*5+k*2) % 3-1)*2.5
                c = (a+b)/2+shift
                for s0, s1 in ((a+.3, c-gap/2), (c+gap/2, b-.3)):
                    if s1-s0 < .6:
                        continue
                    if axis == 'x':
                        partition(g, s0, fixed, s1, fixed, low=low)
                    else:
                        partition(g, fixed, s0, fixed, s1, low=low)
            # Interior: carrinhos, caixas de O2 e uma divisoria baixa de cobertura.
            rng = random.Random(f'bloco{bi}{bj}')
            kid_cart(g, mx+rng.uniform(-3, 3), 0, mz+rng.uniform(-3, 3), rng.uniform(0, 3))
            if not low:
                if (bi+bj) % 2:
                    partition(g, mx-2.5, mz, mx+2.5, mz, low=True)
                else:
                    partition(g, mx, mz-2.5, mx, mz+2.5, low=True)
            else:
                for dx, dz in ((-3.5, -3), (3.5, 3)):
                    g.box((mx+dx, .3, mz+dz), (.6, .6, .6), O2_BLUE, collide=True)
    # Setas de chao nas ruas (adesivos vermelhos).
    for x in STREETS_X:
        for z in (17, -3):
            g.face([(x-.3, .05, z+1), (x+.3, .05, z+1), (x+.3, .05, z-.5), (x-.3, .05, z-.5)], ARROW, PLAIN, (0, 1, 0))
            g.face([(x-.8, .05, z-.5), (x+.8, .05, z-.5), (x, .05, z-1.6)], ARROW, PLAIN, (0, 1, 0))
    # Lampadas penduradas (como no salao do treino) nos cruzamentos.
    for x in STREETS_X:
        for z in STREETS_Z:
            g.lamp(x+1.9, 0, z+1.9, 3.4)


def academy(g):
    """Academia de tijolos (S01E06 02:12, 14:24, 15:06): galeria envidracada sobre uma arcada
    de pilares no terreo (corredor coberto ao longo do mapa). Posto de formatura B."""
    g.zone('academia')
    x0, x1, z0, z1, h = 34, X1, -44, 40, 16
    ax = 38  # fundo da arcada
    g.bounds((ax, 0, z0), (x1, h, z1), BRICK_M, BRICK, top=ROOF_M, pats={'top': ROOF})
    g.bounds((x0, 4.5, z0), (ax, h, z1), BRICK_M, BRICK, top=ROOF_M, pats={'top': ROOF})
    g.solid((x0, 0, z0), (x1, h, z1))
    for zc in range(z0+2, z1, 4):
        g.arch_wall((x0+.3, 0, zc), 4, 4.5, .6, 3.2, 3.6, 'z', BRICK_M, BRICK, intrados=BRICK_M2)
    g.bounds((x0-.1, 4.5, z0+.05), (x0+.6, 4.9, z1-.05), CREAM_M, collide=False)
    g.facade(z0, z1, x0, 4.5, h-4.5, -1, 'z', style='sill', wall=BRICK_M, start_floor=0, floor_h=3.4)
    g.overlay(x0, z0, ax, z1, (214, 196, 170), FLAGSTONE, 5)
    # Pontas da arcada fechadas.
    g.bounds((x0, 0, z0), (ax, 4.5, z0+.6), BRICK_M, BRICK)
    g.bounds((x0, 0, z1-.6), (ax, 4.5, z1), BRICK_M, BRICK)
    for z in range(z0+8, z1-2, 12):
        g.lamp(ax-.5, 0, z, 3.6)
    # Porta do posto B dentro da arcada e na face norte.
    g.door(ax, 0, -2, (-1, 0), color=(110, 70, 60))
    post_sign(g, ax, 3.4, 2.4, -1)
    g.door(42, 0, z0, (0, -1), color=(110, 70, 60))
    post_sign(g, 46.5, 3.6, z0, -1, along='x')
    for z in (-20, 16):
        g.bench(ax-.7, 0, z, math.pi/2)


def canal_plaza(g):
    """Canal com ponte de tijolo em arco (S01E06 01:48) e o atelie (posto de formatura A)."""
    g.zone('canal')
    cx0, cx1, cz0, cz1 = CANAL
    g.bounds((cx0, CANAL_FLOOR-1, cz0), (cx1, CANAL_FLOOR, cz1), STONE_D, ASHLAR, top=(184, 176, 156))
    g.face([(cx0-40, CANAL_WATER, cz0), (cx1, CANAL_WATER, cz0), (cx1, CANAL_WATER, cz1), (cx0-40, CANAL_WATER, cz1)],
           (170, 214, 160), WATER, (0, 1, 0))
    # Rampa de saida na ponta leste (quem cair no canal sai andando).
    g.ramp((cx1-5, CANAL_FLOOR, (cz0+cz1)/2), (cx1, 0, (cz0+cz1)/2), cz1-cz0, STONE, ASHLAR, thick=.1, sides=False)
    for z in (cz0, cz1):
        g.bounds((cx0, 0, z-.25 if z == cz0 else z), (cx1-5, .1, z if z == cz0 else z+.25), (238, 230, 212),
                 collide=False)
    # Ponte em arco com escadas (sobe 1,3 m).
    bx = -43
    g.bounds((bx-1.5, .75, cz0-.5), (bx+1.5, 1.0, cz1+.5), BRICK_C, BRICK)
    g.stairs((bx, 0, cz1+3.3), (bx, 1.0, cz1+.5), 3.0, BRICK_C, BRICK)
    g.stairs((bx, 0, cz0-3.3), (bx, 1.0, cz0-.5), 3.0, BRICK_C, BRICK)
    for sx in (bx-1.5, bx+1.5):
        g.railing((sx, 1.0, cz0-.5), (sx, 1.0, cz1+.5), IRON, ornate=True)
        g.arch_wall((sx, CANAL_FLOOR, (cz0+cz1)/2), cz1-cz0, 2.3, .2, 3.6, 1.9, 'z', BRICK_C, BRICK, collide=False)
    # Pilaretes ao longo das margens.
    for x in range(-49, -38, 3):
        if abs(x-bx) > 2.4:
            g.bollard(x, 0, cz1+.6)
            g.bollard(x, 0, cz0-.6)
    # Culvert na borda oeste.
    g.bounds((X0, CANAL_FLOOR, cz0-1), (X0+.3, 1.4, cz1+1), BRICK_D, BRICK, collide=False)
    # Atelie (posto A): portas leste e sul.
    ax0, ax1, az0, az1, h = X0, -40, -46, -30, 8
    g.block(ax0, ax1, az0, az1, h, wall=CREAM_M, faces=('east', 'south'), style='shutter', roof_color=ROOF_M)
    g.door(ax1, 0, -38, (1, 0), color=(240, 140, 160))
    g.door(-45, 0, az1, (0, 1), color=(240, 140, 160))
    post_sign(g, ax1, 4.4, -34.5, 1)
    # Jardim oeste (S01E06 13:54): arvores, canteiros e caminho de pedras.
    for x, z in ((-46, 24), (-40, 18), (-46, 8), (-40, -2), (-47, -10), (-36, 26)):
        g.tree(x, 0, z, 1.15)
    for x, z in ((-44, 13), (-38, 4)):
        g.planter(x, 0, z, 2.4, .8)
    g.lamp(-31.5, 0, 12)
    g.lamp(-31.5, 0, -8)


def north_plaza(g):
    """Praca norte e o corredor do vaso sanguineo (posto C: o portao com a placa 血管)."""
    g.zone('praca_norte')
    x0, x1, z0, z1, h = -26, -8, -66, -50, 10
    g.block(x0, x1, z0, z1, h, wall=(196, 176, 168), pat=BRICK, faces=('south', 'east'), style='shutter',
            roof_color=(110, 90, 96))
    # Portao grande (escuro) com a placa do vaso.
    g.box((-17, 2.2, z1+.06), (5.5, 4.4, .1), (60, 50, 56), PLANK, collide=False)
    g.box((-17, 5.2, z1+.1), (3.4, 1.1, .1), (110, 80, 60), collide=False)
    g.box((-17, 5.2, z1+.16), (2.6, .7, .04), (230, 214, 180), collide=False)
    g.keep_clear((-20.5, 0, z1-.5), (-13.5, 6, z1+.5))
    g.door(x1, 0, -57, (1, 0), color=(60, 50, 56))
    post_sign(g, x1, 4.2, -61.5, 1)
    for x, z in ((2, -42), (24, -38), (-24, -40)):
        g.tree(x, 0, z, 1.2)
    for x in (6, 18):
        g.bench(x, 0, -33, math.pi)
    g.lamp(-1, 0, -46)
    g.lamp(32.6, 0, -32)
    kid_cart(g, 30, 0, -52, 1.2)


def fracture(g):
    """Fratura no osso (entrada bacteriana): cratera de tecido com anteparos, sob a parede de osso."""
    g.zone('fratura')
    px0, px1, pz0, pz1 = PIT
    mx = (px0+px1)/2
    g.bounds((mx-8, PIT_FLOOR-1, pz0), (mx+8, PIT_FLOOR, pz1), WOUND, TISSUE)
    for lo, hi in (((px0, mx-8), -1), ((mx+8, px1), 1)):
        a, b = lo
        top_x, low_x = (a, b) if hi < 0 else (b, a)
        g.ramp((low_x, PIT_FLOOR, -68), (top_x, 0, -68), 7, SAND, DIRT, thick=.2)
        for z0_, z1_ in ((pz0, -71.5), (-64.5, pz1)):
            g.bounds((a, -3, z0_), (b, 0, z1_), (122, 84, 80), TISSUE, top=SAND, pats={'top': DIRT})
    rng = g.rng
    g.box((mx, -1.0, -63.4), (8, 3.4, 1.4), BONE_D, PLASTER, ry=.05)
    g.box((mx-5.5, -1.4, -65), (3.0, 2.4, 1.2), BONE_D, PLASTER, ry=.5)
    g.box((mx+5.5, -1.4, -65), (3.0, 2.4, 1.2), BONE_D, PLASTER, ry=-.5)
    for _ in range(16):
        x, z = rng.uniform(mx-7, mx+7), rng.uniform(pz0+1, -68)
        g.sphere((x, PIT_FLOOR, z), rng.uniform(.4, 1.0), FLESH, TISSUE, seg=7, rings=4, squash=.6)
    for _ in range(14):
        x, z = rng.uniform(px0-2, px1+2), rng.uniform(-60, -58)
        s = rng.uniform(.5, 1.2)
        g.box((x, s*.3, z), (s*1.4, s*.6, s), BONE_D, PLASTER, ry=rng.uniform(0, 3), collide=False)
    g.face([(mx-8, .05, -60.5), (mx+8, .05, -60.5), (mx+8, -1.2, -63.0), (mx-8, -1.2, -63.0)], NET_C, NET, (0, 1, 0))
    for x in range(int(mx)-12, int(mx)+13, 3):
        g.barrier(x, 0, -58.5, 0, 2.6)
    # Parede de osso compacto (limite norte), rachada sobre a cratera.
    for a, b in ((X0-RING, px0-1), (px1+1, X1+RING)):
        g.bounds((a, -3, Z0-1.5), (b, 12, Z0), BONE, PLASTER, top=BONE_D)
    for x0_, x1_ in ((px0-1, mx-6), (mx+6, px1+1)):
        g.bounds((x0_, -3, Z0-1.5), (x1_, 6, Z0), BONE_D, PLASTER, top=(196, 150, 140))
    g.bounds((mx-6, -3, Z0-7), (mx+6, 1.5, Z0-1.5), (150, 90, 96), TISSUE, top=(160, 100, 104))
    for _ in range(9):
        g.sphere((rng.uniform(mx-6, mx+6), 1.2, Z0-rng.uniform(2, 6)), rng.uniform(.8, 1.6), FLESH, TISSUE, seg=7,
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
    """Fora da area jogavel: predios de tijolo da medula e, ao fundo, as trabeculas do osso."""
    g.zone('perimetro')
    rng = g.rng
    for lo, hi in (((X0-120, -3.2, Z0-160), (X0, -.05, Z1+120)), ((X1, -3.2, Z0-160), (X1+120, -.05, Z1+120)),
                   ((X0, -3.2, Z1), (X1, -.05, Z1+120)), ((X0, -3.2, Z0-160), (X1, -.05, Z0-1.5))):
        g.bounds(lo, hi, (214, 196, 180), FLAGSTONE, collide=False, skip=('bottom', 'north', 'south', 'east', 'west'))
    # Fileira de predios de tijolo a oeste, leste e sul.
    for side in ('west', 'east', 'south'):
        if side == 'south':
            a, end = X0, X1
        else:
            a, end = Z0, Z1+RING
        while a < end-.1:
            b = min(end, a+rng.uniform(12, 18))
            h = rng.uniform(16, 30)
            wall = rng.choice((BRICK_M, BRICK_M2, (196, 132, 116), CREAM_M))
            if side == 'west':
                lo, hi, fx = (X0-RING, -3, a), (X0, h, b), ('z', a, b, X0, 1)
            elif side == 'east':
                lo, hi, fx = (X1, -3, a), (X1+RING, h, b), ('z', a, b, X1, -1)
            else:
                lo, hi, fx = (a, -3, Z1), (b, h, Z1+RING), ('x', a, b, Z1, -1)
            g.bounds(lo, hi, wall, BRICK if wall != CREAM_M else PLASTER, collide=False, top=ROOF_M,
                     skip=('bottom',))
            g.solid(lo, hi)
            g.facade(fx[1], fx[2], fx[3], -3, h+3, fx[4], fx[0], style=rng.choice(('sill', 'shutter')), start_floor=2,
                     laundry=False, wall=wall)
            a = b
    # Alem do osso: trabeculas gigantes (arcos de osso esponjoso) fechando o horizonte ao norte.
    for k in range(7):
        cx = -150+k*50+rng.uniform(-10, 10)
        cz = Z0-60-rng.uniform(0, 50)
        span, rise = rng.uniform(50, 80), rng.uniform(35, 60)
        along = 'x' if k % 2 else 'z'
        pts = g.arch_points((cx, -3, cz), span, rise, along, steps=14)
        g.tube(pts, rng.uniform(3.5, 5.5), BONE if k % 2 else BONE_D, PLASTER, seg=10)


# ---------------------------------------------------------------------------
def markers(g):
    P = {}
    for i, x in enumerate((-4, 0, 4)):
        P[f'spawn_cells.{i}'] = (x, 0, 70)
        P[f'spawn_bacteria.{i}'] = (16+x, PIT_FLOOR, -72 if x else -74)
    # Sem escolta neste modo: os dois pontos so marcam a borda da fratura (rede ao selar).
    P['escort.00'] = (16, 0, -52)
    P['escort.01'] = (16, 0, -56.5)
    P['wound'] = (16, PIT_FLOOR, -68)
    P['recon'] = (-14, 0, 41.5)
    a, b, c = STREETS_X
    r1, r2, r3 = STREETS_Z
    nodes = {
        'depot': (-41, 0, 44), 'depot_out': (-29, 0, 44),
        'La': (a, 0, 34.5), 'Lb': (b, 0, 35.5), 'Lc': (c, 0, 34.5),
        'Ta1': (a, 0, r1), 'Tb1': (b, 0, r1), 'Tc1': (c, 0, r1),
        'Ta2': (a, 0, r2), 'Tb2': (b, 0, r2), 'Tc2': (c, 0, r2),
        'Ta3': (a, 0, r3), 'Tb3': (b, 0, r3), 'Tc3': (c, 0, r3),
        'W1': (-29, 0, 24), 'W2': (-29, 0, r3), 'W3': (-29, 0, -29), 'A_s': (-45, 0, -29),
        'Nw': (-29, 0, -38), 'A_e': (-38.4, 0, -38),
        'E1': (31.2, 0, r2), 'E2': (31.2, 0, -2), 'B_a': (36.5, 0, -2), 'E3': (31.2, 0, -46.5), 'B_n': (42, 0, -46.5),
        'N0': (b, 0, -36), 'Nc': (c, 0, -36), 'C_s': (-17, 0, -48.6), 'C_e': (-6.6, 0, -57),
    }
    edges = [('depot', 'depot_out'), ('depot_out', 'La'), ('La', 'Lb'), ('Lb', 'Lc'), ('La', 'Ta1'), ('Lb', 'Tb1'),
             ('Lc', 'Tc1'), ('Ta1', 'Tb1'), ('Tb1', 'Tc1'), ('Ta2', 'Tb2'), ('Tb2', 'Tc2'), ('Ta3', 'Tb3'),
             ('Tb3', 'Tc3'), ('Ta1', 'Ta2'), ('Ta2', 'Ta3'), ('Tb1', 'Tb2'), ('Tb2', 'Tb3'), ('Tc1', 'Tc2'),
             ('Tc2', 'Tc3'), ('depot_out', 'W1'), ('W1', 'W2'), ('W2', 'Ta3'), ('W2', 'W3'), ('W3', 'A_s'),
             ('W3', 'Nw'), ('Nw', 'A_e'), ('Tc2', 'E1'), ('E1', 'E2'), ('E2', 'B_a'), ('E2', 'E3'), ('E3', 'B_n'),
             ('Tb3', 'N0'), ('Tc3', 'Nc'), ('N0', 'Nc'), ('Nc', 'E3'), ('N0', 'C_s'), ('N0', 'C_e'), ('N0', 'Nw')]
    for k, v in nodes.items():
        P[f'rbc.{k}'] = v
    hints = [(-14, 0, 13), (5, 0, 21), (24, 0, 13), (-14, 0, -7), (24, 0, -7), (1, 0, -27), (-18, 0, -27),
             (-40, 0, 10), (-44, 0, -6), (36, 0, 20), (36, 0, -30), (14, 0, 52), (-4, 0, -56), (38, 0, -56),
             (-36, 0, -44)]
    for i, h in enumerate(hints):
        P[f'colony.{i:02}'] = h
    return {
        'mode': 'training',
        'points': P,
        'rbc_edges': edges,
        'destinations': {'A': ['A_s', 'A_e'], 'B': ['B_a', 'B_n'], 'C': ['C_s', 'C_e']},
        'cells_base': [-24, 58, 24, 78],
        'bounds': [X0, Z0, X1, Z1],
        'nav_ceilings': [9.0, 5.6, 2.9, .5, -1.4],
        'canal': [CANAL[2], CANAL[3], CANAL_FLOOR],
        'ambient_spots': [list(s) for s in getattr(g, 'spots', [])],
        'extra': {'wound_radius': 7.0, 'recon_light': 26.0, 'background': [240, 226, 214]},
    }
