"""Icones vetoriais das habilidades (HUD estilo Arena): poucas primitivas, traço grosso.

``draw_icon(canvas, name, cx, cy, size, tint)`` desenha no espaço virtual 1280x720 do
Canvas. Os nomes vêm de ``catalog.ICONS``.
"""
import math


def _l(c, pts, w, tint, s, cx, cy):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        c.seg(cx+x1*s, cy+y1*s, cx+x2*s, cy+y2*s, w, tint)


def draw_icon(c, name, cx, cy, size, tint):
    s = size/2          # coordenadas normalizadas em [-1, 1]
    w = max(2.0, size*.11)
    L = lambda *pts, k=1.0: _l(c, pts, w*k, tint, s, cx, cy)  # noqa: E731
    O = lambda x, y, r, k=1.0: c.ring(cx+x*s, cy+y*s, r*s-w*k/2, r*s+w*k/2, 0, 360, tint)  # noqa: E731
    D = lambda x, y, r: c.circle(cx+x*s, cy+y*s, r*s, tint)  # noqa: E731
    T = lambda a, b, d: c.tri((cx+a[0]*s, cy+a[1]*s), (cx+b[0]*s, cy+b[1]*s), (cx+d[0]*s, cy+d[1]*s), tint)  # noqa: E731
    if name == 'eye':
        L((-.95, 0), (-.45, -.45), (.45, -.45), (.95, 0), (.45, .45), (-.45, .45), (-.95, 0))
        D(0, 0, .28)
    elif name == 'rifle':
        L((-.9, .1), (.9, .1), k=1.6)
        L((-.9, .1), (-.9, .5))
        L((-.2, .1), (-.35, .6))
        L((.5, -.15), (.9, -.15))
    elif name == 'knife':
        T((-.7, .7), (.75, -.75), (.1, .25))
        L((-.85, .85), (-.45, .45), k=1.6)
    elif name == 'dash':
        T((.2, -.6), (.95, 0), (.2, .6))
        for y in (-.35, 0, .35):
            L((-.9, y), (-.05, y))
    elif name == 'net':
        O(0, 0, .85)
        for k in (-.4, .4):
            L((k, -.75), (k, .75), k=.7)
            L((-.75, k), (.75, k), k=.7)
    elif name == 'radar':
        O(0, 0, .85)
        O(0, 0, .45, .8)
        L((0, 0), (.6, -.6))
        D(.35, .35, .12)
    elif name == 'mouth':
        c.ring(cx, cy, s*.55, s*.85, 200, 340, tint)
        c.ring(cx, cy, s*.55, s*.85, 20, 160, tint)
        for k in (-.4, 0, .4):
            T((k-.12, -.42), (k+.12, -.42), (k, -.15))
    elif name == 'hook':
        L((0, -.9), (0, .3))
        c.ring(cx-s*.35, cy+s*.3, s*.25, s*.25+w, 0, 180, tint)
        T((-.7, .3), (-.85, -.05), (-.5, .05))
    elif name == 'axe':
        L((-.7, .85), (.45, -.55), k=1.4)
        T((.05, -.95), (.95, -.25), (.35, .15))
    elif name == 'mark':
        T((0, -.9), (.75, 0), (0, .9))
        T((0, -.9), (0, .9), (-.75, 0))
    elif name == 'scope':
        O(0, 0, .75)
        L((-.95, 0), (-.35, 0))
        L((.35, 0), (.95, 0))
        L((0, -.95), (0, -.35))
        L((0, .35), (0, .95))
    elif name == 'turret':
        D(0, -.15, .45)
        L((.2, -.15), (.95, -.15), k=1.4)
        L((-.3, .3), (-.7, .9))
        L((.3, .3), (.7, .9))
        L((0, .3), (0, .9))
    elif name == 'grenade':
        D(0, .15, .62)
        L((-.15, -.5), (.25, -.85), k=1.2)
        L((.25, -.85), (.6, -.6))
    elif name == 'rain':
        for x, y in ((-.55, -.55), (.1, -.75), (.6, -.4), (-.3, .2), (.35, .35)):
            L((x, y), (x, y+.4))
            L((x, y+.4), (x-.2, y+.6), k=.8)
            L((x, y+.4), (x+.2, y+.6), k=.8)
    elif name == 'fist':
        c.rect(cx-s*.6, cy-s*.45, s*1.2, s*.95, tint)
        for k in (-.45, -.15, .15, .45):
            D(k, -.5, .2)
        L((-.6, .5), (-.6, .9), k=1.6)
    elif name == 'leap':
        c.ring(cx, cy+s*.4, s*.7, s*.7+w, 180, 360, tint)
        T((.7, .4), (.95, .0), (.45, .05))
        L((-.9, .85), (.9, .85))
    elif name == 'drop':
        T((0, -.95), (-.55, .1), (.55, .1))
        D(0, .3, .58)
    elif name == 'burst':
        for i in range(8):
            a = i*math.tau/8
            L((math.cos(a)*.3, math.sin(a)*.3), (math.cos(a)*.95, math.sin(a)*.95))
        D(0, 0, .25)
    elif name == 'shield':
        T((-.75, -.7), (.75, -.7), (0, .95))
        T((-.75, -.7), (0, .95), (-.75, .1))
        T((.75, -.7), (.75, .1), (0, .95))
    elif name == 'barrier':
        L((-.9, -.75), (.9, -.75), (.9, .75), (-.9, .75), (-.9, -.75))
        for x in (-.3, .3):
            L((x, -.75), (x, .75), k=.7)
        L((-.9, 0), (.9, 0), k=.7)
    elif name == 'cloud':
        D(-.4, .15, .4)
        D(.1, -.15, .5)
        D(.5, .2, .35)
        c.rect(cx-s*.6, cy+s*.15, s*1.2, s*.4, tint)
    elif name == 'cluster':
        for x, y in ((-.4, -.35), (.35, -.35), (0, .3), (-.6, .4), (.6, .4)):
            D(x, y, .32)
    elif name == 'wall':
        for row, y in enumerate((-.6, 0, .6)):
            off = .4 if row % 2 else 0
            for x in (-.8, 0, .8):
                c.rect(cx+(x+off-.35)*s, cy+(y-.24)*s, s*.7, s*.46, tint)
    elif name == 'toxin':
        O(0, -.2, .55)
        L((-.6, .6), (.6, -.0), k=1.2)
        L((-.6, 0), (.6, .6), k=1.2)
        D(-.2, -.25, .1)
        D(.2, -.25, .1)
    elif name == 'dome':
        c.ring(cx, cy+s*.55, s*.85-w/2, s*.85+w/2, 180, 360, tint)
        L((-.95, .55), (.95, .55))
        D(0, .25, .2)
    elif name == 'acid':
        T((0, -.9), (-.45, .0), (.45, .0))
        D(0, .25, .45)
        D(.7, .7, .15)
        D(-.65, .6, .12)
    elif name == 'slide':
        L((-.9, .6), (.9, .6), k=1.4)
        L((-.6, .2), (.6, .2), k=.8)
        T((.4, -.6), (.95, -.15), (.3, .0))
    elif name == 'chain':
        for x, y in ((-.55, .45), (0, 0), (.55, -.45)):
            O(x, y, .3, .8)
    elif name == 'clone':
        D(-.35, -.35, .3)
        D(.35, -.35, .3)
        c.rect(cx-s*.75, cy+s*.05, s*.65, s*.75, tint)
        c.rect(cx+s*.1, cy+s*.05, s*.65, s*.75, tint)
    else:
        D(0, 0, .5)
