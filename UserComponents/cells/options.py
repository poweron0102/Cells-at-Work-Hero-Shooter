"""Tela de configurações (vídeo, áudio, controles e jogo) e aplicação das preferências.

``install(game)`` cria uma camada de UI persistente (``OverlayLayer``) que sobrevive às trocas
de cena e sempre desenha por cima das outras. Nela ficam:

* ``SettingsScreen``: o painel no estilo mangá, aberto pelo menu principal e pelo menu de pausa
  (``open_settings(game)``). Enquanto está aberto (e no quadro em que fecha) as outras telas e
  o ``PlayerInput`` ignoram teclado e cliques (``blocking``), então o Esc que fecha o painel não
  despausa a partida e o clique em "Voltar" não aperta o botão que estava embaixo.
* o contador de FPS (opcional) e a aplicação contínua de modo de tela, resolução, limite de FPS,
  VSync e volume geral (``apply_display``/``apply_audio``: só agem quando algo muda).

Tudo é salvo na hora em ``saves/config.json`` (``settings``); sliders só gravam ao soltar.
"""
import pyray as rl
from EasyCells3D.Components.CameraUI import CameraUI
from . import settings
from .manga_ui import MangaCanvas, INK, PAPER, WHITE, YELLOW, RED, MUTED, GREY, BLUSH
from .visuals import color

RESOLUTIONS = ((1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160))
DISPLAY_KEYS = ("display_mode", "resolution", "fps_limit", "vsync")
_applied = {}
_audio = {"ready": False, "volume": None}


# -- aplicação ---------------------------------------------------------------------------------
def monitor_size():
    if not rl.is_window_ready():
        return 1920, 1080
    monitor = rl.get_current_monitor()
    return max(1280, rl.get_monitor_width(monitor)), max(720, rl.get_monitor_height(monitor))


def resolutions():
    """Resoluções de janela que cabem no monitor atual ("LxA")."""
    mw, mh = monitor_size()
    return [f"{w}x{h}" for w, h in RESOLUTIONS if w <= mw and h <= mh] or ["1280x720"]


def apply_display():
    """Aplica modo de tela, resolução, limite de FPS e VSync (só o que mudou desde a última vez)."""
    if not rl.is_window_ready():
        return
    want = {key: settings.get(key) for key in DISPLAY_KEYS}
    old = dict(_applied)
    if want == old:
        return
    _applied.clear()
    _applied.update(want)
    if want["fps_limit"] != old.get("fps_limit"):
        rl.set_target_fps(int(want["fps_limit"]))
    if want["vsync"] != old.get("vsync"):
        if want["vsync"]:
            rl.set_window_state(rl.ConfigFlags.FLAG_VSYNC_HINT)
        else:
            rl.clear_window_state(rl.ConfigFlags.FLAG_VSYNC_HINT)
    borderless = want["display_mode"] == "borderless"
    if borderless != rl.is_window_state(rl.ConfigFlags.FLAG_BORDERLESS_WINDOWED_MODE):
        rl.toggle_borderless_windowed()
    moved = want["resolution"] != old.get("resolution") or want["display_mode"] != old.get("display_mode")
    if not borderless and moved:
        w, h = (int(v) for v in want["resolution"].split("x"))
        mw, mh = monitor_size()
        w, h = min(w, mw), min(h, mh)
        rl.set_window_size(w, h)
        origin = rl.get_monitor_position(rl.get_current_monitor())
        rl.set_window_position(int(origin.x + (mw - w) / 2), int(origin.y + max(0, (mh - h) / 2)))


def apply_audio():
    """Volume geral: reaplicado quando muda ou quando o dispositivo de áudio é (re)aberto."""
    ready = rl.is_audio_device_ready()
    volume = settings.get("master_volume")
    if ready and (not _audio["ready"] or volume != _audio["volume"]):
        rl.set_master_volume(volume)
        _audio["volume"] = volume
    _audio["ready"] = ready


def install(game, manage_display=True):
    """Cria a camada persistente com a tela de configurações (uma vez por jogo)."""
    if getattr(game, "options", None) is not None:
        return game.options
    item = game.CreateItem()
    item.name = "Options"
    item.destroy_on_load = False
    layer = item.AddComponent(OverlayLayer(manage_display))
    screen = SettingsScreen()
    screen.camera = layer
    item.AddComponent(screen)
    game.options = screen
    if manage_display:
        apply_display()
    return screen


def open_settings(game):
    screen = getattr(game, "options", None)
    if screen is not None:
        screen.open()


def blocking(game):
    """True enquanto a tela de configurações deve segurar teclado e mouse das outras telas."""
    screen = getattr(game, "options", None)
    return screen is not None and screen.blocking()


class OverlayLayer(CameraUI):
    """CameraUI persistente que se mantém por último na lista de câmeras (desenha por cima)."""

    def __init__(self, manage_display=True):
        main = CameraUI.main
        super().__init__()
        CameraUI.main = main  # nunca vira a câmera padrão das telas de cada cena
        self.manage_display = manage_display

    def loop(self):
        cameras = self.game.cameras
        if self in cameras and cameras[-1] is not self:
            cameras.remove(self)
            cameras.append(self)
        if self.manage_display:
            apply_display()
        apply_audio()

    def render(self):
        super().render()
        if settings.get("show_fps"):
            label = f"{rl.get_fps()} FPS"
            size = 20
            w = rl.measure_text(label, size)
            x = rl.get_screen_width() - w - 18
            rl.draw_rectangle(x - 8, 6, w + 16, size + 8, color(INK, 200))
            rl.draw_text(label, x, 10, size, color(YELLOW))


# -- tela ----------------------------------------------------------------------------------------
def _pct(v):
    return f"{int(round(v * 100))}%"


def _rows():
    """Abas -> linhas. Cada linha: (chave, tipo, rótulo, descrição, extra)."""
    from .maps import info as map_info, available as maps_available
    fps = {v: ("SEM LIMITE" if v == 0 else f"{v} FPS") for v in settings.CHOICES["fps_limit"]}
    return {
        "video": [
            ("display_mode", "choice", "MODO DE TELA", "Tela cheia ocupa o monitor inteiro, sem bordas.",
             dict(labels={"window": "JANELA", "borderless": "TELA CHEIA"})),
            ("resolution", "choice", "RESOLUÇÃO", "Tamanho da janela (em tela cheia vale a do monitor).",
             dict(options=resolutions, labels=lambda v: v.replace("x", " × "),
                  enabled=lambda: settings.get("display_mode") == "window")),
            ("fps_limit", "choice", "LIMITE DE FPS", "Quadros por segundo no máximo.", dict(labels=fps)),
            ("vsync", "toggle", "VSYNC", "Sincroniza com o monitor: sem cortes na imagem, um pouco mais de atraso.",
             {}),
            ("fov", "slider", "CAMPO DE VISÃO", "Ângulo vertical da câmera em 1ª pessoa.",
             dict(step=1, fmt=lambda v: f"{int(v)}°")),
            ("shadow_quality", "choice", "SOMBRAS", "Nitidez da sombra do sol · vale a partir da próxima partida.",
             dict(labels={"low": "BAIXA", "medium": "MÉDIA", "high": "ALTA"})),
        ],
        "audio": [
            ("master_volume", "slider", "VOLUME GERAL", "Tudo o que o jogo toca.", dict(step=.01, fmt=_pct)),
            ("sfx_volume", "slider", "EFEITOS", "Tiros, habilidades, avisos e as batidas do coração.",
             dict(step=.01, fmt=_pct)),
            ("voice_volume", "slider", "VOZES", "Falas dos heróis e do narrador.", dict(step=.01, fmt=_pct)),
            ("voice_language", "choice", "DUBLAGEM", "Idioma das falas dos heróis.",
             dict(labels={k: v.upper() for k, v in settings.VOICE_LANGUAGES.items()})),
        ],
        "controls": [
            ("mouse_sensitivity", "slider", "SENSIBILIDADE DO MOUSE", "Velocidade da mira em 1ª pessoa.",
             dict(step=.05, fmt=lambda v: f"{v:.2f}×")),
            ("zoom_sensitivity", "slider", "SENSIBILIDADE NO ZOOM", "Fração da sensibilidade usada na luneta da B Cell.",
             dict(step=.05, fmt=lambda v: f"{v:.2f}×")),
            ("invert_y", "toggle", "INVERTER EIXO Y", "Mover o mouse para cima olha para baixo.", {}),
        ],
        "game": [
            ("show_fps", "toggle", "MOSTRAR FPS", "Contador de quadros no canto da tela.", {}),
            ("record_replay", "toggle", "GRAVAR REPLAYS", "Grava as partidas que você hospedar (também na sala).", {}),
            ("map", "choice", "MAPA AO HOSPEDAR", "Mapa inicial das salas que você criar.",
             dict(options=maps_available, labels=lambda k: map_info(k).title.upper())),
        ],
    }


TABS = (("video", "VÍDEO"), ("audio", "ÁUDIO"), ("controls", "CONTROLES"), ("game", "JOGO"))
TAB_ART = {"video": ("macrophage", "Imagem nítida ajuda a achar bactéria escondida!"),
           "audio": ("platelet", "Escuta só! Dá para ouvir o inimigo chegando."),
           "controls": ("killer_t", "Mira firme! Ajuste até cada tiro sair do jeito certo."),
           "game": ("b_cell", "Grave as partidas e estude cada jogada depois.")}
KEYS = (("W A S D", "MOVER"), ("ESPAÇO", "PULAR"), ("SHIFT", "CORRER"), ("LMB", "ATIRAR"),
        ("RMB", "SECUNDÁRIO"), ("Q / E", "HABILIDADES"), ("F", "ESPECIAL"), ("V", "CORPO A CORPO"),
        ("R", "RECARREGAR"), ("G", "CONSTRUIR"), ("F1", "KIT DO HERÓI"), ("ESC", "PAUSA"))


class SettingsScreen(MangaCanvas):
    """Painel de configurações por cima de qualquer tela (abas + linhas de controles)."""

    def __init__(self):
        super().__init__()
        self.visible = False
        self.tab = "video"
        self.sliders = []
        self.drag = None
        self.closed_at = None
        self.opened_at = None

    # -- estado ------------------------------------------------------------------------------
    def open(self):
        self.visible = True
        self.drag = None
        self.controls, self.sliders = [], []
        self.opened_at = self.game.time

    def close(self):
        self.drag = None
        settings.save()
        self.visible = False
        self.closed_at = self.game.time

    def blocking(self):
        return self.visible or self.closed_at == self.game.time

    def reset_tab(self):
        settings.reset([row[0] for row in _rows()[self.tab]])

    # -- entrada -----------------------------------------------------------------------------
    def loop(self):
        if not self.visible or self.opened_at == self.game.time:  # o clique que abriu não vale aqui
            return
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            self.close()
            return
        mouse = rl.get_mouse_position()
        left = rl.MouseButton.MOUSE_BUTTON_LEFT
        if rl.is_mouse_button_pressed(left):
            for rect, spec in self.sliders:
                if rl.check_collision_point_rec(mouse, rect):
                    self.drag = spec
                    break
        if self.drag is not None:
            if rl.is_mouse_button_down(left):
                self.slide(self.drag, mouse.x)
            else:
                self.drag = None
                settings.save()
            return
        super().loop()

    def slide(self, spec, mx):
        rect, key, lo, hi, step = spec
        k = max(0.0, min(1.0, (mx - rect.x) / max(1.0, rect.width)))
        value = round((lo + k * (hi - lo)) / step) * step
        settings.set_value(key, value, save_now=False)

    def cycle(self, key, options, direction):
        options = list(options)
        current = settings.get(key)
        i = options.index(current) if current in options else (-1 if direction > 0 else 0)
        settings.set_value(key, options[(i + direction) % len(options)])

    # -- desenho -----------------------------------------------------------------------------
    def render(self):
        if not self.visible:
            return
        rl.draw_rectangle(0, 0, rl.get_screen_width(), rl.get_screen_height(), color(INK, 205))
        super().render()

    def draw(self):
        rl.clear_background(rl.BLANK)  # só o painel é opaco; o escurecido foi desenhado na tela
        self.sliders = []
        pw = min(self.W - 64, 1180)
        x0, y0, ph = (self.W - pw) / 2, 40, 640
        self.box(x0, y0, pw, ph, WHITE, 3, 7)
        art_w = 268
        self.art_column(x0, y0, art_w, ph)

        # Plaqueta do título (mesmo recurso dos capítulos do menu)
        title = "EXTRA · CONFIGURAÇÕES"
        tw = self.measure(title, 30, "title") + 34
        self.rbox(x0 + 18, y0 - 18, tw, 40, INK, -2)
        self.rbox(x0 + 14, y0 - 22, tw, 40, INK, -2)
        self.rbox(x0 + 17, y0 - 19, tw - 6, 34, YELLOW, -2)
        self.t(title, x0 + 32, y0 - 16, 30, INK, "title", angle=-2)

        cx = x0 + art_w + 34
        cw = x0 + pw - 30 - cx
        self.tabs(cx, y0 + 40)
        rows = _rows()[self.tab]
        y = y0 + 112
        row_h = 66
        for row in rows:
            self.row(row, cx, y, cw, row_h)
            y += row_h
        if self.tab == "controls":
            self.key_sheet(cx, y + 14, cw, y0 + ph - 96 - (y + 14))

        # Rodapé
        fy = y0 + ph - 74
        self.panel(cx, fy - 12, cw, 3, INK)
        self.button("RESTAURAR PADRÕES", cx, fy + 6, 250, self.reset_tab, h=50, size=24)
        self.t("Salvo automaticamente · Esc fecha", cx + 268, fy + 22, 14, MUTED, "body")
        self.button("VOLTAR", cx + cw - 200, fy + 6, 200, self.close, True, h=50, size=28, arrow=True)

    def art_column(self, x, y, w, h):
        hero, line = TAB_ART[self.tab]
        self.panel(x + 3, y + 3, w - 3, h - 6, BLUSH if self.tab == "audio" else PAPER)
        self.scissor(x + 3, y + 3, w - 3, h - 6)
        self.speed_lines(x + w / 2, y + h * .62, 90, 520, INK, 40, 56)
        self.halftone_fade(x + 3, y + h - 230, w - 3, 227, INK, 70)
        self.art(hero, x + 3, y + 3, w - 3, h - 6, h * .86, dy=h * .2)
        self.end_scissor()
        self.panel(x + w, y + 3, 3, h - 6, INK)
        # Balão de fala com a dica da aba
        bx, by, bw = x + 18, y + 54, w - 34
        lines = self._lines(line, bw - 30, 16)
        bh = 26 + len(lines) * 21
        self.bubble(bx, by, bw, bh, WHITE, 18, tail=((bx + bw * .55, by + bh - 2), (bx + bw * .75, by + bh - 2),
                                                      (bx + bw * .78, by + bh + 34)))
        for i, text in enumerate(lines):
            self.t(text, bx + 15, by + 13 + i * 21, 16, INK, "body")

    def _lines(self, value, width, size):
        lines, current = [], ""
        for word in value.split():
            probe = f"{current} {word}".strip()
            if current and self.measure(probe, size, "body") > width:
                lines.append(current)
                current = word
            else:
                current = probe
        return lines + [current] if current else lines

    def tabs(self, x, y):
        for key, label in TABS:
            selected = key == self.tab
            w = self.measure(label, 26, "title") + 44
            hover = self.hovered(x, y, w, 46)
            lift = 4 if selected else (2 if hover else 0)
            self.box(x - lift, y - lift, w, 46, YELLOW if selected else WHITE, 3, 3 + lift)
            self.t(label, x - lift + w / 2, y - lift + 9, 26, INK if selected or hover else MUTED, "title", "c")
            if selected:
                self.panel(x - lift + 14, y - lift + 38, w - 28, 3, RED)
            self.click(x, y, w, 46, lambda k=key: setattr(self, "tab", k))
            x += w + 14

    def row(self, row, x, y, w, h):
        key, kind, label, desc, extra = row
        enabled = extra.get("enabled", lambda: True)()
        ctrl_w = min(400.0, w * .46)
        cx = x + w - ctrl_w
        if self.hovered(x - 10, y, w + 20, h - 6):
            self.panel(x - 10, y + 2, w + 20, h - 10, YELLOW, 70)
        self.t(label, x, y + 10, 20, INK if enabled else MUTED)
        self.fit(desc, x, y + 37, cx - x - 24, 14, tint=MUTED, font="body")
        cy = y + (h - 6) / 2
        if kind == "choice":
            self.selector(key, extra, cx, cy - 21, ctrl_w, 42, enabled)
        elif kind == "toggle":
            self.toggle(key, cx, cy - 21, ctrl_w, 42)
        elif kind == "slider":
            self.slider(key, extra, cx, cy, ctrl_w)
        self.panel(x, y + h - 4, w, 1, GREY)

    def selector(self, key, extra, x, y, w, h, enabled):
        options = extra.get("options", lambda: settings.CHOICES[key])()
        labels = extra.get("labels", {})
        value = settings.get(key)
        text = labels(value) if callable(labels) else labels.get(value, str(value))
        if not enabled:
            self.panel(x, y, w, h, GREY)
            self.outline(x, y, w, h, INK, 3)
            self.t(text, x + w / 2, y + (h - 22) / 2, 22, MUTED, "title", "c")
            return
        self.box(x, y, w, h, WHITE, 3, 3)
        for direction, bx in ((-1, x), (1, x + w - 42)):
            hover = self.hovered(bx, y, 42, h)
            self.panel(bx + 3, y + 3, 36, h - 6, YELLOW if hover else WHITE)
            self.arrow(bx + 21 - 6 * direction, y + h / 2, 14, INK, direction)
            self.click(bx, y, 42, h, lambda d=direction: self.cycle(key, options, d))
        self.panel(x + 42, y + 3, 3, h - 6, INK)
        self.panel(x + w - 45, y + 3, 3, h - 6, INK)
        size = min(24.0, 24 * (w - 120) / max(1.0, self.measure(text, 24, "title")))
        self.t(text, x + w / 2, y + (h - size) / 2, size, INK, "title", "c")
        self.click(x + 42, y, w - 84, h, lambda: self.cycle(key, options, 1))

    def toggle(self, key, x, y, w, h):
        on = bool(settings.get(key))
        self.box(x, y, w, h, WHITE, 3, 3)
        half = (w - 3) / 2
        for state, label, bx in ((False, "DESLIGADO", x), (True, "LIGADO", x + half + 3)):
            chosen = state == on
            hover = not chosen and self.hovered(bx, y, half, h)
            if chosen:
                self.panel(bx + 3, y + 3, half - 3, h - 6, INK if not state else RED)
            elif hover:
                self.panel(bx + 3, y + 3, half - 3, h - 6, YELLOW)
            self.t(label, bx + half / 2, y + (h - 22) / 2, 22, WHITE if chosen else (INK if hover else MUTED),
                   "title", "c")
            self.click(bx, y, half, h, lambda s=state: settings.set_value(key, s))
        self.panel(x + half, y + 3, 3, h - 6, INK)

    def slider(self, key, extra, x, cy, w):
        lo, hi = settings.RANGES[key]
        value = settings.get(key)
        k = (value - lo) / (hi - lo)
        tw = w - 96
        self.box(x, cy - 8, tw, 16, WHITE, 3, 2)
        self.panel(x + 3, cy - 5, max(0.0, (tw - 6) * k), 10, RED)
        kx = x + 3 + (tw - 6) * k
        active = self.drag is not None and self.drag[1] == key
        hover = active or self.hovered(x - 12, cy - 18, tw + 24, 36)
        self.circle(kx + 2, cy + 2, 14, INK)
        self.circle(kx, cy, 14, INK)
        self.circle(kx, cy, 10, YELLOW if hover else WHITE)
        # valor
        self.box(x + w - 82, cy - 19, 82, 38, INK if active else WHITE, 3, 3)
        self.t(extra["fmt"](value), x + w - 41, cy - 13, 24, WHITE if active else INK, "title", "c")
        self.sliders.append((self.rect(x - 12, cy - 18, tw + 24, 36), (self.rect(x + 3, cy, tw - 6, 1), key, lo, hi,
                                                                        extra["step"])))

    def key_sheet(self, x, y, w, h):
        """Referência das teclas (não remapeáveis por enquanto)."""
        if h < 120:
            return
        self.t("TECLAS", x, y, 20)
        self.t("referência rápida", x + self.measure("TECLAS", 20) + 10, y + 3, 14, MUTED, "body")
        cols = 3
        cw = w / cols
        for i, (keys, action) in enumerate(KEYS):
            col, line = i % cols, i // cols
            kx, ky = x + col * cw, y + 34 + line * 38
            kw = self.kb(keys, kx, ky, 28, INK, WHITE, 16)
            self.t(action, kx + kw + 10, ky + 5, 15, INK)
