"""Menus no estilo Mangá: Menu (M1, com nomes/IPs recentes), Lobby (M2: elenco 3 VS 3, herói
animado explicando o kit) com a seleção de personagem embutida (S2) e Resultados.
Cada tela é montada pelo seu Level."""
import math
import socket
import time
import pyray as rl
from . import recents
from . import kit_lines
from .catalog import HEROES, KIT, ICONS, CELLS, BACTERIA, BALANCE, UNLOCKS, can_select, unlocked
from .hud_icons import draw_icon
from .manga_ui import (MangaCanvas, HeroStage, INK, PAPER, WHITE, YELLOW, RED, CYAN, PINK, BLUSH, MINT,
                       GREY, MUTED, BURST_SOFT, ease_out)
from .session import connect, disconnect
from .options import open_settings
from .maps import info as map_info, available as maps_available, next_map, MODES

TEAM_TINT = {CELLS: CYAN, BACTERIA: PINK}
TEAM_PAGE = {CELLS: MINT, BACTERIA: BLUSH}
SLOTS = ("rmb", "q", "e", "f")
KEYS = {"rmb": "RMB", "q": "Q", "e": "E", "f": "F"}


def leave(game):
    disconnect(game)
    game.new_game("menu")


def open_replays(game):
    """Menu -> estante de replays (a cena "replay" sem replay carregado mostra a lista)."""
    game.replay = None
    game.new_game("replay")


def lan_ip():
    """IPv4 desta máquina na rede local (o connect UDP não envia pacotes)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def key_hit(key):
    repeat = getattr(rl, "is_key_pressed_repeat", None)
    return rl.is_key_pressed(key) or bool(repeat and repeat(key))


def clip_segment(p0, p1, polygon):
    """Recorta o segmento p0-p1 no polígono convexo (Cyrus-Beck); None se ficar fora."""
    t0, t1 = 0.0, 1.0
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = len(polygon)
    cx = sum(p[0] for p in polygon) / n
    cy = sum(p[1] for p in polygon) / n
    for i in range(n):
        a, b = polygon[i], polygon[(i + 1) % n]
        nx, ny = b[1] - a[1], a[0] - b[0]
        if nx * (cx - a[0]) + ny * (cy - a[1]) > 0:  # normal apontando para fora
            nx, ny = -nx, -ny
        num = nx * (p0[0] - a[0]) + ny * (p0[1] - a[1])
        den = nx * dx + ny * dy
        if abs(den) < 1e-9:
            if num > 0:
                return None
            continue
        t = -num / den
        if den < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return (p0[0] + dx * t0, p0[1] + dy * t0), (p0[0] + dx * t1, p0[1] + dy * t1)



class MenuScreen(MangaCanvas):
    """M1 · Página de mangá: título, splash do Neutrófilo e formulário com recentes."""

    def __init__(self):
        super().__init__()
        self.recent = recents.load()
        self.name = self.recent["names"][0]["value"] if self.recent["names"] else "Worker 1146"
        self.ip = self.recent["ips"][0]["value"] if self.recent["ips"] else "127.0.0.1"
        self.error = ""

    def open_session(self, host):
        if not self.name.strip():
            self.error = "Digite um nome antes de entrar."
            return
        try:
            connect(self.game, "::" if host else self.ip.strip(), 25765, host, self.name.strip())
        except (OSError, ValueError):
            self.error = "Não foi possível abrir a sala. Confira o IP e a porta 25765."
            return
        recents.push("names", self.name)
        if not host:
            recents.push("ips", self.ip)
        self.game.new_game("lobby")

    def pick(self, field, value):
        setattr(self, field, value)
        self.focus = ""
        self.error = ""

    def forget(self, kind, value):
        self.recent = recents.remove(kind, value)

    def loop(self):
        if self.blocked():
            return
        super().loop()
        if rl.is_key_pressed(rl.KeyboardKey.KEY_TAB):
            self.focus = "ip" if self.focus == "name" else "name"
        if not self.focus:
            if rl.is_key_pressed(rl.KeyboardKey.KEY_ENTER):
                self.open_session(False)
            return
        text = getattr(self, self.focus)
        limit = 48 if self.focus == "ip" else 20
        char = rl.get_char_pressed()
        while char:
            if 32 <= char < 256 and len(text) < limit:
                text += chr(char)
            char = rl.get_char_pressed()
        ctrl = rl.is_key_down(rl.KeyboardKey.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KeyboardKey.KEY_RIGHT_CONTROL)
        if ctrl and rl.is_key_pressed(rl.KeyboardKey.KEY_V):
            pasted = rl.get_clipboard_text()
            pasted = rl.ffi.string(pasted).decode("utf-8", "ignore") if isinstance(pasted, rl.ffi.CData) else str(pasted or "")
            text = (text + pasted.strip().splitlines()[0] if pasted.strip() else text)[:limit]
        if key_hit(rl.KeyboardKey.KEY_BACKSPACE):
            text = text[:-1]
        setattr(self, self.focus, text)
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ENTER):
            if self.focus == "name":
                self.focus = "ip"
            else:
                self.open_session(False)

    # -- partes ----------------------------------------------------------------------------
    def field(self, field, label, x, y, w):
        focused = self.focus == field
        self.t(label, x, y - 23, 14, INK)
        if focused:
            self.panel(x + 5, y + 5, w, 48, YELLOW)
            self.outline(x + 5, y + 5, w, 48, INK, 2)
        self.box(x, y, w, 48, WHITE, 3, 0)
        value = getattr(self, field)
        caret = "|" if focused and int(time.perf_counter() * 2) % 2 == 0 else ""
        self.fit(value + caret, x + 14, y + 11, w - 28, 21, font="body")
        self.click(x, y, w, 48, lambda: setattr(self, "focus", field))

    def recent_row(self, kind, field, x, y, width):
        entries = self.recent[kind]
        if not entries:
            self.t("Os " + ("nomes" if kind == "names" else "IPs") + " usados aparecem aqui.", x, y + 7, 14, MUTED, "body")
            return
        self.t("RECENTES", x, y + 8, 13, MUTED)
        cx = x + self.measure("RECENTES", 13) + 12
        for entry in entries:
            value = entry["value"]
            note = ""
            if kind == "ips":
                note = "local" if value in ("127.0.0.1", "localhost") else recents.when(entry["t"])
            size_guess = 12 + self.measure(value, 15) + (self.measure(" · " + note, 13, "body") if note else 0) + 32
            if cx + size_guess > x + width:
                break
            current = getattr(self, field) == value
            cx += self.chip(value, cx, y, lambda v=value: self.pick(field, v), lambda v=value: self.forget(kind, v),
                            YELLOW if current else WHITE, note) + 7

    def splash(self, now, left):
        top, right, bottom = self.top + 22, self.W - 22, self.bottom - 24
        slant = 65
        pts = [(left + slant, top), (right, top), (right, bottom), (left, bottom)]
        self.poly([(px + 5, py + 5) for px, py in pts], INK)
        self.poly(pts, WHITE)
        self.scissor(left, top, right - left, bottom - top)
        cx, cy = (left + right) / 2 + 80, top + (bottom - top) * .46
        self.speed_lines(cx, cy, 175, max(820, right - left), INK, 95, 80, spin=now * .015)
        self.halftone_fade(left, bottom - 200, right - left, 200, INK, 80)
        art_h = (bottom - top) * 1.04
        self.art("neutrophil", left, top, right - left, bottom - top, art_h, dx=110, dy=26 + math.sin(now * 2) * 6)
        self.tri((left - 2, top - 2), (left + slant, top - 2), (left - 2, bottom), PAPER)
        self.end_scissor()
        for a, b in zip(pts, pts[1:] + pts[:1]):
            self.seg(a[0], a[1], b[0], b[1], 4, INK)
            self.circle(a[0], a[1], 2, INK)
        # Onomatopeia, legenda e plaqueta
        self.t("ZAN!", right - 190, top + 50, 76, YELLOW, "title", stroke=3, shadow=5, angle=10)
        cap = ("Um corte limpo.", "Nenhuma bactéria passa daqui.")
        cw = max(self.measure(c, 15, "body") for c in cap) + 28
        self.rbox(left + 100, top + 44, cw, 58, INK, -2)
        self.rbox(left + 96, top + 40, cw, 58, INK, -2)
        self.rbox(left + 99, top + 43, cw - 6, 52, WHITE, -2)
        self.t(cap[0], left + 111, top + 51, 15, font="body", angle=-2)
        self.t(cap[1], left + 112, top + 71, 15, font="body", angle=-2)
        self.panel(left + 40, bottom - 96, 278, 44, INK)
        self.t("NEUTRÓFILO 1146", left + 54, bottom - 90, 33, WHITE, "title")
        tag = "PRIMEIRA LINHA DE DEFESA"
        self.box(left + 40, bottom - 44, self.measure(tag, 14) + 22, 26, WHITE, 3, 3)
        self.t(tag, left + 51, bottom - 40, 14)
        self.button("CONFIGURAÇÕES", right - 278, bottom - 152, 252, lambda: open_settings(self.game), h=54,
                    size=26)
        self.button("ASSISTIR REPLAYS", right - 278, bottom - 82, 252, lambda: open_replays(self.game), h=58,
                    size=27, arrow=True)

    def draw(self):
        now = time.perf_counter()
        self.page(PAPER)
        col = 560 + min(160, (self.W - 1280) * .25)  # coluna do formulário cresce um pouco em telas largas
        self.splash(now, 22 + col + 22)

        # Quadro A: título
        self.box(22, 22, col, 286)
        self.halftone_fade(25, 200, col - 6, 105, INK, 45)
        self.ring(61, 56, 5, 11, 0, 360, RED)
        self.t("O CORPO É O SEU CAMPO DE BATALHA", 80, 46, 15)
        self.t("CELLS", 48, 70, 108, INK, "title")
        self.t("AT WORK!", 48, 160, 108, RED, "title", stroke=3, shadow=5)
        x = 50
        for tag in ("3v3 EM REDE", "8 HERÓIS", "1 CORPO VIVO"):
            w = self.measure(tag, 14) + 22
            self.panel(x, 266, w, 26, INK)
            self.t(tag, x + 11, 270, 14, WHITE)
            x += w + 8

        # Quadro C: formulário com recentes
        self.box(22, 326, col, 370)
        self.rbox(16, 312, 300, 32, INK, -2)
        self.rbox(12, 308, 300, 32, INK, -2)
        self.rbox(15, 311, 294, 26, YELLOW, -2)
        self.t("CAPÍTULO 1 · APRESENTE-SE!", 26, 315, 21, INK, "title", angle=-2)
        fw = col - 52
        self.field("name", "SEU NOME", 48, 376, fw)
        self.recent_row("names", "name", 48, 431, fw)
        self.field("ip", "IP DO SERVIDOR", 48, 496, fw)
        self.recent_row("ips", "ip", 48, 551, fw)
        bw = (fw - 14) / 2
        self.button("CRIAR SALA!", 48, 598, bw, lambda: self.open_session(True), True, h=58, size=30)
        self.button("ENTRAR NA REDE", 62 + bw, 598, bw, lambda: self.open_session(False), h=58, size=28, arrow=True)
        if self.error:
            self.fit(self.error, 48, 666, fw, 14, tint=RED)
        else:
            self.fit("Porta 25765 · Bairro Arterial · clique numa etiqueta para preencher", 48, 667, fw, 14,
                     tint=MUTED, font="body")


class LobbyScreen(MangaCanvas):
    """M2 · elenco 3 VS 3 + herói animado explicando o kit; "Trocar herói" abre a seleção (S2)."""

    LEFT = 96  # depois da lombada

    def __init__(self, picking=False):
        super().__init__()
        self.picking = picking
        self.candidate = None
        self.hover_hero = None
        self.stage = HeroStage()
        self.stage_box = None
        self.stage_hero = None
        self.shown = None
        self.changed = time.perf_counter()
        self.room = None

    def on_destroy(self):
        self.stage.unload()
        super().on_destroy()

    @property
    def R(self):
        return self.W - 22

    # -- estado ----------------------------------------------------------------------------
    @property
    def net(self):
        return self.game.session

    def local(self):
        return self.net.roster.value.get(self.net.local_slot)

    def open_picker(self):
        local = self.local()
        if local:
            self.picking = True
            self.candidate = local["hero"]

    def close_picker(self):
        self.picking = False
        self.candidate = None

    def availability(self, key):
        """(pode escolher, motivo) para o herói ``key`` no lobby."""
        net = self.net
        roster = net.roster.value
        local = roster.get(net.local_slot)
        hero = HEROES[key]
        if local and local["hero"] == key:
            return True, "ATUAL"
        if not unlocked(key, 0):
            return False, f"BLOQUEADO · {BALANCE[UNLOCKS[key]]}"
        if not can_select(key, hero.team, roster, exclude=net.local_slot):
            return False, "OCUPADO"
        if local and local["team"] != hero.team and sum(p["team"] == hero.team for p in roster.values()) >= 3:
            return False, "EQUIPE CHEIA"
        return True, ""

    def confirm(self, key):
        local = self.local()
        ok, _ = self.availability(key)
        if not ok:
            return
        if local and local["hero"] != key:
            self.net.choose(key)
        self.close_picker()

    def loop(self):
        super().loop()
        if self.picking and not self.blocked():
            if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
                self.close_picker()
            elif rl.is_key_pressed(rl.KeyboardKey.KEY_ENTER) and self.candidate:
                self.confirm(self.candidate)
        self.stage.warm(HEROES)
        if self.stage_box and self.stage_hero:
            _, _, w, h = self.stage_box
            k = self.scale * self.ss  # o palco também sai supersampleado
            self.stage.update(self.stage_hero, w * k, h * k)

    # -- partes ----------------------------------------------------------------------------
    def spine(self, count):
        self.panel(0, self.top, 72, self.bottom - self.top, INK)
        self.ring(36, 34, 7, 14, 0, 360, RED)
        self.circle(36, 34, 7, WHITE)
        label = "CAP. 2 · OPERAÇÃO ABRASION"
        w = self.measure(label, 30, "title")
        self.t(label, 52, 360 - w / 2, 30, WHITE, "title", angle=90)
        self.panel(10, 664, 52, 34, YELLOW)
        self.t(f"{count}/6", 36, 669, 24, INK, "title", "c")

    def record_toggle(self, right, y):
        """Anfitrião: caixa "Gravar replay"; clientes veem só o aviso de que a partida será gravada."""
        net = self.net
        on = bool(net.recording.value)
        pulse = .5 + .5 * math.sin(time.perf_counter() * 5)
        if not net.manager.is_server:
            if on:
                label = "PARTIDA SERÁ GRAVADA"
                w = self.measure(label, 13) + 40
                self.panel(right - w, y + 2, w, 28, RED)
                self.circle(right - w + 15, y + 16, 5, WHITE, int(140 + 115 * pulse))
                self.t(label, right - w + 27, y + 8, 13, WHITE)
            return
        label = "GRAVAR REPLAY"
        w = 44 + self.measure(label, 21, "title") + (46 if on else 14)
        x = right - w
        hover = self.hovered(x, y, w, 34)
        self.box(x, y, w, 34, YELLOW if on or hover else WHITE, 3, 3)
        self.box(x + 9, y + 7, 20, 20, WHITE, 2, 0)
        if on:
            self.seg(x + 12, y + 17, x + 18, y + 23, 4, RED)
            self.seg(x + 17, y + 23, x + 27, y + 9, 4, RED)
        self.t(label, x + 38, y + 5, 21, INK, "title")
        if on:
            cx = x + w - 22
            self.circle(cx, y + 17, 9, INK)
            self.circle(cx, y + 17, 6, RED)
            self.ring(cx, y + 17, 9, 9 + 4 * pulse, 0, 360, RED, int(200 * (1 - pulse)))
        self.click(x, y, w, 34, lambda: net.set_recording(not on))

    def map_picker(self, x, y, right):
        """Mapa da partida: o anfitrião troca com as setas; os clientes só leem."""
        net = self.net
        current = map_info(net.map_key)
        host = net.manager.is_server
        options = maps_available()
        cycle = host and len(options) > 1
        title = current.title.upper()
        sub = MODES[current.mode]["objective"]
        tw = self.measure(title, 24, "title")
        sw = self.measure(sub, 13)
        if x + tw + sw + (96 if cycle else 40) > right:
            sub, sw = "", -10
        w = tw + sw + (96 if cycle else 40)
        self.panel(x + 4, y + 4, w, 34, INK)
        self.panel(x, y, w, 34, RED)
        cx = x + (34 if cycle else 12)
        if cycle:
            for side, bx in ((-1, x + 4), (1, x + w - 30)):
                hover = self.hovered(bx, y + 4, 26, 26)
                self.panel(bx, y + 4, 26, 26, YELLOW if hover else WHITE)
                mx, my = bx + 13, y + 17
                self.tri((mx - 6 * side, my - 7), (mx - 6 * side, my + 7), (mx + 6 * side, my), INK)
                self.click(bx, y + 4, 26, 26, lambda d=side: net.set_map(next_map(net.map_key, d)))
        self.t(title, cx, y + 3, 24, WHITE, "title")
        if sub:
            self.t(sub, cx + tw + 10, y + 10, 13, YELLOW)

    def card(self, slot, x, y, w, h, picking):
        net = self.net
        p = net.roster.value.get(slot)
        if p is None:
            self.box(x, y, w, h, WHITE, 3, 4, dashed=True)
            self.halftone_rect(x + 3, y + 3, w - 6, h - 6, INK, 70)
            self.t("?", x + w / 2, y + h / 2 - 70, 80, WHITE, "title", "c", stroke=3)
            tw = self.measure("VAGA ABERTA", 14) + 20
            self.box(x + (w - tw) / 2, y + h / 2 + 20, tw, 28, WHITE, 2, 0)
            self.t("VAGA ABERTA", x + w / 2, y + h / 2 + 24, 14, INK, align="c")
            return
        hero, team = p["hero"], p["team"]
        mine = slot == net.local_slot
        if mine:
            self.panel(x + 1, y + 1, w + 10, h + 10, INK)
            self.panel(x - 5, y - 5, w + 10, h + 10, YELLOW)
            self.box(x, y, w, h, WHITE if team == CELLS else BLUSH, 3, 0)
        else:
            self.box(x, y, w, h, WHITE if team == CELLS else BLUSH)
        big = team == CELLS
        img_h = (330 if big else 230) * h / 270
        if mine and picking:
            self.art(hero, x + 3, y + 3, w - 6, h - 6, img_h, dy=8 if big else 20, tint=(150, 150, 150), alpha=120)
            wob = math.sin(time.perf_counter() * 5) * 3
            self.t("?", x + w / 2, y + 50, 76, WHITE, "title", "c", stroke=3, angle=wob)
        else:
            self.art(hero, x + 3, y + 3, w - 6, h - 6, img_h, dy=8 if big else 20)
        band = YELLOW if mine else INK
        self.panel(x + 3, y + h - 52, w - 6, 49, band)
        name = p["name"] + (" · você" if mine and picking else "")
        self.fit(name, x + 12, y + h - 48, w - 22, 17, tint=INK if mine else WHITE)
        sub = "ESCOLHENDO…" if mine and picking else kit_lines.name(hero).upper()
        self.fit(sub, x + 12, y + h - 25, w - 22, 14, tint=INK if mine else TEAM_TINT[team])
        if mine and not picking:
            self.rbox(x + w - 64, y + 10, 56, 26, INK, 6)
            self.rbox(x + w - 62, y + 12, 52, 22, RED, 6)
            self.t("VOCÊ", x + w - 53, y + 12, 18, WHITE, "title", angle=6)
        if p.get("bot"):
            self.panel(x + 8, y + 8, 40, 22, INK)
            self.t("BOT", x + 14, y + 11, 14, WHITE)

    def roster(self, picking):
        h = 250 if picking else 270
        y = 58
        avail = self.R - self.LEFT
        w = min(230.0, (avail - 86 - 2 * 12 - 4 * 12) / 6)
        total = 6 * w + 4 * 12 + 2 * 12 + 86
        x = self.LEFT + (avail - total) / 2
        for slot in range(3):
            self.card(slot, x, y, w, h, picking)
            x += w + 12
        self.burst(x, y + h / 2 - 60, 86, 120, RED, BURST_SOFT, border=6, shadow=4)
        self.t("VS", x + 43, y + h / 2 - 22, 38, WHITE, "title", "c", stroke=1.5)
        x += 98
        for slot in range(3, 6):
            self.card(slot, x, y, w, h, picking)
            x += w + 12

    def cut_in(self, hero, x, y, w, h, fill):
        pts = [(x, y + h * .06), (x + w, y), (x + w * .92, y + h), (x, y + h * .96)]
        self.poly([(px + 5, py + 5) for px, py in pts], INK)
        self.poly(pts, fill)
        k = -h * .36
        while k < w:
            seg = clip_segment((x + k, y + h), (x + k + h * .36, y), pts)
            if seg:
                (a, b) = seg
                self.seg(a[0], a[1], b[0], b[1], 3, WHITE, 180)
            k += 17
        # Maior retângulo dentro do quadro inclinado: o boneco nunca vaza pela borda de cima.
        self.stage_box = (x + 4, y + h * .06 + 4, w * .92 - 8, h * .9 - 8)
        self.stage_hero = hero
        self.stage.draw(self, *self.stage_box)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            self.seg(a[0], a[1], b[0], b[1], 4, INK)
            self.circle(a[0], a[1], 2, INK)
        name = kit_lines.name(hero).upper()
        nw = self.measure(name, 24, "title") + 22
        self.panel(x + 10, y + h - 46, nw, 32, INK)
        self.t(name, x + 21, y + h - 42, 24, WHITE, "title")

    def kit_bubbles(self, hero, x, y, w, row_h, size=16):
        now = time.perf_counter()
        if hero != self.shown:
            self.shown, self.changed = hero, now
        col_w = (w - 16) / 2
        leading = 1.25
        max_lines = max(1, int((row_h - 44) / (size * leading)))
        for i, slot in enumerate(SLOTS):
            bx = x + (i % 2) * (col_w + 16)
            by = y + (i // 2) * (row_h + 10)
            e = ease_out((now - self.changed - i * .1) / .35)
            if e <= 0:
                continue
            alpha = int(255 * e)
            by += (1 - e) * 12
            special = slot == "f"
            self.bubble(bx, by, col_w, row_h, YELLOW if special else WHITE, 20, alpha=alpha)
            kw = self.kb(KEYS[slot], bx + 14, by + 12, 30, RED if special else INK)
            title, text = kit_lines.line(hero, slot)
            icon = ICONS.get(KIT.get(hero, {}).get(slot, ("",))[0])
            tx = bx + 14 + kw + 10
            if icon:
                draw_icon(self, icon, bx + col_w - 32, by + 28, 28, INK)
            self.fit((title + "!") if special else title, tx, by + 13, col_w - (tx - bx) - 56, 22, font="title",
                     alpha=alpha)
            self.wrap(text, tx, by + 40, col_w - (tx - bx) - 18, size, INK, alpha=alpha, max_lines=max_lines,
                      leading=leading)

    def passive_line(self, hero, x, y, w, h=40):
        self.circle(x + 6, y + h / 2 + 8, 4, WHITE)
        self.ring(x + 6, y + h / 2 + 8, 3, 5, 0, 360, INK)
        self.circle(x + 18, y + h / 2 + 2, 6, WHITE)
        self.ring(x + 18, y + h / 2 + 2, 5, 7, 0, 360, INK)
        bx = x + 30
        self.bubble(bx, y, w - 30, h, WHITE, h / 2, shadow=0, border=2)
        p_name, p_text = kit_lines.line(hero, "passive")
        l_name, l_text = kit_lines.line(hero, "lmb")
        cx = bx + 18
        cx += self.t(f"PASSIVA · {p_name}", cx, y + h / 2 - 10, 20, INK, "title") + 10
        right = f"{l_name}: {l_text}"
        rw = min(320, self.measure(right, 14, "body"))
        lx = bx + w - 30 - 18 - rw
        self.kb("LMB", lx - 50, y + h / 2 - 12, 24)
        self.fit(right, lx, y + h / 2 - 9, rw, 14, font="body")
        self.fit(p_text, cx, y + h / 2 - 9, lx - 50 - 16 - cx, 14, font="body")

    def footer(self, local):
        net = self.net
        roster = net.roster.value
        y, L, R = 654, self.LEFT, self.R
        self.button("TROCAR HERÓI", L, y, 196, self.open_picker, True, local is not None, h=50, size=23)
        self.button("SAIR", L + 210, y, 104, lambda: leave(self.game), h=50, size=23)
        if net.manager.is_server:
            missing = 6 - len(roster)
            label = "INICIAR 3v3" if missing <= 0 else f"INICIAR 3v3 · FALTAM {missing}"
            self.button(label, R - 256, y, 256, lambda: net.start(False), True, missing <= 0, h=50, size=21,
                        arrow=missing <= 0)
            self.button("TREINO + BOTS", R - 256 - 14 - 196, y, 196, lambda: net.start(True), h=50, size=23)
            middle = (L + 330, R - 256 - 14 - 196 - 16)
        else:
            hint = "O anfitrião inicia a partida."
            self.t(hint, R, y + 15, 16, MUTED, "body", align="r")
            middle = (L + 330, R - self.measure(hint, 16, "body") - 24)
        text = net.error or (f"Dica: {kit_lines.tip(local['hero'])}" if local else "")
        if text:
            self.wrap(text, middle[0], y + 6, middle[1] - middle[0], 15, RED if net.error else INK, max_lines=2,
                      leading=1.25)

    def showcase(self, local):
        L, R = self.LEFT, self.R
        if local is None:
            self.stage_hero = None
            self.bubble(L + 276, 420, 540, 96, WHITE, 26, tail=((L + 324, 510), (L + 364, 510), (L + 304, 546)))
            self.t("Conectando à sala…", L + 304, 442, 30, INK, "title")
            self.t("Assim que o anfitrião aceitar, seu herói aparece aqui.", L + 304, 478, 16, font="body")
            return
        hero = local["hero"]
        self.cut_in(hero, L, 360, 250, 266, YELLOW)
        # Em telas largas os balões ficam compridos: o texto cresce um pouco para preenchê-los.
        self.kit_bubbles(hero, L + 276, 352, R - L - 276, 106, size=16 + min(2.0, (self.W - 1280) / 200))
        self.passive_line(hero, L + 276, 586, R - L - 276)

    def picker(self, local):
        L, R = self.LEFT, self.R
        focus = self.hover_hero or self.candidate or local["hero"]
        team = HEROES[focus].team
        self.cut_in(focus, L, 330, 236, 250, TEAM_TINT[team])
        hp = HEROES[focus]
        tag = f"{kit_lines.role(focus).upper()} · {hp.health} HP"
        tw = self.measure(tag, 13) + 18
        self.box(L + 10, 330 + 250 - 80, tw, 24, WHITE, 2, 2)
        self.t(tag, L + 19, 330 + 250 - 76, 13)
        kx = L + 260
        lw = self.measure("PRÉVIA DO KIT", 13) + 18
        self.panel(kx, 330, lw, 24, INK)
        self.t("PRÉVIA DO KIT", kx + 9, 334, 13, WHITE)
        p_name, p_text = kit_lines.line(focus, "passive")
        l_name, l_text = kit_lines.line(focus, "lmb")
        self.fit(f"Passiva · {p_name}: {p_text}   ·   LMB {l_name}: {l_text}", kx + lw + 12, 333, R - kx - lw - 12, 15,
                 font="body")
        self.kit_bubbles(focus, kx, 364, R - kx, 84, size=15)
        self.fit(f"Dica: {kit_lines.tip(focus)}", kx, 552, R - kx, 15, tint=MUTED, font="body")

        # Tira de retratos
        self.hover_hero = None
        x = L
        for group, title in ((CELLS, "DEFESA IMUNE"), (BACTERIA, "INVASÃO BACTERIANA")):
            self.t(title, x, 584, 13, INK)
            for key in [k for k, h in HEROES.items() if h.team == group]:
                self.frame(key, x, 606, focus)
                x += 108
            if group == CELLS:
                self.panel(x + 2, 606, 3, 100, INK)
                x += 17
        strip_end = x - 8

        ok, reason = self.availability(focus)
        bw, bh = 176, 88
        bx, by = strip_end + max(16, (R - strip_end - bw) / 2), 588
        hover = ok and self.hovered(bx, by, bw, bh)
        grow = 4 if hover else 0
        self.burst(bx - grow, by - grow, bw + 2 * grow, bh + 2 * grow, YELLOW if ok else GREY, BURST_SOFT, border=8,
                   shadow=4)
        label = ("MANTER!" if reason == "ATUAL" else "ESCOLHER!") if ok else "INDISPONÍVEL"
        self.fit(label, bx + bw / 2, by + 29, 116, 28, font="title", align="c")
        if ok:
            self.click(bx, by, bw, bh, lambda h=focus: self.confirm(h))
        self.button("× CANCELAR", bx + (bw - 140) / 2, 682, 140, self.close_picker, h=28, size=17)

    def frame(self, key, x, y, focus):
        ok, reason = self.availability(key)
        team = HEROES[key].team
        focused = key == focus
        if self.hovered(x, y, 100, 100):
            self.hover_hero = key
        lift = 8 if focused else (4 if self.hovered(x, y, 100, 100) else 0)
        y -= lift
        locked = reason.startswith("BLOQUEADO")
        fill = YELLOW if focused else GREY if locked else TEAM_PAGE[team] if ok else (238, 238, 238)
        self.box(x, y, 100, 100, fill, 4 if focused else 3, 4 if focused else 3)
        if locked:
            self.halftone_rect(x + 3, y + 3, 94, 94, (120, 120, 120), 255)
        big = team == CELLS
        tint, alpha = ((80, 80, 80), 255) if locked else ((255, 255, 255), 255 if ok else 115)
        self.art(key, x + 3, y + 3, 94, 94, 220 if big else 110, dy=4, tint=tint, alpha=alpha)
        label = kit_lines.name(key) if ok or not reason else reason
        band = RED if focused else (85, 85, 85) if not ok else INK
        self.panel(x + 3, y + 76, 94, 21, band)
        self.fit(label.upper(), x + 50, y + 78, 88, 16, tint=WHITE, font="title", align="c")
        if reason == "ATUAL":
            self.panel(x + 6, y + 6, 52, 20, INK)
            self.t("ATUAL", x + 11, y + 8, 13, YELLOW)
        if locked:
            cx, cy = x + 50, y + 38
            self.round(cx - 11, cy - 4, 22, 18, 3, WHITE)
            self.ring(cx, cy - 4, 5, 8, 180, 360, WHITE)
        self.click(x, y, 100, 100, lambda h=key: setattr(self, "candidate", h))

    def draw(self):
        net = self.net
        roster = net.roster.value
        local = self.local()
        if local is None:
            self.picking = False
        self.page(WHITE)
        self.halftone_rect(72, self.top, self.W - 72, (330 if self.picking else 362) - self.top, INK, 36)
        self.spine(sum(not p["bot"] for p in roster.values()))
        if self.room is None:
            self.room = lan_ip() if net.manager.is_server else net.manager.ip
        tag = f"SALA {self.room} · PORTA {net.manager.port}" + (" · VOCÊ É O ANFITRIÃO" if net.manager.is_server else "")
        tw = self.measure(tag, 13) + 22
        self.panel(self.R - tw, 16, tw, 28, INK)
        self.t(tag, self.R - tw + 11, 21, 13, WHITE)
        self.record_toggle(self.R - tw - 14, 14)
        count = len(roster)
        if self.picking:
            story = f"{local['name']} está escolhendo um herói…"
        else:
            story = f"{count} de 6 combatentes a caminho de"
        sw = self.measure(story, 22, "title") + 28
        self.rbox(100, 18, sw, 34, INK, -1)
        self.rbox(96, 14, sw, 34, INK, -1)
        self.rbox(99, 17, sw - 6, 28, YELLOW, -1)
        self.t(story, 110, 20, 22, INK, "title", angle=-1)
        self.map_picker(96 + sw + 12, 14, self.R - tw - 14 - 230)
        self.roster(self.picking)
        if self.picking:
            self.picker(local)
        else:
            self.hover_hero = None
            self.showcase(local)
            self.footer(local)


class ResultScreen(MangaCanvas):
    """Relatório da operação no mesmo estilo."""

    def draw(self):
        net = self.game.session
        data = net.result or {"state": {}, "actors": {}}
        state = data["state"]
        winner = state.get("winner", CELLS)
        now = time.perf_counter()
        self.page(PAPER)
        R = self.W - 22
        # Splash do lado vencedor
        hero = next((p["hero"] for p in net.roster.value.values() if p["team"] == winner), "neutrophil")
        right, top, bottom = R, 22, 300
        left = right - 438 - min(220, (self.W - 1280) * .4)
        self.box(left, top, right - left, bottom - top, WHITE, 3, 5)
        self.scissor(left + 3, top + 3, right - left - 6, bottom - top - 6)
        self.speed_lines((left + right) / 2, 160, 70, 420 + (right - left) / 2, INK, 90, 60, spin=now * .02)
        self.art(hero, left, top, right - left, bottom - top, 520 if HEROES[hero].team == CELLS else 300, dy=10)
        self.end_scissor()
        self.outline(left, top, right - left, bottom - top, INK, 3)

        title = "INFECÇÃO CONTIDA!" if winner == CELLS else "INFECÇÃO ESTABELECIDA!"
        self.fit(title, 46, 40, left - 46 - 24, 74, tint=TEAM_TINT[winner] if winner == CELLS else RED, font="title",
                 stroke=3, shadow=5)
        mode = state.get("mode", "escort")
        sub = {"escort": "Resultado decidido por escolta, colônias e infecção.",
               "convoy": "Resultado decidido pelo comboio, pelas valvas e pelas colônias.",
               "training": "Resultado decidido pela formatura, pelas colônias e pela infecção."}.get(mode, "")
        self.rbox(46, 132, self.measure(sub, 16, "body") + 24, 32, YELLOW, -1)
        self.t(sub, 58, 138, 16, font="body", angle=-1)
        elapsed = int(state.get("elapsed", 0))
        stats = [("TEMPO", f"{elapsed // 60:02}:{elapsed % 60:02}"), ("ANTÍGENO", f"{int(state.get('recognition', 0))}%"),
                 (MODES.get(mode, MODES["escort"])["result"],
                  f"{int(state.get('escort', 0))}/{int(state.get('escort_total', 0))}" if mode == "training" else
                  f"{int(100 * state.get('escort', 0) / max(1, state.get('escort_total', 1)))}%"),
                 ("COLÔNIAS", str(len(state.get('colonies', []))))]
        sw = min(186.0, (left - 46 - 24) / 4)
        for i, (label, value) in enumerate(stats):
            x = 46 + i * sw
            self.box(x, 186, sw - 16, 94)
            self.t(label, x + 14, 195, 14)
            self.t(value, x + 14, 216, 48, INK, "title")

        for i, (slot, player) in enumerate(sorted(net.roster.value.items())):
            y = 318 + i * 50
            a = data["actors"].get(slot, {})
            team = player["team"]
            self.box(46, y, R - 46, 42, WHITE if team == CELLS else BLUSH, 3, 3)
            self.art(player["hero"], 49, y + 3, 60, 36, 150 if team == CELLS else 80, dy=4)
            self.fit(player["name"], 124, y + 10, 300, 19)
            self.t(kit_lines.name(player["hero"]).upper(), 440, y + 8, 25, INK, "title")
            tag = "CÉLULAS" if team == CELLS else "BACTÉRIAS"
            tw = self.measure(tag, 14) + 18
            self.panel(R - 460, y + 9, tw, 24, INK)
            self.t(tag, R - 451, y + 12, 14, TEAM_TINT[team])
            self.t(f"{a.get('kills', 0)} K  /  {a.get('deaths', 0)} D", R - 18, y + 6, 30, INK, "title", "r")
        self.button("VOLTAR AO MENU", 46, 640, 300, lambda: leave(self.game), True, h=54, size=26)
        saved = getattr(self.game, "last_replay", None)
        if saved is not None and net.manager.is_server:
            from .replay_screens import open_from_file
            self.button("ASSISTIR REPLAY", 362, 640, 270, lambda: open_from_file(self.game, saved), h=54, size=26,
                        arrow=True)
            note = "Replay salvo na pasta replays/"
            self.rbox(648, 652, self.measure(note, 15, "body") + 24, 30, YELLOW, -1)
            self.t(note, 660, 657, 15, font="body", angle=-1)
