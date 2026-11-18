"""Linguagem visual "Mangá" dos menus: quadros brancos com contorno de nanquim e sombra
chapada, retícula, linhas de velocidade, balões, explosões e o palco 3D do herói.

O espaço virtual tem 720 de altura útil e a largura real da janela (``W`` >= 1280): as telas
ancoram nas bordas em vez de ganhar faixas laterais. Em telas mais altas que 16:9 o conteúdo
fica centrado na vertical (``top``/``bottom`` dizem até onde o fundo deve ir).

Cada quadro é desenhado numa RenderTexture com o dobro da resolução e reduzido com filtro
bilinear (supersampling 4x): bordas inclinadas, balões e texto saem sem serrilhado.
A HUD de combate continua com o próprio estilo; só os menus herdam ``MangaCanvas``.
"""
import math
import time
from pathlib import Path
import pyray as rl
from .ui_base import Canvas
from .visuals import color

INK = (17, 17, 17)
PAPER = (244, 241, 232)
WHITE = (255, 255, 255)
YELLOW = (255, 225, 74)
RED = (200, 16, 46)
CYAN = (159, 240, 234)
PINK = (255, 179, 189)
BLUSH = (255, 227, 231)
MINT = (233, 251, 249)
GREEN = (26, 127, 75)
GREY = (221, 221, 221)
MUTED = (85, 85, 85)

# Glifos carregados nas fontes: ASCII + Latin-1 + alguns sinais usados nos menus.
CODEPOINTS = list(range(32, 127)) + list(range(160, 256)) + [0x2013, 0x2014, 0x2022, 0x2026, 0x2605, 0x2606,
                                                               0x25C0, 0x25B6, 0x25CF]
# Cada fonte é carregada em alguns tamanhos de atlas; o texto usa o menor atlas que cobre o
# tamanho em pixels (já contando o supersampling). "body" é o texto corrido (Medium) e
# "bold" os rótulos curtos.
FONTS = {"title": ("Bangers-Regular", (40, 72, 128, 200), .06),
         "body": ("MPLUSRounded1c-Medium", (24, 40, 64, 96), .0),
         "bold": ("MPLUSRounded1c-Bold", (24, 40, 64, 96), .0)}
# A M PLUS tem letras baixas para o tamanho da linha: os tamanhos pedidos crescem 12% para
# que 16 "pareça" 16 ao lado da Bangers.
SIZE_BOOST = {"body": 1.12, "bold": 1.12}
_ATLASES = {}  # compartilhado entre telas: recarregar as fontes a cada troca de tela é lento

# Explosões (pontas normalizadas 0..1 em x/y; todas "estreladas" em relação ao centro).
BURST = [(.5, 0), (.6, .2), (.84, .06), (.8, .32), (1, .4), (.82, .56), (.96, .84), (.68, .76), (.54, 1),
         (.4, .8), (.12, .94), (.18, .66), (0, .52), (.2, .38), (.1, .1), (.36, .2)]
BURST_SOFT = [(.5, 0), (.62, .22), (.88, .1), (.8, .36), (1, .5), (.8, .64), (.88, .9), (.62, .78), (.5, 1),
              (.38, .78), (.12, .9), (.2, .64), (0, .5), (.2, .36), (.12, .1), (.38, .22)]


def _load_fonts():
    if _ATLASES:
        return _ATLASES
    storage = rl.ffi.new("int[]", CODEPOINTS)
    codepoints = rl.ffi.cast("int *", storage)  # ponteiro (o wrapper do pyray tomaria o endereço do array)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_ERROR)  # acentos altos geram avisos inofensivos
    try:
        for key, (name, sizes, _) in FONTS.items():
            path = Path("Assets/fonts") / f"{name}.ttf"
            if path.exists():
                _ATLASES[key] = []
                for size in sizes:
                    font = rl.load_font_ex(str(path), size, codepoints, len(CODEPOINTS))
                    rl.set_texture_filter(font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
                    _ATLASES[key].append((size, font))
    finally:
        rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    return _ATLASES


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


class MangaCanvas(Canvas):
    def __init__(self):
        super().__init__()
        self.fonts = {}
        self.halftone = None
        self.mouse_down = False
        self.frame_target = None
        self.ss = 1
        self.W, self.H = 1280.0, 720.0
        self.top, self.bottom = 0.0, 720.0

    def init(self):
        super().init()
        self.fonts = _load_fonts()
        self.layout()
        # Retícula: um ponto por ladrilho, repetido por wrap (um único draw para qualquer área).
        image = rl.gen_image_color(24, 24, rl.BLANK)
        rl.image_draw_circle(rl.ffi.addressof(image), 12, 12, 5, rl.WHITE)
        self.halftone = rl.load_texture_from_image(image)
        rl.unload_image(image)
        rl.set_texture_wrap(self.halftone, rl.TextureWrap.TEXTURE_WRAP_REPEAT)
        rl.set_texture_filter(self.halftone, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)

    def on_destroy(self):
        if self.frame_target is not None:
            rl.unload_render_texture(self.frame_target)
            self.frame_target = None
        if self.halftone is not None:
            rl.unload_texture(self.halftone)
            self.halftone = None
        super().on_destroy()

    # -- base ------------------------------------------------------------------------------
    def layout(self):
        sw, sh = max(1, rl.get_screen_width()), max(1, rl.get_screen_height())
        self.scale = min(sw / 1280, sh / 720)
        self.W, self.H = sw / self.scale, sh / self.scale
        self.ox, self.oy = 0.0, (sh - 720 * self.scale) / 2
        self.top, self.bottom = -self.oy / self.scale, 720 + self.oy / self.scale
        # 2x até 2560x1600; acima disso o pixel já é pequeno e a textura ficaria enorme.
        self.ss = 2 if sw * sh <= 2560 * 1600 else 1
        self.controls = []

    def page(self, tint=PAPER):
        rl.clear_background(color(tint))

    def draw(self):
        """Conteúdo da tela (as subclasses desenham aqui; ``render`` cuida do supersampling)."""

    def render(self):
        self.layout()
        sw, sh = rl.get_screen_width(), rl.get_screen_height()
        tw, th = int(sw * self.ss), int(sh * self.ss)
        target = self.frame_target
        if target is None or (target.texture.width, target.texture.height) != (tw, th):
            if target is not None:
                rl.unload_render_texture(target)
            target = self.frame_target = rl.load_render_texture(tw, th)
            rl.set_texture_filter(target.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
        rl.begin_texture_mode(target)
        rl.rl_push_matrix()
        rl.rl_scalef(self.ss, self.ss, 1)
        try:
            self.draw()
        finally:
            rl.rl_pop_matrix()
            rl.end_texture_mode()
        outer = getattr(self.camera, "final_render_target", None) if self.camera else None
        if outer:
            rl.begin_texture_mode(outer)  # end_texture_mode acima voltou para a tela
        rl.draw_texture_pro(target.texture, rl.Rectangle(0, 0, tw, -th), rl.Rectangle(0, 0, sw, sh),
                            rl.Vector2(0, 0), 0, rl.WHITE)

    def P(self, x, y):
        return rl.Vector2(self.ox + x * self.scale, self.oy + y * self.scale)

    def rect(self, x, y, w, h, tint=None, alpha=255):
        """Sem ``tint``: o retângulo de tela; com ``tint``: desenha (API dos ícones da HUD)."""
        if tint is None:
            return super().rect(x, y, w, h)
        self.panel(x, y, w, h, tint, alpha)

    def hovered(self, x, y, w, h):
        return rl.check_collision_point_rec(rl.get_mouse_position(), self.rect(x, y, w, h))

    def click(self, x, y, w, h, action):
        self.controls.append((self.rect(x, y, w, h), action))

    # -- texto -----------------------------------------------------------------------------
    def _font(self, font, size=64):
        atlases = self.fonts.get(font)
        if not atlases:
            return self.font
        pixels = size * getattr(self, "scale", 1.0) * self.ss
        return next((f for s, f in atlases if s >= pixels * .92), atlases[-1][1])

    def measure(self, value, size, font="bold"):
        size *= SIZE_BOOST.get(font, 1.0)
        spacing = size * FONTS.get(font, ("", 0, 0))[2]
        return rl.measure_text_ex(self._font(font, size), str(value), size, spacing).x

    def t(self, value, x, y, size=16, tint=INK, font="bold", align="l", alpha=255, stroke=0, shadow=0,
          stroke_tint=INK, angle=0.0):
        """Texto no espaço virtual; ``stroke``/``shadow`` desenham contorno e sombra de nanquim."""
        value = str(value)
        size *= SIZE_BOOST.get(font, 1.0)
        f = self._font(font, size)
        spacing = size * FONTS.get(font, ("", 0, 0))[2]
        width = rl.measure_text_ex(f, value, size, spacing).x
        if align == "c":
            x -= width / 2
        elif align == "r":
            x -= width
        s = self.scale

        def draw(dx, dy, tint_, a):
            if angle:
                rl.draw_text_pro(f, value, self.P(x + dx, y + dy), rl.Vector2(0, 0), angle, size * s, spacing * s,
                                 color(tint_, a))
            else:
                rl.draw_text_ex(f, value, self.P(x + dx, y + dy), size * s, spacing * s, color(tint_, a))
        ring = [(math.cos(i * math.tau / 12) * stroke, math.sin(i * math.tau / 12) * stroke) for i in range(12)]
        if shadow:
            for dx, dy in ring or [(0, 0)]:
                draw(shadow + dx, shadow + dy, stroke_tint, alpha)
        for dx, dy in ring:
            draw(dx, dy, stroke_tint, alpha)
        draw(0, 0, tint, alpha)
        return width

    def fit(self, value, x, y, width, size=16, **kw):
        m = self.measure(value, size, kw.get("font", "bold"))
        size = min(size, size * width / max(1.0, m))
        return self.t(value, x, y, size, **kw)

    def wrap(self, value, x, y, width, size=15, tint=INK, font="body", leading=1.32, alpha=255, max_lines=99):
        """Quebra por palavras; devolve a altura usada."""
        lines, current = [], ""
        for word in str(value).split():
            probe = f"{current} {word}".strip()
            if current and self.measure(probe, size, font) > width:
                lines.append(current)
                current = word
            else:
                current = probe
        if current:
            lines.append(current)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(".,;:") + "…"
        for i, text in enumerate(lines):
            self.t(text, x, y + i * size * leading, size, tint, font, alpha=alpha)
        return len(lines) * size * leading

    # -- formas ----------------------------------------------------------------------------
    def tri(self, a, b, c, tint, alpha=255):
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0:
            b, c = c, b
        rl.draw_triangle(self.P(*a), self.P(*b), self.P(*c), color(tint, alpha))

    def poly(self, points, tint, alpha=255):
        """Polígono estrelado em relação ao centróide (quadros inclinados, explosões)."""
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        for a, b in zip(points, points[1:] + points[:1]):
            self.tri((cx, cy), a, b, tint, alpha)

    def seg(self, x1, y1, x2, y2, w, tint, alpha=255):
        rl.draw_line_ex(self.P(x1, y1), self.P(x2, y2), w * self.scale, color(tint, alpha))

    def ring(self, cx, cy, r0, r1, a0, a1, tint, alpha=255):
        rl.draw_ring(self.P(cx, cy), max(0, r0) * self.scale, r1 * self.scale, a0, a1, 40, color(tint, alpha))

    def circle(self, x, y, r, tint, alpha=255):
        rl.draw_circle_v(self.P(x, y), r * self.scale, color(tint, alpha))

    def rbox(self, x, y, w, h, tint, angle=0.0, alpha=255):
        """Retângulo girado em torno do próprio centro."""
        s = self.scale
        rl.draw_rectangle_pro(rl.Rectangle(self.ox + (x + w / 2) * s, self.oy + (y + h / 2) * s, w * s, h * s),
                              rl.Vector2(w * s / 2, h * s / 2), angle, color(tint, alpha))

    def round(self, x, y, w, h, r, tint, alpha=255):
        rl.draw_rectangle_rounded(self.rect(x, y, w, h), min(1.0, 2 * r / max(1, min(w, h))), 12, color(tint, alpha))

    def outline(self, x, y, w, h, tint=INK, thick=3):
        self.panel(x, y, w, thick, tint)
        self.panel(x, y + h - thick, w, thick, tint)
        self.panel(x, y, thick, h, tint)
        self.panel(x + w - thick, y, thick, h, tint)

    def dashed(self, x, y, w, h, tint=INK, thick=3, dash=10, gap=7):
        for (x1, y1, dx, dy, length) in ((x, y, 1, 0, w), (x, y + h - thick, 1, 0, w), (x, y, 0, 1, h),
                                         (x + w - thick, y, 0, 1, h)):
            k = 0
            while k < length:
                n = min(dash, length - k)
                self.panel(x1 + dx * k, y1 + dy * k, max(thick, dx * n), max(thick, dy * n), tint)
                k += dash + gap

    def box(self, x, y, w, h, fill=WHITE, border=3, shadow=4, shadow_tint=INK, dashed=False):
        """Quadro de mangá: sombra chapada, contorno de nanquim e miolo."""
        if shadow:
            self.panel(x + shadow, y + shadow, w, h, shadow_tint)
        self.panel(x, y, w, h, fill)
        if dashed:
            self.dashed(x, y, w, h, INK, border)
        elif border:
            self.outline(x, y, w, h, INK, border)

    def framed_poly(self, points, fill, border=4, shadow=5):
        """Quadro poligonal (borda inclinada): sombra, nanquim e miolo recuado."""
        if shadow:
            self.poly([(px + shadow, py + shadow) for px, py in points], INK)
        self.poly(points, fill)
        for a, b in zip(points, points[1:] + points[:1]):
            self.seg(a[0], a[1], b[0], b[1], border, INK)
            self.circle(a[0], a[1], border / 2, INK)

    def halftone_rect(self, x, y, w, h, tint=INK, alpha=60, step=6):
        if self.halftone is None:
            return
        rl.draw_texture_pro(self.halftone, rl.Rectangle(0, 0, w / step * 24, h / step * 24), self.rect(x, y, w, h),
                            rl.Vector2(0, 0), 0, color(tint, alpha))

    def halftone_fade(self, x, y, w, h, tint=INK, alpha=70, bands=8, up=True):
        """Retícula que se desfaz (de baixo para cima quando ``up``)."""
        for i in range(bands):
            k = (i + 1) / bands
            by = y + h - h * (i + 1) / bands if up else y + h * i / bands
            self.halftone_rect(x, by, w, h / bands, tint, alpha * (1 - k + 1 / bands))

    def speed_lines(self, cx, cy, r0, r1, tint=INK, alpha=110, count=64, width=.012, spin=0.0):
        for i in range(count):
            a = spin + i * math.tau / count + (i * 7 % 5) * .01
            w = width * (1 + (i * 13 % 7) / 7)
            inner = r0 * (1 + (i * 11 % 5) * .08)
            p0 = (cx + math.cos(a) * inner, cy + math.sin(a) * inner)
            p1 = (cx + math.cos(a - w) * r1, cy + math.sin(a - w) * r1)
            p2 = (cx + math.cos(a + w) * r1, cy + math.sin(a + w) * r1)
            self.tri(p0, p1, p2, tint, alpha)

    def stripes(self, x, y, w, h, tint=WHITE, alpha=170, gap=17, thick=3, slant=.36):
        k = -h * slant
        while k < w:
            self.poly([(x + k, y + h), (x + k + h * slant, y), (x + k + h * slant + thick, y), (x + k + thick, y + h)],
                      tint, alpha)
            k += gap

    def burst(self, x, y, w, h, fill=YELLOW, shape=BURST, border=8, shadow=5):
        def pts(dx, dy, inset):
            return [(x + inset + px * (w - 2 * inset) + dx, y + inset * .9 + py * (h - 1.8 * inset) + dy)
                    for px, py in shape]
        if shadow:
            self.poly(pts(shadow, shadow, 0), INK)
        self.poly(pts(0, 0, 0), INK)
        self.poly(pts(0, 0, border), fill)

    def scissor(self, x, y, w, h):
        r, k = self.rect(x, y, w, h), self.ss
        rl.begin_scissor_mode(int(r.x * k), int(r.y * k), int(math.ceil(r.width * k)), int(math.ceil(r.height * k)))

    def end_scissor(self):
        rl.end_scissor_mode()

    def arrow(self, x, y, size, tint=INK, direction=1):
        """Triângulo (▸ / ◂): as fontes de título não têm esses glifos."""
        self.tri((x, y - size / 2), (x, y + size / 2), (x + direction * size * .85, y), tint)

    # -- componentes -----------------------------------------------------------------------
    def kb(self, label, x, y, h=28, fill=INK, tint=WHITE, size=None):
        """Tecla em pílula (RMB, Q, E, F). Devolve a largura."""
        size = size or h * .62
        w = max(h, self.measure(label, size, "title") + h * .5)
        self.round(x, y, w, h, h / 2, fill)
        self.t(label, x + w / 2, y + (h - size) / 2 - size * .02, size, tint, "title", "c")
        return w

    def button(self, title, x, y, w, action, primary=False, enabled=True, h=54, fill=None, size=None, arrow=False):
        hover = enabled and self.hovered(x, y, w, h)
        fill = fill or (YELLOW if primary else WHITE)
        size = size or min(30, h * .5)
        if not enabled:
            self.panel(x, y, w, h, GREY)
            self.halftone_rect(x, y, w, h, (170, 170, 170), 200)
            self.outline(x, y, w, h)
            self.t(title, x + w / 2, y + (h - size) / 2, size, (60, 60, 60), "title", "c", stroke=2,
                   stroke_tint=GREY)
            return
        lift = 2 if hover else 0
        self.box(x - lift, y - lift, w, h, fill, 3, 4 + lift * 1.5)
        tw = self.measure(title, size, "title") + (size * .9 if arrow else 0)
        tx = x - lift + (w - tw) / 2
        self.t(title, tx, y - lift + (h - size) / 2, size, INK, "title")
        if arrow:
            self.arrow(tx + tw - size * .55, y - lift + h / 2, size * .5)
        self.click(x, y, w, h, action)

    def chip(self, label, x, y, action, remove=None, fill=WHITE, note=""):
        """Etiqueta de recente: clique preenche; o "×" apaga. Devolve a largura."""
        h, size = 32, 15
        w_label = self.measure(label, size)
        w_note = self.measure(" · " + note, 13, "body") if note else 0
        w = 12 + w_label + w_note + (32 if remove else 12)
        hover = self.hovered(x, y, w - (26 if remove else 0), h)
        self.box(x, y, w, h, YELLOW if hover else fill, 2, 0)
        self.t(label, x + 12, y + 6, size)
        if note:
            self.t(" · " + note, x + 12 + w_label, y + 8, 13, MUTED, "body")
        self.click(x, y, w - (26 if remove else 0), h, action)
        if remove:
            cx, cy = x + w - 15, y + h / 2
            over = self.hovered(cx - 11, cy - 11, 22, 22)
            self.circle(cx, cy, 10, RED if over else INK)
            self.seg(cx - 4, cy - 4, cx + 4, cy + 4, 2.2, WHITE)
            self.seg(cx + 4, cy - 4, cx - 4, cy + 4, 2.2, WHITE)
            self.click(cx - 11, cy - 11, 22, 22, remove)
        return w

    def bubble(self, x, y, w, h, fill=WHITE, radius=22, tail=None, shadow=4, alpha=255, border=3):
        """Balão de fala; ``tail`` = (a, b, ponta): a e b sobre a borda do balão."""
        if shadow:
            self.round(x + shadow, y + shadow, w, h, radius, INK, alpha)
            if tail:
                a, b, p = tail
                self.tri((a[0] + shadow, a[1] + shadow), (b[0] + shadow, b[1] + shadow),
                         (p[0] + shadow, p[1] + shadow), INK, alpha)
        self.round(x, y, w, h, radius, INK, alpha)
        self.round(x + border, y + border, w - 2 * border, h - 2 * border, radius - border, fill, alpha)
        if tail:
            a, b, p = tail
            self.tri(a, b, p, INK, alpha)
            # Miolo da cauda: entra no balão (cobre a borda) e recua da ponta e das laterais.
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            nx, ny = mx - p[0], my - p[1]
            n = math.hypot(nx, ny) or 1
            nx, ny = nx / n, ny / n
            k = border + 2

            def pull(q):
                ux, uy = mx - q[0], my - q[1]
                u = math.hypot(ux, uy) or 1
                return q[0] + nx * k + ux / u * border * 1.4, q[1] + ny * k + uy / u * border * 1.4
            self.tri(pull(a), pull(b), (p[0] + nx * border * 2.2, p[1] + ny * border * 2.2), fill, alpha)

    # -- arte 2D ---------------------------------------------------------------------------
    def art_texture(self, hero):
        if hero not in self.textures:
            path = Path("Assets/characters") / f"{hero}.png"
            self.textures[hero] = rl.load_texture(str(path)) if path.exists() else None
            if self.textures[hero]:
                rl.gen_texture_mipmaps(rl.ffi.addressof(self.textures[hero]))
                rl.set_texture_filter(self.textures[hero], rl.TextureFilter.TEXTURE_FILTER_TRILINEAR)
        return self.textures[hero]

    def art(self, hero, x, y, w, h, img_h, dx=0.0, dy=0.0, tint=WHITE, alpha=255, flip=False):
        """Retrato oficial com altura ``img_h``, centralizado em x e recortado no quadro."""
        texture = self.art_texture(hero)
        if not texture:
            return
        k = img_h / texture.height
        iw = texture.width * k
        ix, iy = x + (w - iw) / 2 + dx, y + dy
        x0, y0 = max(x, ix), max(y, iy)
        x1, y1 = min(x + w, ix + iw), min(y + h, iy + img_h)
        if x1 <= x0 or y1 <= y0:
            return
        src = rl.Rectangle((x0 - ix) / k, (y0 - iy) / k, (x1 - x0) / k, (y1 - y0) / k)
        if flip:
            src.x = texture.width - src.x - src.width
            src.width = -src.width
        rl.draw_texture_pro(texture, src, self.rect(x0, y0, x1 - x0, y1 - y0), rl.Vector2(0, 0), 0, color(tint, alpha))


class HeroStage:
    """Palco 3D: o modelo do herói tocando a animação Idle, com contorno de nanquim.

    ``update`` desenha numa RenderTexture fora do quadro de tela (no ``loop`` do
    componente, antes de ``begin_drawing``); ``draw`` cola a textura no quadro da UI.
    """

    def __init__(self):
        self.target = None
        self.size = (0, 0)
        self.hero = None
        self.since = time.perf_counter()
        self.preload = None

    def update(self, hero, width, height):
        from .visuals import model
        from .models import load_meta
        from .outline import draw_outline
        width, height = max(8, int(width)), max(8, int(height))
        if self.target is None or self.size != (width, height):
            if self.target is not None:
                rl.unload_render_texture(self.target)
            self.target = rl.load_render_texture(width, height)
            rl.set_texture_filter(self.target.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
            self.size = (width, height)
        if hero != self.hero:
            self.hero = hero
            self.since = time.perf_counter()
        bottom, top, radius = self.bounds(hero, load_meta)
        now = time.perf_counter()
        fovy = 26.0
        aspect = width / height
        # Enquadramento de cabeça: mostra ~90% da altura (a placa do nome cobre as pernas) e
        # alarga se o giro em 3/4 pedir (raio no plano XZ). Quem sai do quadro são os pés.
        span = top - bottom
        visible = max(span * .9, 2 * radius * .75 / aspect)
        head_room = visible * .08
        cy = max(top + head_room - visible / 2, (top + bottom) / 2)
        distance = visible / 2 / math.tan(math.radians(fovy / 2)) + radius * .5
        camera = rl.Camera3D(rl.Vector3(0, cy + visible * .03, distance), rl.Vector3(0, cy, 0), rl.Vector3(0, 1, 0),
                             fovy, rl.CameraProjection.CAMERA_PERSPECTIVE)
        # Entrada girando + balanço lento em 3/4.
        spin = (1 - ease_out((now - self.since) / .6)) * math.tau * .5
        yaw = math.pi - .45 + .32 * math.sin(now * .7) + spin
        from EasyCells3D.Geometry import Vec3
        m = model(hero)
        args = (Vec3(0, 0, 0), yaw, 0.0, False, 0, 0, 0.0, None, 0.0)
        rl.begin_texture_mode(self.target)
        rl.clear_background(rl.BLANK)
        rl.begin_mode_3d(camera)
        m.draw(*args)
        draw_outline(m, args, (INK[0] / 255, INK[1] / 255, INK[2] / 255), width=2.6)
        rl.end_mode_3d()
        rl.end_texture_mode()

    def bounds(self, hero, load_meta):
        """(pé, topo, raio XZ) do modelo em repouso, pela caixa das malhas (o "height" do
        JSON não vale para bichos deitados como a Pseudomonas)."""
        cache = HeroStage.__dict__.get("_bounds")
        if cache is None:
            cache = HeroStage._bounds = {}
        if hero not in cache:
            try:
                tall = float(load_meta(hero).get("height", 1.9))
            except (OSError, ValueError):
                tall = 1.9
            result = (0.0, tall, tall * .3)
            from .visuals import model
            rig = model(hero).rig
            if rig is not None:
                box = rl.get_model_bounding_box(rig.model)
                lo, hi = box.min, box.max
                radius = max(math.hypot(x, z) for x in (lo.x, hi.x) for z in (lo.z, hi.z))
                result = (min(0.0, lo.y), max(hi.y, .5), radius)
            cache[hero] = result
        return cache[hero]

    def warm(self, heroes):
        """Carrega um modelo por chamada (evita travar quando a seleção troca de herói)."""
        from .visuals import model
        if self.preload is None:
            self.preload = list(heroes)
        if self.preload:
            model(self.preload.pop()).rig

    def draw(self, canvas, x, y, w, h, alpha=255):
        if self.target is None:
            return
        tw, th = self.size
        rl.draw_texture_pro(self.target.texture, rl.Rectangle(0, 0, tw, -th), canvas.rect(x, y, w, h),
                            rl.Vector2(0, 0), 0, color(WHITE, alpha))

    def unload(self):
        if self.target is not None:
            rl.unload_render_texture(self.target)
            self.target = None
