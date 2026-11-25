"""Layout do Coracao (S01E08 - Circulacao Sanguinea), em coordenadas do jogo.

x = leste, y = cima, z = sul. Base das celulas ao sul (+z), entrada bacteriana ao norte (-z).
Referencias em ``referencias/Coracao/`` (README com o que cada quadro inspirou).

Modo ``convoy``: o comboio de hemacias leva CO2 da veia cava ate o pulmao, pelo caminho do
episodio. Duas valvas (portoes) abrem e fecham no ritmo do batimento (``heart.py``):
a tricuspide (entre o atrio e o tunel de torii) e a pulmonar (saida do ventriculo).

Zonas (sul -> norte):
  z  60..74  Estacao da veia cava (base das celulas)
  z  34..58  Avenida da veia cava: placa com o mapa do coracao, deposito das hemacias a leste
  z  -1..34  Patio do atrio direito: torii de entrada, lanternas de pedra e o templo (o comboio
             atravessa o salao, cheio de lanternas)
  z  -3..-1  Paredao de rocha com a VALVA TRICUSPIDE (portao com dois guardioes) e uma fenda
  z -31..-3  Tunel de torii com tapete vermelho; fora dele, jardim de musgo (O) e servico (L)
  z -51..-31 Salao do ventriculo direito: teto listrado, lanternas, mezaninos; VALVA PULMONAR
  z -64..-51 Arteria pulmonar: corredor branco abobadado ("siga em frente")
  z -86..-68 Estacao de troca do pulmao (galpao de trelicas com cilindros de O2) e, a leste, a
             lesao do endocardio (entrada bacteriana)
Corredores laterais (x ~ +-30) contornam as valvas: so o comboio depende delas.
"""
import math
from distrito_geo import *  # noqa: F401,F403

X0, X1, Z0, Z1 = -50, 50, -86, 74
PIT = (24, 44, -84, -68)
PIT_FLOOR = -2.5

TEMPLE = (-14, 14, 6, 22)
HALL = (-24, 24, -51, -31)      # salao do ventriculo (paredes incluidas)
SHED = (-20, 20, -86, -68)      # galpao do pulmao
VALVE_T = (0, 0, -2)            # tricuspide (no paredao de rocha)
VALVE_P = (0, 0, -50.5)         # pulmonar (parede norte do salao)

PLASTER_W = (242, 236, 222)
TIMBER = (196, 52, 46)          # madeira laqueada vermelha
TIMBER_D = (150, 40, 38)
ROOF_GREY = (150, 152, 148)
ROOF_GREY_D = (118, 120, 118)
ROCK = (112, 108, 92)
ROCK_D = (84, 82, 70)
MOSS = (110, 140, 84)
CARPET = (184, 36, 40)
LANTERN = (250, 214, 140)
STEEL = (150, 160, 182)
STEEL_D = (104, 114, 140)
O2_TANK = (52, 52, 58)


def build(g, only=None):
    sections = [ground, station, avenue, atrium, temple, septum, torii_tunnel, flanks, ventricle, artery,
                lung_station, lesion, boundary, perimeter]
    for fn in sections:
        if only and fn.__name__ not in only:
            continue
        fn(g)
    g.flush_facades()
    g.flush_overlays()
    return markers(g)


# -- pecas -------------------------------------------------------------------
def oxygen_sign(g, x, y, z, n, along='z'):
    if along == 'z':
        g.box((x+n*.1, y, z), (.1, 2.0, 4.4), WHITE, collide=False)
        g.box((x+n*.2, y, z), (.1, 1.2, 1.2), RED_ARCH, collide=False)
        g.keep_clear((x-.4, y-1.2, z-2.5), (x+.4, y+1.2, z+2.5))
    else:
        g.box((x, y, z+n*.1), (4.4, 2.0, .1), WHITE, collide=False)
        g.box((x, y, z+n*.2), (1.2, 1.2, .1), RED_ARCH, collide=False)
        g.keep_clear((x-2.5, y-1.2, z-.4), (x+2.5, y+1.2, z+.4))


def disc(g, cx, cy, cz, r, color, normal, seg=20, pat=PLAIN):
    """Disco vertical (emblema, mostrador) virado para ``normal`` (eixo x ou z)."""
    nx, _, nz = normal
    pts = []
    for k in range(seg):
        a = k*math.tau/seg
        d, y = math.cos(a)*r, math.sin(a)*r
        pts.append((cx+d, cy+y, cz) if nz else (cx, cy+y, cz+d))
    g.face(pts, color, pat, normal)


def tomoe(g, cx, cy, cz, r, normal):
    """Emblema circular branco com o redemoinho escuro (simbolo do templo do atrio)."""
    nx, _, nz = normal
    disc(g, cx, cy, cz, r, WHITE, normal)
    off = .02
    for k in range(3):
        a = k*math.tau/3
        px, py = math.cos(a)*r*.45, math.sin(a)*r*.45
        pts = [(math.cos(a+b*math.tau/10)*r*.2+px, math.sin(a+b*math.tau/10)*r*.2+py) for b in range(10)]
        g.face([(cx+d+nx*off, cy+y, cz+nz*off) if nz else (cx+nx*off, cy+y, cz+d) for d, y in pts],
               (40, 36, 40), PLAIN, normal)


def stone_lantern(g, x, z, h=2.2):
    """Lanterna de pedra (toro) com a luz acesa (S01E08 10:16)."""
    g.cylinder((x, 0, z), .35, .3, STONE_D, ASHLAR, seg=8)
    g.cylinder((x, .3, z), .14, h*.45, STONE, ASHLAR, seg=8)
    g.box((x, h*.6, z), (.8, .12, .8), STONE_D, ASHLAR, collide=False)
    g.box((x, h*.72, z), (.5, .4, .5), LANTERN, GLOW, collide=False)
    g.cylinder((x, h*.82, z), .55, .35, STONE_D, ASHLAR, seg=6, r_top=.05, collide=False)
    g.collider((x-.35, 0, z-.35), (x+.35, h, z+.35))


def hanging_lantern(g, x, y, z, r=.4, color=LANTERN):
    g.tube([(x, y+r+1.2, z), (x, y+r, z)], .02, IRON, seg=4, caps=False)
    g.cylinder((x, y-r, z), r, r*2, color, GLOW, seg=10, collide=False)
    g.cylinder((x, y+r, z), r*.6, .12, (40, 36, 40), seg=10, collide=False)
    g.cylinder((x, y-r-.12, z), r*.6, .12, (40, 36, 40), seg=10, collide=False)


def hip_roof(g, x0, x1, z0, z1, y, h, over, color, pat=ROOF):
    """Telhado de quatro aguas com beiral (``over`` m) e cumeeira ao longo do lado maior."""
    a0, a1, b0, b1 = x0-over, x1+over, z0-over, z1+over
    if (a1-a0) >= (b1-b0):
        inset = (b1-b0)/2
        r0, r1 = (a0+inset, y+h, (b0+b1)/2), (a1-inset, y+h, (b0+b1)/2)
        g.face([(a0, y, b1), (a1, y, b1), r1, r0], color, pat, (0, 1, 1))
        g.face([(a0, y, b0), (a1, y, b0), r1, r0], color, pat, (0, 1, -1))
        g.face([(a0, y, b0), (a0, y, b1), r0], color, pat, (-1, 1, 0))
        g.face([(a1, y, b0), (a1, y, b1), r1], color, pat, (1, 1, 0))
    else:
        inset = (a1-a0)/2
        r0, r1 = ((a0+a1)/2, y+h, b0+inset), ((a0+a1)/2, y+h, b1-inset)
        g.face([(a1, y, b0), (a1, y, b1), r1, r0], color, pat, (1, 1, 0))
        g.face([(a0, y, b0), (a0, y, b1), r1, r0], color, pat, (-1, 1, 0))
        g.face([(a0, y, b0), (a1, y, b0), r0], color, pat, (0, 1, -1))
        g.face([(a0, y, b1), (a1, y, b1), r1], color, pat, (0, 1, 1))
    g.face([(a0, y-.01, b0), (a1, y-.01, b0), (a1, y-.01, b1), (a0, y-.01, b1)], TIMBER_D, PLANK, (0, -1, 0))


def shrine_block(g, x0, x1, z0, z1, h, faces=('north', 'south', 'east', 'west'), roof=True):
    """Construcao do complexo do templo: reboco branco, esteios vermelhos e telhado cinza."""
    g.bounds((x0, 0, z0), (x1, h, z1), PLASTER_W, PLASTER, top=ROOF_GREY)
    g.solid((x0, 0, z0), (x1, h+3, z1))
    for f in faces:
        if f in ('north', 'south'):
            z = z0-.08 if f == 'north' else z1+.08
            for x in [x0+.2+k*2.4 for k in range(int((x1-x0-.4)/2.4)+1)]:
                g.box((x, h/2, z), (.28, h, .16), TIMBER, PLANK, collide=False)
            g.box(((x0+x1)/2, h*.55, z), (x1-x0+.1, .2, .2), TIMBER, PLANK, collide=False)
        else:
            x = x0-.08 if f == 'west' else x1+.08
            for z in [z0+.2+k*2.4 for k in range(int((z1-z0-.4)/2.4)+1)]:
                g.box((x, h/2, z), (.16, h, .28), TIMBER, PLANK, collide=False)
            g.box((x, h*.55, (z0+z1)/2), (.2, .2, z1-z0+.1), TIMBER, PLANK, collide=False)
    if roof:
        hip_roof(g, x0, x1, z0, z1, h, min(x1-x0, z1-z0)*.28, 1.0, ROOF_GREY)


def rock(g, x0, z0, x1, z1, h, y0=0.0, seed=None, collide=True):
    """Massa de rocha (paredes do tunel e do paredao): bloco com calombos de pedra e musgo."""
    g.bounds((x0, y0, z0), (x1, y0+h, z1), ROCK, FLAGSTONE, top=MOSS, pats={'top': LEAF}, collide=collide)
    rng = random.Random(seed or f'{x0}|{z0}|{x1}|{z1}')
    n = int((x1-x0)*(z1-z0)/14)+2
    for _ in range(n):
        x, z = rng.uniform(x0+.5, x1-.5), rng.uniform(z0+.5, z1-.5)
        r = rng.uniform(.8, 1.6)
        g.sphere((x, y0+h+r*.2, z), r, ROCK_D if rng.random() < .5 else MOSS, FLAGSTONE, seg=7, rings=4, squash=.6)


def nio(g, x, z, facing, color=(176, 120, 70)):
    """Guardiao do portao (nio, S01E08): figura de bronze estilizada sobre um pedestal."""
    g.bounds((x-1.1, 0, z-1.1), (x+1.1, 1.0, z+1.1), STONE_D, ASHLAR)
    y = 1.0
    g.box((x, y+1.0, z), (1.1, 2.0, .8), color, collide=False)          # pernas/quadril
    g.box((x, y+2.6, z), (1.6, 1.4, 1.0), color, collide=False)         # tronco
    g.sphere((x, y+3.7, z), .45, color, seg=8, rings=5)                 # cabeca
    g.box((x, y+4.15, z), (.25, .3, .25), (60, 50, 40), collide=False)  # coque
    for s in (-1, 1):
        g.box((x+s*1.0, y+2.5, z+facing*.3), (.45, 1.5, .45), color, collide=False, ry=s*.3)
    g.box((x, y+.3, z+facing*.5), (1.6, .6, .3), TIMBER, collide=False)  # faixa
    g.cylinder((x+.9, y+.1, z+facing*.6), .08, 3.6, (90, 60, 40), seg=6, collide=False)  # bastao
    g.collider((x-.9, y, z-.6), (x+.9, y+4.2, z+.6))


# -- zonas -------------------------------------------------------------------
def ground(g):
    g.zone('chao')
    side = {'north': ASHLAR, 'south': ASHLAR, 'east': ASHLAR, 'west': ASHLAR, 'top': FLAGSTONE}
    px0, px1, pz0, pz1 = PIT
    for lo, hi in (((X0, -3, pz1), (X1, 0, Z1)), ((X0, -3, Z0), (px0, 0, pz1)), ((px1, -3, Z0), (X1, 0, pz1)),
                   ((px0, -3, Z0), (px1, 0, pz0))):
        g.bounds(lo, hi, STONE, FLAGSTONE, top=PAVING, pats=side)
    g.overlay(X0, 34, X1, 59, (226, 214, 198), FLAGSTONE, 2)        # avenida
    g.overlay(-30, -1, 30, 34, (210, 186, 140), DIRT, 2)            # patio de terra do atrio
    g.overlay(-2.5, -1, 2.5, 34, (222, 210, 188), FLAGSTONE, 3)     # caminho de pedras ate o templo
    g.overlay(-24, -31, -6, -3, MOSS, LEAF, 3)                      # jardim de musgo
    g.overlay(-1.6, -31, 1.6, -3, CARPET, PLAIN, 5)                 # tapete vermelho do tunel
    g.overlay(-34, -68, 34, -51, (214, 210, 204), FLAGSTONE, 2)     # praca da arteria
    g.overlay(-23.4, -50.4, 23.4, -31.6, (120, 66, 52), PLANK, 4)   # piso de madeira do ventriculo
    g.overlay(SHED[0], SHED[2], SHED[1], SHED[3], (196, 200, 210), TILE, 4)


def station(g):
    """Estacao da veia cava (base das celulas)."""
    g.zone('base_celulas')
    x0, x1, z0, z1, h = -22, 22, 60, 74, 8
    doors = [(-16, -12), (12, 16)]
    xs = [x0]+[d for pair in doors for d in pair]+[x1]
    for i in range(0, len(xs), 2):
        g.bounds((xs[i], 0, z0), (xs[i+1], h, z0+1), PLASTER_W, PLASTER)
    for a, b in doors:
        g.bounds((a, 3.4, z0), (b, h, z0+1), PLASTER_W, PLASTER)
        g.box(((a+b)/2, 3.7, z0-.7), (b-a+1.2, .12, 1.6), TIMBER, collide=False)
    for x in (x0, x1-1):
        g.bounds((x, 0, z0+1), (x+1, h, z1), PLASTER_W, PLASTER)
    g.bounds((x0+1, 0, z1-1), (x1-1, h, z1), PLASTER_W, PLASTER)
    g.bounds((x0, h, z0), (x1, h+.6, z1), CREAM2, PLASTER, top=ROOF_GREY, pats={'top': ROOF})
    g.solid((x0, 0, z0), (x1, h+.6, z1))
    for x in range(int(x0), int(x1)+1, 4):
        g.box((x, h/2, z0-.1), (.3, h, .2), TIMBER, PLANK, collide=False)
    g.box((0, 6.2, z0-.25), (14, 1.4, .2), WHITE, collide=False)
    g.box((0, 6.2, z0-.38), (1.0, 1.0, .08), RED_ARCH, collide=False)
    g.overlay(x0+1, z0+1, x1-1, z1-1, (226, 222, 214), TILE, 6)
    for x in range(-18, 19, 4):
        g.box((x, 1.1, z1-1.5), (1.6, 2.2, .8), (220, 222, 226), METAL)
    for x in (-8, 8):
        g.bench(x, 0, 68)
    for a, b in doors:
        cx = (a+b)/2
        g.bounds((cx-4, 0, 54.6), (cx+4, 3.0, 55.4), PLASTER_W, PLASTER)
        g.planter(cx, 3.0, 55, 7.6, .7)
    g.block(X0, x0, 60, Z1, 16, wall=PLASTER_W, faces=('north',), style='shutter', roof_color=ROOF_GREY)
    g.block(x1, X1, 60, Z1, 16, wall=PLASTER_W, faces=('north',), style='shutter', roof_color=ROOF_GREY)


def avenue(g):
    """Avenida da veia cava: placa com o mapa do coracao (S01E08 07:52), deposito das hemacias."""
    g.zone('avenida')
    # Placa-guia com o mapa do coracao.
    for x in (-23, -15):
        g.box((x, 1.8, 40), (.25, 3.6, .25), TIMBER_D, PLANK)
    g.box((-19, 2.7, 40), (8.4, 3.2, .2), (240, 232, 214), collide=False)
    g.face([(-21.4, 1.6, 39.88), (-19.2, 1.6, 39.88), (-18.8, 3.8, 39.88), (-21.8, 3.6, 39.88)], (200, 120, 190), PLAIN,
           (0, 0, -1))
    g.face([(-18.4, 1.6, 39.88), (-16.2, 1.6, 39.88), (-16.0, 3.7, 39.88), (-18.6, 3.9, 39.88)], (232, 120, 130), PLAIN,
           (0, 0, -1))
    g.box((-19, 4.45, 40), (8.8, .3, .4), ROOF_GREY, ROOF, collide=False)
    # Deposito das hemacias (leste): porta voltada para oeste.
    sx0, sx1, sz0, sz1, h = 34, X1, 40, 57, 7
    g.bounds((sx0, 0, sz0), (sx1, h, sz0+.6), PLASTER_W, PLASTER)
    g.bounds((sx0, 0, sz1-.6), (sx1, h, sz1), PLASTER_W, PLASTER)
    g.bounds((sx1-.6, 0, sz0+.6), (sx1, h, sz1-.6), PLASTER_W, PLASTER)
    g.bounds((sx0, 0, sz0+.6), (sx0+.6, h, 45.5), PLASTER_W, PLASTER)
    g.bounds((sx0, 0, 50.5), (sx0+.6, h, sz1-.6), PLASTER_W, PLASTER)
    g.bounds((sx0, 3.6, 45.5), (sx0+.6, h, 50.5), PLASTER_W, PLASTER)
    hip_roof(g, sx0, sx1, sz0, sz1, h, 4, .8, ROOF_GREY)
    g.solid((sx0, 0, sz0), (sx1, h+4, sz1))
    g.box((sx0-.7, 3.9, 48), (1.6, .12, 6.2), TIMBER, collide=False)
    oxygen_sign(g, sx0, 5.0, 48, -1)
    g.overlay(sx0+.6, sz0+.6, sx1-.6, sz1-.6, (226, 222, 214), TILE, 6)
    for z in (41.6, 55.4):
        for x in range(37, 49, 2):
            g.box((x, .3, z), (.8, .6, .6), (206, 168, 116), collide=True)
            g.box((x, .9, z), (.8, .6, .6), (206, 168, 116), collide=False)
    # Bloco a oeste da avenida.
    shrine_block(g, X0, -34, 38, 57, 9, faces=('east', 'north'))
    for x in (-8, 8):
        g.lamp(x, 0, 52)
    for x in (-30, 26):
        g.bench(x, 0, 57.6)


def atrium(g):
    """Patio do atrio direito (S01E08 10:00): grande torii de entrada, lanternas de pedra, arvores."""
    g.zone('patio_atrio')
    g.torii(0, 0, 33, w=9, h=6.5, along='x')
    for x in (-8, 8):
        for z in (28, 24.5):
            stone_lantern(g, x, z)
    for x, z in ((-19, 26), (19, 26), (-22, 10), (22, 10), (-18, 3), (18, 3)):
        g.tree(x, 0, z, 1.2)
    # Atrio A (oeste): edificio do complexo com portas leste e sul.
    shrine_block(g, X0, -34, 8, 30, 8, faces=('east', 'south'))
    g.door(-34, 0, 18, (1, 0), color=TIMBER)
    g.door(-42, 0, 30, (0, 1), color=TIMBER)
    oxygen_sign(g, -34, 5.2, 24, 1)
    # Bloco leste do patio.
    shrine_block(g, 34, X1, 6, 32, 9, faces=('west', 'south'))


def temple(g):
    """Templo do atrio direito: o comboio atravessa o salao (portas sul e norte). Dentro, pilares e
    lanternas como na sala do santuario (S01E08 11:00)."""
    g.zone('templo')
    x0, x1, z0, z1 = TEMPLE
    h, t = 7.0, .6
    # Paredes com portas (sul/norte no eixo do comboio, laterais menores).
    for zz, zi in ((z1-t, z1), (z0, z0+t)):
        g.bounds((x0, 0, zz), (-3, h, zi), PLASTER_W, PLASTER)
        g.bounds((3, 0, zz), (x1, h, zi), PLASTER_W, PLASTER)
        g.bounds((-3, 4.6, zz), (3, h, zi), PLASTER_W, PLASTER)
    for xx, xi in ((x0, x0+t), (x1-t, x1)):
        g.bounds((xx, 0, z0+t), (xi, h, 12.5), PLASTER_W, PLASTER)
        g.bounds((xx, 0, 15.5), (xi, h, z1-t), PLASTER_W, PLASTER)
        g.bounds((xx, 3.2, 12.5), (xi, h, 15.5), PLASTER_W, PLASTER)
    g.bounds((x0, h, z0), (x1, h+.4, z1), TIMBER_D, PLANK, top=ROOF_GREY)
    g.solid((x0, 0, z0), (x1, h+.4, z1))
    # Esteios vermelhos e trelicas (fora).
    for z in (z0-.12, z1+.12):
        for x in [x0+.15+k*2.0 for k in range(15)]:
            if -3.2 < x < 3.2:
                continue
            g.box((x, h/2, z), (.3, h, .24), TIMBER, PLANK, collide=False)
        g.box((0, 5.6, z), (x1-x0+.4, .22, .26), TIMBER, PLANK, collide=False)
        for a, b in ((x0-.2, -3.2), (3.2, x1+.2)):
            g.box(((a+b)/2, 2.6, z), (b-a, .22, .26), TIMBER, PLANK, collide=False)
    for x in (x0-.12, x1+.12):
        for z in [z0+.15+k*2.0 for k in range(9)]:
            if 12.3 < z < 15.7:
                continue
            g.box((x, h/2, z), (.24, h, .3), TIMBER, PLANK, collide=False)
    # Telhado em dois andares e o emblema circular sobre a porta.
    hip_roof(g, x0, x1, z0, z1, h+.4, 2.4, 2.4, ROOF_GREY)
    g.bounds((-9, h+2.8, 9), (9, h+6.0, 19), PLASTER_W, PLASTER, collide=False, top=ROOF_GREY)
    hip_roof(g, -9, 9, 9, 19, h+6.0, 3.2, 1.8, ROOF_GREY_D)
    tomoe(g, 0, h+4.4, 19.06, 1.3, (0, 0, 1))
    g.box((0, h+4.4, 19.03), (3.2, 2.9, .04), TIMBER, collide=False)
    # Torii colado na porta sul (como no quadro de 10:00) e corda sagrada.
    g.torii(0, 0, z1+1.0, w=6.4, h=5.4, along='x', collide=False)
    g.tube([(-3, 4.3, z1+.4), (0, 3.9, z1+.4), (3, 4.3, z1+.4)], .12, (226, 210, 160), seg=6)
    # Interior: piso de madeira, pilares, lanternas, balcao com o painel "XXXX" e o emblema.
    g.overlay(x0+t, z0+t, x1-t, z1-t, (150, 96, 64), PLANK, 6)
    for x in (-7, 7):
        for z in (10, 14, 18):
            g.cylinder((x, 0, z), .32, h, TIMBER, PLANK, seg=10)
            g.collider((x-.32, 0, z-.32), (x+.32, h, z+.32))
            hanging_lantern(g, x+(1.6 if x < 0 else -1.6), 4.6, z)
    g.bounds((9, 0, 9), (13.2, 1.1, 19), (110, 60, 46), PLANK)
    g.box((13.3, 3.6, 14), (.1, 1.0, 4.2), (30, 30, 36), collide=False)
    for k in range(4):
        g.box((13.24, 3.6, 12.5+k), (.04, .5, .5), (70, 90, 230), collide=False)
    tomoe(g, -13.36, 4.2, 14, 1.1, (1, 0, 0))
    g.lamp(-11, 0, 8, 3.2)


def septum(g):
    """Paredao de rocha com a valva tricuspide: portao de 6 m com dois guardioes e uma fenda
    estreita a leste. Os corredores laterais (x ~ +-29) passam por fora."""
    g.zone('paredao')
    z0, z1 = -3, -1
    rock(g, -24, z0, -3, z1, 8.5, seed='paredao-o')
    rock(g, 3, z0, 12, z1, 8.5, seed='paredao-c')
    rock(g, 14.5, z0, 24, z1, 8.5, seed='paredao-l')
    rock(g, 12, z0, 14.5, z1, 5.5, y0=3.0, seed='fenda')   # teto baixo da fenda
    rock(g, -3, z0, 3, z1, 2.4, y0=6.1, seed='lintel')     # verga do portao
    # Portico do portao (moldura vermelha) e os guardioes.
    for x in (-3.3, 3.3):
        g.box((x, 3.05, z1+.35), (.6, 6.1, .6), TIMBER, PLANK)
    g.box((0, 6.3, z1+.25), (7.6, .5, .7), TIMBER, PLANK, collide=False)
    g.box((0, 6.8, z1+.25), (3.0, .7, .1), (30, 30, 36), collide=False)
    nio(g, -8.5, 2.4, 1)
    nio(g, 8.5, 2.4, 1)
    for x in (-12.5, 12.5):
        stone_lantern(g, x, 1.4)


def torii_tunnel(g):
    """Tunel de torii (S01E08 11:24, 11:36): gruta de rocha, tapete vermelho e porticos seguidos."""
    g.zone('tunel_torii')
    z0, z1 = -31, -3
    rock(g, -6, z0, -4, z1, 6.5, seed='tunel-o')
    rock(g, 4, z0, 6, z1, 6.5, seed='tunel-l')
    g.bounds((-6, 6.5, z0), (6, 7.6, z1), ROCK_D, FLAGSTONE, top=MOSS, pats={'top': LEAF})
    rng = random.Random('teto')
    for _ in range(26):
        g.sphere((rng.uniform(-5, 5), 6.6, rng.uniform(z0+1, z1-1)), rng.uniform(.6, 1.2), ROCK_D, FLAGSTONE, seg=7,
                 rings=4, squash=.5)
    for z in range(-6, -30, -4):
        g.torii(0, 0, z, w=5.2, h=4.6, along='x')
    for z in range(-8, -30, -8):
        for x in (-3.4, 3.4):
            hanging_lantern(g, x, 3.4, z, .3)


def flanks(g):
    """Fora do tunel: jardim de musgo (oeste, com rochas e lanternas) e o patio de servico (leste,
    com caixas). Os corredores laterais ligam o atrio ao ventriculo sem passar pelas valvas."""
    g.zone('flancos')
    for x, z, s in ((-18, -10, 1.3), (-12, -22, 1.0), (-20, -26, 1.1), (-9, -14, .8)):
        g.sphere((x, 0, z), 1.6*s, ROCK, FLAGSTONE, seg=8, rings=5, squash=.7)
        g.collider((x-1.3*s, 0, z-1.3*s), (x+1.3*s, 1.3*s, z+1.3*s))
    for x, z in ((-15, -16), (-22, -18)):
        stone_lantern(g, x, z)
    for x, z in ((-11, -6.5), (-21, -6), (-8, -27.5)):
        g.tree(x, 0, z, 1.0)
    for x, z, s in ((14, -8, 1.4), (18, -9, 1.0), (10, -18, 1.2), (20, -22, 1.4), (13, -27, 1.0), (21, -14, 1.0)):
        g.crate(x, 0, z, s, .3)
    for x in (10, 22):
        g.lamp(x, 0, -14.5)
    # Edificio B (servico, leste): portas oeste e norte.
    shrine_block(g, 34, X1, -28, -8, 8, faces=('west', 'north'))
    g.door(34, 0, -18, (-1, 0), color=TIMBER)
    g.door(42, 0, -28, (0, -1), color=TIMBER)
    oxygen_sign(g, 34, 5.0, -13, -1)
    # Bloco oeste ao lado do jardim (fecha a borda).
    shrine_block(g, X0, -34, -28, 6, 9, faces=('east',))


def ventricle(g):
    """Salao do ventriculo direito (S01E08 11:48): teto em tenda listrado de vermelho e branco,
    lanternas em tambor penduradas, torii interno e mezaninos laterais."""
    g.zone('ventriculo')
    x0, x1, z0, z1 = HALL
    h, t = 8.0, .6
    # Parede sul: boca do tunel. Parede norte: valva pulmonar. Laterais: portas.
    g.bounds((x0, 0, z1-t), (-4, h, z1), (226, 200, 176), PLASTER)
    g.bounds((4, 0, z1-t), (x1, h, z1), (226, 200, 176), PLASTER)
    g.bounds((-4, 6.5, z1-t), (4, h, z1), (226, 200, 176), PLASTER)
    g.bounds((x0, 0, z0), (-3, h, z0+t), (226, 200, 176), PLASTER)
    g.bounds((3, 0, z0), (x1, h, z0+t), (226, 200, 176), PLASTER)
    g.bounds((-3, 6.1, z0), (3, h, z0+t), (226, 200, 176), PLASTER)
    for xx, xi in ((x0, x0+t), (x1-t, x1)):
        g.bounds((xx, 0, z0+t), (xi, h, -44), (226, 200, 176), PLASTER)
        g.bounds((xx, 0, -38), (xi, h, z1-t), (226, 200, 176), PLASTER)
        g.bounds((xx, 3.6, -44), (xi, h, -38), (226, 200, 176), PLASTER)
    g.solid((x0, 0, z0), (x1, h+6, z1))
    for x in range(int(x0), int(x1)+1, 3):
        if abs(x) < 4.5:
            continue  # vao do tunel (sul) e da valva pulmonar (norte)
        for z in (z0-.1, z1+.1):
            g.box((x, h/2, z), (.3, h, .2), TIMBER, PLANK, collide=False)
    # Teto em tenda: faixas alternadas que sobem das paredes ate a cumeeira (x = 0).
    ridge = h+6
    steps = 16
    for side in (-1, 1):
        for k in range(steps):
            za, zb = z0+(z1-z0)*k/steps, z0+(z1-z0)*(k+1)/steps
            col = (200, 50, 50) if k % 2 else (244, 226, 222)
            xe = x1 if side > 0 else x0
            g.face([(xe, h, za), (xe, h, zb), (0, ridge, zb), (0, ridge, za)], col, PLAIN, (side*.4, -1, 0))
            g.face([(xe+side*.3, h, za), (xe+side*.3, h, zb), (0, ridge+.3, zb), (0, ridge+.3, za)], ROOF_GREY_D, ROOF,
                   (side, 1, 0))
    for zz, n in ((z0, -1), (z1, 1)):
        g.face([(x0, h, zz), (x1, h, zz), (0, ridge, zz)], (226, 200, 176), PLASTER, (0, 0, -n))
        g.face([(x0, h, zz+n*.02), (x1, h, zz+n*.02), (0, ridge, zz+n*.02)], (226, 200, 176), PLASTER, (0, 0, n))
    # Lanternas em tambor, torii interno e balcao.
    for x in (-12, -6, 6, 12):
        for z in (-46, -40):
            hanging_lantern(g, x, 7.4, z, .36, (240, 200, 150))
    g.torii(0, 0, -36, w=7, h=5.4, along='x')
    g.torii(0, 0, -45, w=7, h=5.4, along='x')
    # Mezaninos (4 m) ao longo das paredes oeste e leste, com escadas.
    for sgn in (-1, 1):
        xa, xb = (x0+t, x0+t+4.5) if sgn < 0 else (x1-t-4.5, x1-t)
        g.bounds((xa, 3.8, -49.8), (xb, 4.0, -33.8), (150, 96, 64), PLANK)
        edge = xb if sgn < 0 else xa
        g.railing((edge, 4.0, -49.8), (edge, 4.0, -40.6), TIMBER)
        for z in (-49.4, -44.4, -38.6, -34.2):
            g.cylinder((edge, 0, z), .16, 3.8, TIMBER, PLANK, seg=6, collide=False)
            g.collider((edge-.17, 0, z-.17), (edge+.17, 3.8, z+.17))
        # Escada perpendicular a parede, chegando na ponta sul do mezanino (sem guarda-corpo ali).
        g.stairs((sgn*11, 0, -35.4), (edge, 4.0, -35.4), 2.4, (150, 96, 64), PLANK, side_color=TIMBER_D)
    for x in (-18, 18):
        g.box((x, .4, -48), (1.2, .8, .8), (206, 168, 116), PLANK)


def artery(g):
    """Arteria pulmonar (S01E08 12:24): corredor branco abobadado com aneis azuis e a placa
    "siga em frente". Fora dele, a praca que liga os corredores laterais ao pulmao."""
    g.zone('arteria')
    z0, z1 = -64, -51
    for x0_, x1_ in ((-4.6, -4), (4, 4.6)):
        g.bounds((x0_, 0, z0), (x1_, 4, z1), WHITE, PLASTER)
    steps = 10
    for k in range(steps):
        a0, a1 = math.pi*k/steps, math.pi*(k+1)/steps
        p0 = (-math.cos(a0)*4.3, 4+math.sin(a0)*3)
        p1 = (-math.cos(a1)*4.3, 4+math.sin(a1)*3)
        g.face([(p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], z1), (p0[0], p0[1], z1)], WHITE, PLASTER,
               (-(p0[0]+p1[0]), -(p0[1]+p1[1]-8), 0), smooth=True)
        g.face([(p0[0]*1.07, p0[1]+.2, z0), (p1[0]*1.07, p1[1]+.2, z0), (p1[0]*1.07, p1[1]+.2, z1),
                (p0[0]*1.07, p0[1]+.2, z1)], (226, 228, 232), PLASTER, ((p0[0]+p1[0]), (p0[1]+p1[1]-8), 0),
               smooth=True)
    for z in (-54, -58, -62):
        g.arch_rib((0, 4, z), 8.8, 3.2, .12, (90, 170, 210), 'x', steps=12)
        for x in (-4.4, 4.4):
            g.tube([(x, 0, z), (x, 4, z)], .12, (90, 170, 210), seg=6)
    for z in (-55.5, -61):
        g.tube([(0, 7.2, z), (0, 5.6, z)], .02, IRON, seg=4, caps=False)
        g.box((0, 4.9, z), (1.0, 1.6, .06), WHITE, collide=False)
        g.box((0, 4.6, z+.04), (.14, .6, .02), RED_ARCH, collide=False)
        g.face([(-.3, 5.0, z+.04), (.3, 5.0, z+.04), (0, 5.4, z+.04)], RED_ARCH, PLAIN, (0, 0, 1))
    for x, z in ((-12, -56), (-20, -60), (14, -55), (22, -61), (12, -62)):
        g.crate(x, 0, z, 1.2, .2)
    for x in (-10, 10):
        g.lamp(x, 0, -64.6)


def lung_station(g):
    """Estacao de troca do pulmao (S01E08 12:56, 13:12): galpao de trelicas com claraboias,
    canos, um tanque e as prateleiras de cilindros de O2; a doca do comboio fica a leste."""
    g.zone('pulmao')
    x0, x1, z0, z1 = SHED
    top = 10.0
    g.bounds((x0, 0, z0+.2), (x1, top, z0+.8), STEEL_D, METAL)
    g.bounds((x0, 0, z0+.8), (x0+.6, top, -76), STEEL_D, METAL)
    for x in range(int(x0), int(x1)+1, 5):
        if abs(x) < 6:
            continue  # entrada do comboio
        g.box((x, top/2, z1), (.5, top, .5), STEEL, METAL)
    for z in range(int(z0)+5, int(z1), 5):
        if z > -76:
            g.box((x0+.3, top/2, z), (.5, top, .5), STEEL, METAL)
        g.box((x1, top/2, z), (.5, top, .5), STEEL, METAL)
    # Telhado em trelica com faixas de claraboia.
    for x in range(int(x0), int(x1), 5):
        g.box((x+1.25, top+.4, (z0+z1)/2), (2.5, .2, z1-z0), STEEL_D, METAL, collide=False)
        g.box((x+3.75, top+.42, (z0+z1)/2), (2.5, .16, z1-z0), (200, 226, 236), GLASS, collide=False)
    for z in range(int(z0)+2, int(z1), 4):
        g.tube([(x0, top, z), (x1, top, z)], .1, STEEL_D, METAL, seg=5)
    # Placa do galpao, canos e o tanque.
    g.box((0, 7.4, z0+.7), (5, 1.2, .1), WHITE, collide=False)
    g.box((0, 7.4, z0+.76), (4, .5, .04), (40, 40, 46), collide=False)
    for y, col in ((3.2, (200, 70, 70)), (2.4, (90, 130, 200))):
        g.tube([(x0+.8, y, -70), (x0+.8, y, z0+1.2), (x1-2, y, z0+1.2)], .25, col, METAL, seg=8)
    g.cylinder((-14, 0, -80), 2.0, 6.5, (90, 110, 130), METAL, seg=14, collide=True)
    g.cylinder((-14, 6.5, -80), 2.0, 1.0, (90, 110, 130), METAL, seg=14, r_top=.4, collide=False)
    # Prateleiras de cilindros de O2 (escuros, com faixa branca).
    for xc in (-6, 2):
        g.bounds((xc-3.2, 0, -84.4), (xc+3.2, .2, -83.0), STEEL_D, METAL)
        g.bounds((xc-3.2, 2.4, -84.4), (xc+3.2, 2.5, -83.0), STEEL_D, METAL, collide=False)
        for k in range(8):
            x = xc-2.8+k*.8
            g.cylinder((x, .2, -83.7), .3, 1.6, O2_TANK, METAL, seg=10, collide=False)
            g.cylinder((x, 1.8, -83.7), .3, .2, O2_TANK, METAL, seg=10, r_top=.12, collide=False)
            g.box((x, 1.1, -83.38), (.24, .7, .04), WHITE, collide=False)
        g.collider((xc-3.2, 0, -84.4), (xc+3.2, 2.5, -83.0))
    # Carrinhos de cilindros e caixas de CO2 descarregadas.
    for x, z in ((-8, -72), (8, -82.4), (-4, -80)):
        g.cart(x, 0, z, .4)
    for x, z in ((10, -80), (11.2, -80.3), (10.5, -79)):
        g.crate(x, 0, z, .9, .2, (206, 168, 116))
    # Doca do comboio (piso amarelo listrado).
    g.overlay(11, -79, 19, -73, YELLOW, HAZARD, 7)
    # Posto C (oeste do pulmao): portas leste e sul.
    shrine_block(g, X0, -34, -68, -48, 9, faces=('east', 'south'))
    g.door(-34, 0, -56, (1, 0), color=TIMBER)
    g.door(-42, 0, -48, (0, 1), color=TIMBER)
    oxygen_sign(g, -34, 5.4, -61, 1)
    g.overlay(X0, -68, -20, -51, (214, 210, 204), FLAGSTONE, 2)


def lesion(g):
    """Lesao do endocardio (entrada bacteriana): cratera de tecido rasgado a leste do pulmao."""
    g.zone('lesao')
    px0, px1, pz0, pz1 = PIT
    g.bounds((30, PIT_FLOOR-1, pz0), (38, PIT_FLOOR, pz1), WOUND, TISSUE)
    for (a, b), (lo, hi) in (((px0, 30), (30, px0)), ((38, px1), (38, px1))):
        g.ramp((lo, PIT_FLOOR, -76), (hi, 0, -76), 7, (176, 100, 104), TISSUE, thick=.2)
        for z0_, z1_ in ((pz0, -79.5), (-72.5, pz1)):
            g.bounds((a, -3, z0_), (b, 0, z1_), (150, 80, 90), TISSUE, top=(186, 110, 116), pats={'top': TISSUE})
    rng = g.rng
    g.box((34, -1.0, -71.4), (7, 3.4, 1.4), (170, 96, 104), TISSUE, ry=.05)
    g.box((29.5, -1.4, -73), (2.6, 2.4, 1.2), (170, 96, 104), TISSUE, ry=.5)
    g.box((38.5, -1.4, -73), (2.6, 2.4, 1.2), (170, 96, 104), TISSUE, ry=-.5)
    for _ in range(14):
        g.sphere((rng.uniform(31, 37), PIT_FLOOR, rng.uniform(pz0+1, -76)), rng.uniform(.4, 1.0), FLESH, TISSUE, seg=7,
                 rings=4, squash=.6)
    for x in range(26, 43, 3):
        g.barrier(x, 0, -66.5, 0, 2.6)
    # Fibras do endocardio rasgadas por cima da cratera.
    for k in range(5):
        x = 26+k*4
        g.tube([(x, 0, -86), (x+1.5, 4.5, -82), (x+.5, 6, -76)], .35, (200, 120, 130), TISSUE, seg=6)


def boundary(g):
    g.zone('limites')
    H = 40
    g.collider((X0-1, -4, Z0), (X0, H, Z1))
    g.collider((X1, -4, Z0), (X1+1, H, Z1))
    g.collider((X0, -4, Z0-1), (X1, H, Z0))
    g.collider((X0, -4, Z1), (X1, H, Z1+1))


RING = 16


def perimeter(g):
    """Fora da area jogavel: o complexo de construcoes de madeira vermelha subindo em degraus
    (como atras do templo, S01E08 10:00) e, ao norte, a parede do coracao."""
    g.zone('perimetro')
    rng = g.rng
    for lo, hi in (((X0-120, -3.2, Z0-160), (X0, -.05, Z1+120)), ((X1, -3.2, Z0-160), (X1+120, -.05, Z1+120)),
                   ((X0, -3.2, Z1), (X1, -.05, Z1+120)), ((X0, -3.2, Z0-160), (X1, -.05, Z0))):
        g.bounds(lo, hi, (196, 176, 150), FLAGSTONE, collide=False, skip=('bottom', 'north', 'south', 'east', 'west'))
    for side in ('west', 'east', 'south', 'north'):
        a, end = (Z0-RING, Z1+RING) if side in ('west', 'east') else (X0, X1)
        while a < end-.1:
            b = min(end, a+rng.uniform(12, 18))
            h = rng.uniform(14, 26) if side != 'north' else rng.uniform(18, 30)
            if side == 'west':
                lo, hi = (X0-RING, -3, a), (X0, h, b)
                face = ('z', a, b, X0, 1)
            elif side == 'east':
                lo, hi = (X1, -3, a), (X1+RING, h, b)
                face = ('z', a, b, X1, -1)
            elif side == 'south':
                lo, hi = (a, -3, Z1), (b, h, Z1+RING)
                face = ('x', a, b, Z1, -1)
            else:
                lo, hi = (a, -3, Z0-RING), (b, h, Z0)
                face = ('x', a, b, Z0, 1)
            wall = PLASTER_W if rng.random() < .6 else (226, 200, 176)
            g.bounds(lo, hi, wall, PLASTER, collide=False, top=ROOF_GREY, skip=('bottom',))
            g.solid(lo, hi)
            if side == 'south':
                a = b
                continue  # escondida atras dos blocos da estacao
            g.facade(face[1], face[2], face[3], -3, h+3, face[4], face[0], style='shutter', start_floor=2, laundry=False,
                     wall=wall, accent=TIMBER)
            # Grade de madeira vermelha nas fachadas (o "predio de trelica" do fundo), so no trecho visivel.
            if face[0] == 'z':
                za, zb = max(a, Z0), min(b, Z1)
                for y in range(3, int(h), 3):
                    if zb-za > .5:
                        g.box((face[3]+face[4]*.08, y, (za+zb)/2), (.12, .18, zb-za), TIMBER, collide=False)
            else:
                for y in range(3, int(h), 3):
                    g.box(((a+b)/2, y, face[3]+face[4]*.08), (b-a, .18, .12), TIMBER, collide=False)
            a = b
    # Ao fundo, a parede muscular do coracao em camadas (vermelho-rosado).
    for k in range(10):
        x = -180+k*40
        g.sphere((x+rng.uniform(-10, 10), -10, Z0-120-rng.uniform(0, 40)), rng.uniform(40, 60), (210, 120, 128),
                 TISSUE, seg=10, rings=6, squash=.55)


# ---------------------------------------------------------------------------
def markers(g):
    P = {}
    for i, x in enumerate((-4, 0, 4)):
        P[f'spawn_cells.{i}'] = (x, 0, 68)
        P[f'spawn_bacteria.{i}'] = (34+x, PIT_FLOOR, -78 if x else -80)
    escort = [(0, 0, 54), (0, 0, 34), (0, 0, 22), (0, 0, 6), (0, 0, -2), (0, 0, -31), (0, 0, -50.5), (0, 0, -64),
              (0, 0, -70), (6, 0, -74), (15, 0, -76)]
    for i, p in enumerate(escort):
        P[f'escort.{i:02}'] = p
    P['wound'] = (34, PIT_FLOOR, -76)
    P['recon'] = (-24, 0, 20)
    nodes = {
        'depot': (44, 0, 48), 'depot_out': (31, 0, 48), 'S': (20, 0, 46), 'V': (0, 0, 44), 'W': (-24, 0, 44),
        'Wa': (-29, 0, 31.6), 'A_s': (-42, 0, 31.6), 'Wb': (-29, 0, 18), 'A_e': (-32.4, 0, 18), 'Wc': (-29, 0, 2),
        'Wd': (-29, 0, -20), 'We': (-29, 0, -46.4), 'C_s': (-42, 0, -46.4), 'Wf': (-29, 0, -56), 'C_e': (-32.4, 0, -56),
        'Ea': (29, 0, 34), 'Eb': (29, 0, 2), 'B_w': (32.4, 0, -18), 'Ec': (29, 0, -29.6), 'B_n': (42, 0, -29.6),
        'Ed': (29, 0, -56), 'Ee': (24, 0, -66), 'Nl': (-24, 0, -66),
    }
    edges = [('depot', 'depot_out'), ('depot_out', 'S'), ('S', 'V'), ('V', 'W'), ('W', 'Wa'), ('Wa', 'A_s'),
             ('Wa', 'Wb'), ('Wb', 'A_e'), ('Wb', 'Wc'), ('Wc', 'Wd'), ('Wd', 'We'), ('We', 'C_s'), ('We', 'Wf'),
             ('Wf', 'C_e'), ('S', 'Ea'), ('Ea', 'Eb'), ('Eb', 'B_w'), ('B_w', 'Ec'), ('Ec', 'B_n'), ('Ec', 'Ed'),
             ('Ed', 'Ee'), ('Ee', 'Nl'), ('Nl', 'C_e')]
    for k, v in nodes.items():
        P[f'rbc.{k}'] = v
    hints = [(5, 0, 1.2), (-5, 0, 1.2), (5.5, 0, -46.4), (-5.5, 0, -46.4), (-15, 0, -14), (16, 0, -24),
             (-22, 0, 8), (22, 0, 16), (-14, 0, 50), (24, 0, 52), (-16, 0, -58), (16, 0, -58), (-14, 0, -72),
             (44, 0, -62), (-40, 0, -36), (40, 0, -40)]
    for i, h in enumerate(hints):
        P[f'colony.{i:02}'] = h
    valves = [dict(id=0, kind='av', pos=list(VALVE_T), axis='x', width=6.0, height=6.1, flow=-1),
              dict(id=1, kind='semilunar', pos=list(VALVE_P), axis='x', width=6.0, height=6.1, flow=-1)]
    return {
        'mode': 'convoy',
        'points': P,
        'rbc_edges': edges,
        'destinations': {'A': ['A_s', 'A_e'], 'B': ['B_w', 'B_n'], 'C': ['C_s', 'C_e']},
        'cells_base': [-24, 56, 24, 76],
        'bounds': [X0, Z0, X1, Z1],
        'nav_ceilings': [9.0, 5.6, 2.9, .5, -1.4],
        'valves': valves,
        'ambient_spots': [list(s) for s in getattr(g, 'spots', [])],
        'extra': {'wound_radius': 6.0, 'recon_light': 3.0, 'background': [232, 214, 206]},
    }
