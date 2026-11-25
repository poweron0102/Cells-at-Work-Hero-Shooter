"""Telas do replay no estilo Mangá: a estante de replays (lista) e os controles da reprodução
desenhados por cima da arena (linha do tempo, velocidade, quadros dos jogadores e câmera)."""
import math
import os
import time
from datetime import datetime
import pyray as rl
from . import kit_lines
from .catalog import HEROES, CELLS
from .manga_ui import (MangaCanvas, INK, PAPER, WHITE, YELLOW, RED, CYAN, PINK, BLUSH, MINT, GREY, MUTED,
                       BURST_SOFT, ease_out)
from .replay import (REPLAY_DIR, SPEEDS, close_replay, delete_replay, list_replays, load_replay, open_replay)

TEAM_TINT = {CELLS: CYAN}
TEAM_PAGE = {CELLS: MINT}
TEAM_BAR = {CELLS: (32, 168, 156)}
BACTERIA_BAR = (226, 70, 104)
MONTHS = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")


def clock_text(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60:02}:{seconds % 60:02}"


def team_of(slot, player=None):
    if player and player.get("team"):
        return player["team"]
    return CELLS if int(slot) < 3 else "bacteria"


def page_tint(team):
    return TEAM_PAGE.get(team, BLUSH)


def bar_tint(team):
    return TEAM_BAR.get(team, BACTERIA_BAR)


def accent(team):
    return TEAM_TINT.get(team, PINK)


def size_text(size):
    if size >= 1 << 20:
        return f"{size / (1 << 20):.1f} MB".replace(".", ",")
    return f"{max(1, size // 1024)} KB"


def created(meta):
    try:
        return datetime.fromisoformat(meta.get("created", ""))
    except ValueError:
        return None


def open_from_file(game, path):
    """Carrega e entra na reprodução (levanta NewGame); devolve a mensagem de erro se falhar."""
    try:
        data = load_replay(path)
    except Exception as error:  # arquivo corrompido, de outra versão ou que não é replay
        return f"Não foi possível abrir este replay: {error}"
    if not data.chunks:
        return "Este replay está vazio."
    open_replay(game, data)
    game.new_game("replay")
    return ""


class ReplayLibrary(MangaCanvas):
    """CAP. EXTRA · a estante com as partidas gravadas."""

    ROW = 96

    def __init__(self):
        super().__init__()
        self.entries = list_replays()
        self.scroll = 0.0
        self.confirm = None
        self.error = ""

    @property
    def R(self):
        return self.W - 22

    def loop(self):
        super().loop()
        wheel = rl.get_mouse_wheel_move()
        if wheel:
            self.scroll = max(0.0, self.scroll - wheel * self.ROW * .6)
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            self.game.new_game("menu")

    def play(self, meta):
        self.error = open_from_file(self.game, meta["path"])

    def remove(self, meta):
        if self.confirm != meta["path"]:
            self.confirm = meta["path"]
            return
        delete_replay(meta["path"])
        self.confirm = None
        self.entries = list_replays()

    def open_folder(self):
        REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(REPLAY_DIR.resolve())  # Windows; noutros sistemas só não abre
        except (AttributeError, OSError):
            self.error = f"Os replays ficam em {REPLAY_DIR.resolve()}"

    # -- partes ----------------------------------------------------------------------------
    def spine(self):
        self.panel(0, self.top, 72, self.bottom - self.top, INK)
        self.ring(36, 34, 7, 14, 0, 360, RED)
        self.circle(36, 34, 7, WHITE)
        label = "CAP. EXTRA · SALA DE REPLAYS"
        w = self.measure(label, 30, "title")
        self.t(label, 52, 360 - w / 2, 30, WHITE, "title", angle=90)
        self.panel(10, 664, 52, 34, YELLOW)
        self.t(str(len(self.entries)), 36, 669, 24, INK, "title", "c")

    def header(self, now):
        L, R = 96, self.R
        top, h = 22, 156
        self.box(L, top, R - L, h, WHITE)
        self.scissor(L + 3, top + 3, R - L - 6, h - 6)
        cx = R - 230
        self.speed_lines(cx, top + h / 2, 60, 560, INK, 80, 70, spin=now * .02)
        self.halftone_fade(L + 3, top + h - 70, R - L - 6, 67, INK, 50)
        self.art("killer_t", cx - 190, top + 3, 380, h - 6, 430, dy=-18 + math.sin(now * 2) * 4)
        self.end_scissor()
        self.outline(L, top, R - L, h, INK, 3)
        self.t("REPLAYS", L + 26, top + 8, 104, RED, "title", stroke=3, shadow=5)
        self.t("REVEJA CADA CORTE, CADA TIRO, CADA INFECÇÃO", L + 30, top + 122, 15)
        self.t("REC!", R - 120, top + 18, 58, YELLOW, "title", stroke=3, shadow=4, angle=12)
        cap = "CAPÍTULO EXTRA · A BATALHA EM REPRISE"
        cw = self.measure(cap, 21, "title") + 30
        self.rbox(L + 14, top + h - 2, cw, 32, INK, -2)
        self.rbox(L + 10, top + h - 6, cw, 32, INK, -2)
        self.rbox(L + 13, top + h - 3, cw - 6, 26, YELLOW, -2)
        self.t(cap, L + 26, top + h - 1, 21, INK, "title", angle=-2)

    def lineup(self, roster, x, y, size=58):
        for group in (CELLS, "bacteria"):
            slots = [s for s in sorted(roster, key=int) if team_of(s, roster[s]) == group][:3]
            for slot in slots:
                player = roster[slot]
                hero = player.get("hero")
                self.box(x, y, size, size, page_tint(group), 2, 0)
                if hero in HEROES:
                    self.art(hero, x + 2, y + 2, size - 4, size - 4, size * (2.4 if group == CELLS else 1.5), dy=2)
                if player.get("bot"):
                    self.panel(x + 2, y + size - 16, 30, 14, INK)
                    self.t("BOT", x + 5, y + size - 16, 11, WHITE)
                x += size + 6
            if group == CELLS:
                self.burst(x - 2, y + size / 2 - 22, 46, 44, RED, BURST_SOFT, border=4, shadow=2)
                self.t("VS", x + 21, y + size / 2 - 11, 19, WHITE, "title", "c", stroke=1)
                x += 50
        return x

    def row(self, meta, y):
        L, R = 96, self.R
        h = self.ROW - 14
        hover = self.hovered(L, y, R - L, h)
        self.box(L, y, R - L, h, YELLOW if hover else WHITE)
        # Data
        when = created(meta)
        self.panel(L + 3, y + 3, 112, h - 6, INK)
        if when:
            self.t(f"{when.day:02}", L + 59, y + 2, 46, WHITE, "title", "c")
            self.t(f"{MONTHS[when.month - 1]} {when.year}", L + 59, y + 47, 13, YELLOW, align="c")
            self.t(when.strftime("%H:%M"), L + 59, y + 62, 13, WHITE, "body", "c")
        else:
            self.t("?", L + 59, y + 14, 46, WHITE, "title", "c")
        roster = meta.get("roster") or {}
        x = self.lineup(roster, L + 130, y + (h - 58) / 2)
        # Ficha
        info_x = x + 18
        buttons = 236
        width = R - info_x - buttons
        from .maps import info as map_info
        place = map_info(meta.get("map", "bairro")).title.upper()
        self.fit(f"{place} · SALA DE {str(meta.get('host', '?')).upper()}", info_x, y + 8, width, 19,
                 font="title")
        tx = info_x
        duration = meta.get("duration")
        tx += self.t(clock_text(duration) if duration is not None else "--:--", tx, y + 32, 24, INK, "title") + 12
        winner = meta.get("winner")
        if winner:
            tag = "CÉLULAS VENCERAM" if winner == CELLS else "BACTÉRIAS VENCERAM"
            fill = accent(winner)
        else:
            tag, fill = ("INTERROMPIDA" if not meta.get("complete") else "SEM VENCEDOR"), GREY
        tw = self.measure(tag, 13) + 18
        self.panel(tx, y + 36, tw, 22, INK)
        self.t(tag, tx + 9, y + 39, 13, fill)
        tx += tw + 10
        self.t(size_text(meta.get("size", 0)), tx, y + 39, 13, MUTED, "body")
        names = [p.get("name", "?") for _, p in sorted(roster.items(), key=lambda kv: int(kv[0]))]
        self.fit("  ·  ".join(names), info_x, y + 62, width, 13, tint=MUTED, font="body")
        # Ações
        self.button("ASSISTIR!", R - 226, y + (h - 50) / 2, 166, lambda m=meta: self.play(m), True, h=50, size=24,
                    arrow=True)
        cx, cy = R - 32, y + h / 2
        asking = self.confirm == meta["path"]
        if asking:
            self.panel(R - 226, y + h - 22, 166, 20, RED)
            self.t("CLIQUE NO × DE NOVO PARA APAGAR", R - 143, y + h - 20, 11, WHITE, align="c")
        over = self.hovered(cx - 14, cy - 14, 28, 28)
        self.circle(cx, cy, 14, RED if over or asking else INK)
        self.seg(cx - 5, cy - 5, cx + 5, cy + 5, 2.6, WHITE)
        self.seg(cx + 5, cy - 5, cx - 5, cy + 5, 2.6, WHITE)
        self.click(cx - 14, cy - 14, 28, 28, lambda m=meta: self.remove(m))
        self.click(L, y, R - L - 240, h, lambda m=meta: self.play(m))

    def empty(self, now):
        L = 96
        y = 250
        self.bubble(L + 250, y + 20, 640, 150, WHITE, 30, tail=((L + 290, y + 160), (L + 340, y + 166),
                                                                 (L + 222, y + 220)))
        self.t("Nenhum replay por aqui…", L + 284, y + 44, 36, INK, "title")
        self.wrap("Ao criar uma sala, marque GRAVAR REPLAY no lobby. A partida inteira fica salva e "
                  "aparece nesta estante para você rever em terceira pessoa.", L + 286, y + 92, 580, 17,
                  max_lines=3)
        self.box(L, y + 120, 210, 250, YELLOW)
        self.scissor(L + 3, y + 123, 204, 244)
        self.art("neutrophil", L + 3, y + 123, 204, 244, 380, dy=-10 + math.sin(now * 2) * 4)
        self.end_scissor()
        self.outline(L, y + 120, 210, 250)

    def draw(self):
        now = time.perf_counter()
        self.page(PAPER)
        self.spine()
        self.header(now)
        L, R = 96, self.R
        list_top, list_bottom = 214, self.bottom - 96
        if not self.entries:
            self.empty(now)
        else:
            total = len(self.entries) * self.ROW
            view = list_bottom - list_top
            self.scroll = max(0.0, min(self.scroll, max(0.0, total - view)))
            self.scissor(L - 4, list_top - 4, R - L + 14, view + 8)
            y = list_top - self.scroll
            for meta in self.entries:
                if y + self.ROW > list_top - self.ROW and y < list_bottom:
                    self.row(meta, y)
                y += self.ROW
            self.end_scissor()
            # Os cliques fora da área visível não valem.
            self.controls = [(rect, action) for rect, action in self.controls
                             if rect.y + rect.height > self.rect(0, list_top, 1, 1).y
                             and rect.y < self.rect(0, list_bottom, 1, 1).y]
            if total > view:
                k = view / total
                bar = view * k
                by = list_top + (view - bar) * (self.scroll / max(1.0, total - view))
                self.panel(R + 6, list_top, 6, view, GREY)
                self.panel(R + 6, by, 6, bar, INK)
        y = self.bottom - 76
        self.button("VOLTAR AO MENU", L, y, 250, lambda: self.game.new_game("menu"), True, h=54, size=26)
        self.button("ABRIR PASTA", L + 266, y, 200, self.open_folder, h=54, size=24)
        if self.error:
            self.wrap(self.error, L + 490, y + 6, R - L - 490, 15, RED, max_lines=2, leading=1.25)
        else:
            n = len(self.entries)
            text = f"{n} replay{'s' if n != 1 else ''} · pasta {REPLAY_DIR.as_posix()}/ · os arquivos podem ser " \
                   f"enviados para outra pessoa assistir"
            self.wrap(text, L + 490, y + 6, R - L - 490, 15, MUTED, max_lines=2, leading=1.25)


class ReplayOverlay(MangaCanvas):
    """Controles da reprodução por cima da arena (transparente onde não há quadro)."""

    def __init__(self, director):
        super().__init__()
        self.director = director
        self.track = None
        self.dragging = False
        self.preview = None
        self.ended_at = None

    @property
    def R(self):
        return self.W - 16

    # -- entrada ---------------------------------------------------------------------------
    def virtual_mouse(self):
        m = rl.get_mouse_position()
        return (m.x - self.ox) / self.scale, (m.y - self.oy) / self.scale

    def loop(self):
        super().loop()
        d = self.director
        if self.track is None or not d.state.ui:
            self.dragging = False
            return
        x, y, w, h = self.track
        mx, my = self.virtual_mouse()
        if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT) and x - 8 <= mx <= x + w + 8 \
                and y - 14 <= my <= y + h + 14:
            self.dragging = True
        if self.dragging:
            self.preview = max(0.0, min(1.0, (mx - x) / w))
            if not rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
                self.dragging = False
                target, self.preview = self.preview * d.duration, None
                d.seek(target)

    # -- desenho ---------------------------------------------------------------------------
    def draw(self):
        rl.clear_background(rl.BLANK)
        d = self.director
        self.track = None
        if not d.state.ui:
            self.t("H · MOSTRAR CONTROLES", 20, self.bottom - 34, 14, WHITE, stroke=2)
            return
        self.title_plate()
        self.match_strip()
        self.feed()
        self.cards()
        self.transport()
        self.focus_plate()
        if not d.finished:
            self.ended_at = None
        if d.finished:
            self.ending()
        elif d.state.paused:
            wob = math.sin(time.perf_counter() * 3) * 2
            self.t("PAUSA…", self.W / 2, 128, 64, WHITE, "title", "c", stroke=3, shadow=5, angle=-6 + wob)

    def title_plate(self):
        d = self.director
        label = "REPLAY · OPERAÇÃO ABRASION"
        w = self.measure(label, 22, "title") + 54
        self.rbox(20, 18, w, 34, INK, -2)
        self.rbox(16, 14, w, 34, INK, -2)
        self.rbox(19, 17, w - 6, 28, YELLOW, -2)
        self.circle(36, 31, 7, RED)
        self.t(label, 50, 19, 22, INK, "title", angle=-2)
        header = d.data.header
        try:
            when = datetime.fromisoformat(header.get("created", "")).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            when = ""
        sub = f"{when} · sala de {header.get('host', '?')}".strip(" ·")
        sw = self.measure(sub, 14, "body") + 22
        self.box(22, 56, sw, 26, WHITE, 2, 3)
        self.t(sub, 33, 60, 14, font="body")
        if not d.data.same_balance:
            note = "Gravado com outro balanceamento: granadas e zonas podem divergir."
            nw = self.measure(note, 13, "body") + 20
            self.panel(22, 88, nw, 22, RED)
            self.t(note, 32, 91, 13, WHITE, "body")

    def match_strip(self):
        s = self.director.arena.state
        items = [("TEMPO", clock_text(s.elapsed)),
                 ("ESCOLTA", f"{int(100 * s.escort / max(1, s.escort_total))}%"),
                 ("ANTÍGENO", f"{int(s.recognition)}%"),
                 ("COLÔNIAS", str(len(s.colonies)))]
        widths = [max(self.measure(label, 11), self.measure(value, 24, "title")) + 26 for label, value in items]
        x = self.R - sum(widths)
        self.box(x, 14, sum(widths), 52, WHITE, 3, 4)
        for (label, value), w in zip(items, widths):
            self.t(label, x + 13, 19, 11, MUTED)
            self.t(value, x + 13, 32, 24, INK, "title")
            x += w
            if x < self.R - 2:
                self.panel(x - 1, 20, 2, 40, GREY)

    def feed(self):
        """Últimos avisos da partida (abates, colônias), no alto e ao centro, o mais novo embaixo."""
        s = self.director.arena.state
        y = 16
        lines = list(s.feed)[-3:]
        for i, text in enumerate(lines):
            newest = i == len(lines) - 1
            w = self.measure(text, 14) + 24
            x = (self.W - w) / 2
            self.panel(x + 3, y + 3, w, 26, INK)
            self.panel(x, y, w, 26, YELLOW if newest else INK)
            self.t(text, x + 12, y + 4, 14, INK if newest else WHITE)
            y += 30

    def card(self, slot, x, y, w, h):
        d = self.director
        actor = d.arena.actors.get(slot)
        player = self.game.session.roster.value.get(slot)
        if actor is None or player is None:
            return
        team = player["team"]
        followed = d.state.follow == slot and not d.state.free
        hover = self.hovered(x, y, w, h)
        lift = 2 if hover and not followed else 0
        if followed:
            self.panel(x - 4, y - 4, w + 8, h + 8, INK)
        self.box(x - lift, y - lift, w, h, YELLOW if followed else page_tint(team), 3, 4 + lift)
        x -= lift
        y -= lift
        hero = actor.hero
        self.panel(x + 3, y + 3, h - 6, h - 6, accent(team))
        self.art(hero, x + 3, y + 3, h - 6, h - 6, (h - 6) * (2.5 if team == CELLS else 1.55), dy=2)
        self.panel(x + h - 3, y + 3, 3, h - 6, INK)
        tx = x + h + 6
        self.fit(player["name"], tx, y + 5, w - h - 60, 16)
        self.fit(kit_lines.name(hero).upper(), tx, y + 25, w - h - 64, 12, tint=MUTED)
        kills, deaths = actor.kills.value, actor.deaths.value
        self.t(f"{kills}/{deaths}", x + w - 9, y + 5, 22, INK, "title", "r")
        # Vida e escudo
        bx, by, bw, bh = tx, y + h - 19, w - h - 15, 11
        health = max(0.0, actor.health.value / max(1, HEROES[hero].health))
        shield = max(0.0, actor.shield.value / max(1, HEROES[hero].health))
        self.panel(bx, by, bw, bh, WHITE)
        self.panel(bx, by, bw * min(1.0, health), bh, RED if health < .35 else bar_tint(team))
        if shield > 0:
            self.panel(bx + bw * min(1.0, health), by, bw * min(1.0 - min(1.0, health), shield), bh, (150, 200, 255))
        self.outline(bx, by, bw, bh, INK, 2)
        if not actor.alive:
            self.halftone_rect(x + 3, y + 3, w - 6, h - 6, INK, 120)
            cx, cy = x + h / 2, y + h / 2
            self.seg(cx - 14, cy - 14, cx + 14, cy + 14, 6, RED)
            self.seg(cx + 14, cy - 14, cx - 14, cy + 14, 6, RED)
            self.panel(bx, by - 1, 64, bh + 2, INK)
            self.t("FORA", bx + 8, by - 2, 12, WHITE)
        if player.get("bot"):
            self.panel(x + w - 41, y + 29, 32, 15, INK)
            self.t("BOT", x + w - 37, y + 29, 12, WHITE)
        self.kb(str(slot + 1), x - 9, y - 9, 20, RED if followed else INK)
        self.click(x, y, w, h, lambda s=slot: d.follow(s))

    def cards(self):
        roster = self.game.session.roster.value
        w, h, gap = 232, 64, 12
        y0 = 136
        for column, slots in ((0, (0, 1, 2)), (1, (3, 4, 5))):
            x = 26 if column == 0 else self.R - w - 6
            title = "DEFESA IMUNE" if column == 0 else "INVASÃO BACTERIANA"
            tw = self.measure(title, 13) + 18
            tx = x if column == 0 else x + w - tw
            self.panel(tx, y0 - 26, tw, 20, INK)
            self.t(title, tx + 9, y0 - 24, 13, CYAN if column == 0 else PINK)
            for i, slot in enumerate(slots):
                if slot in roster:
                    self.card(slot, x, y0 + i * (h + gap), w, h)

    def speed_control(self, x, y, w, h):
        d = self.director
        self.box(x, y, w, h, WHITE, 3, 3)
        speed = d.state.speed
        label = (f"{speed:g}x").replace(".", ",")
        self.t(label, x + w / 2, y + (h - 24) / 2, 24, INK, "title", "c")
        for direction, ax in ((-1, x + 16), (1, x + w - 16)):
            enabled = (speed > SPEEDS[0]) if direction < 0 else (speed < SPEEDS[-1])
            tint = INK if enabled else GREY
            if enabled and self.hovered(ax - 14, y, 28, h):
                tint = RED
            self.arrow(ax - direction * 5, y + h / 2, 14, tint, direction)
            self.click(ax - 16, y, 32, h, lambda k=direction: d.step_speed(k))
        self.t("VELOCIDADE", x + w / 2, y - 15, 11, WHITE, align="c", stroke=1.5)

    def transport(self):
        d = self.director
        L, R = 16, self.R
        h = 74
        y = self.bottom - h - 16
        self.box(L, y, R - L, h, WHITE, 3, 5)
        # Play / pausa (explosão amarela)
        bx, by = L + 6, y - 12
        hover = self.hovered(bx, by, 92, 92)
        grow = 3 if hover else 0
        self.burst(bx - grow, by - grow, 92 + 2 * grow, 92 + 2 * grow, YELLOW, BURST_SOFT, border=7, shadow=4)
        cx, cy = bx + 46, by + 46
        if d.state.paused or d.finished:
            self.arrow(cx - 9, cy, 30, INK)
        else:
            self.round(cx - 13, cy - 14, 9, 28, 2, INK)
            self.round(cx + 4, cy - 14, 9, 28, 2, INK)
        self.click(bx, by, 92, 92, d.toggle_pause)
        # Relógio
        shown = self.preview * d.duration if self.preview is not None else d.clock
        self.t(clock_text(shown), L + 110, y + 9, 34, INK, "title")
        self.t(f"DE {clock_text(d.duration)}", L + 112, y + 47, 13, MUTED)
        # Controles à direita
        exit_w, cam_w, speed_w = 96, 168, 128
        rx = R - 10 - exit_w
        self.button("SAIR", rx, y + 14, exit_w, lambda: close_replay(self.game), h=46, size=24)
        rx -= 12 + cam_w
        free = d.state.free
        self.button("CÂMERA LIVRE" if not free else "SEGUIR JOGADOR", rx, y + 14, cam_w, d.toggle_free,
                    primary=free, h=46, size=19)
        rx -= 14 + speed_w
        self.speed_control(rx, y + 14, speed_w, 46)
        # Linha do tempo
        tx0, tx1 = L + 214, rx - 26
        tw = tx1 - tx0
        ty = y + 40
        self.track = (tx0, ty - 9, tw, 18)
        progress = d.clock / max(1e-6, d.duration)
        self.panel(tx0, ty - 6, tw, 12, GREY)
        self.halftone_rect(tx0, ty - 6, tw, 12, (150, 150, 150), 160, step=4)
        self.panel(tx0, ty - 6, tw * progress, 12, RED)
        self.outline(tx0, ty - 6, tw, 12, INK, 2)
        for minute in range(1, int(d.duration // 60) + 1):
            mx = tx0 + tw * minute * 60 / d.duration
            self.panel(mx - 1, ty + 7, 2, 8, INK)
        for t, victim, source in d.data.kills:
            kx = tx0 + tw * t / max(1e-6, d.duration)
            fill = CYAN if team_of(source) == CELLS else PINK
            self.tri((kx - 6, ty - 22), (kx + 6, ty - 22), (kx, ty - 10), INK)
            self.tri((kx - 3.5, ty - 20.5), (kx + 3.5, ty - 20.5), (kx, ty - 13.5), fill)
        knob = self.preview if self.preview is not None else progress
        kx = tx0 + tw * knob
        self.circle(kx + 2, ty + 2, 12, INK)
        self.circle(kx, ty, 12, INK)
        self.circle(kx, ty, 8, YELLOW)
        mx, my = self.virtual_mouse()
        if self.dragging or (tx0 <= mx <= tx1 and ty - 14 <= my <= ty + 14):
            at = (self.preview if self.dragging else (mx - tx0) / tw) * d.duration
            label = clock_text(at)
            lw = self.measure(label, 16) + 16
            px = (kx if self.dragging else mx) - lw / 2
            self.panel(px, ty - 52, lw, 24, INK)
            self.tri((px + lw / 2 - 6, ty - 28), (px + lw / 2 + 6, ty - 28), (px + lw / 2, ty - 21), INK)
            self.t(label, px + 8, ty - 50, 16, WHITE)
        # Atalhos
        hint = ("ESPAÇO pausa · SETAS pulam 5 s / mudam a velocidade · 1-6 ou TAB trocam o jogador · "
                "C câmera livre · H esconde · ESC sai")
        self.fit(hint, L + 110, y + h + 2, R - L - 120, 12, tint=WHITE, font="bold", stroke=1.5)

    def focus_plate(self):
        d = self.director
        y = self.bottom - 74 - 16 - 46
        if d.state.free:
            text = "CÂMERA LIVRE · botão direito gira · WASD move · Q/E desce e sobe · Shift acelera"
            w = self.measure(text, 15) + 28
            x = (self.W - w) / 2
            self.panel(x + 4, y + 4, w, 30, INK)
            self.panel(x, y, w, 30, INK)
            self.t(text, x + 14, y + 6, 15, WHITE)
            return
        actor = d.arena.actors.get(d.state.follow)
        player = self.game.session.roster.value.get(d.state.follow)
        if actor is None or player is None:
            return
        name = player["name"].upper()
        hero = kit_lines.name(actor.hero).upper()
        status = "" if actor.alive else "  · ELIMINADO"
        nw = self.measure(name, 22, "title")
        hw = self.measure(hero + status, 14)
        w = nw + hw + 120
        x = (self.W - w) / 2
        self.panel(x + 4, y + 4, w, 32, INK)
        self.panel(x, y, w, 32, INK)
        self.panel(x + 4, y + 4, 92, 24, YELLOW)
        self.t("SEGUINDO", x + 50, y + 8, 14, INK, align="c")
        self.t(name, x + 106, y + 3, 22, WHITE, "title")
        self.t(hero + status, x + 114 + nw, y + 9, 14, accent(player["team"]) if actor.alive else RED)

    def ending(self):
        d = self.director
        state = d.arena.state
        result = d.data.result or {}
        winner = result.get("state", {}).get("winner") or state.winner
        cx = self.W / 2
        if self.ended_at is None:
            self.ended_at = time.perf_counter()
        e = .6 + .4 * ease_out((time.perf_counter() - self.ended_at) / .35)
        bw, bh = 560 * e, 270 * e
        self.burst(cx - bw / 2, 170 + (270 - bh) / 2, bw, bh, YELLOW, BURST_SOFT, border=9, shadow=6)
        self.t("FIM DA PARTIDA!", cx, 222, 50, INK, "title", "c")
        if winner:
            line = "INFECÇÃO CONTIDA!" if winner == CELLS else "INFECÇÃO ESTABELECIDA!"
            self.t(line, cx, 276, 40, accent(winner) if winner == CELLS else RED, "title", "c", stroke=2.5,
                   shadow=3)
        else:
            self.t("A gravação termina aqui.", cx, 284, 20, INK, "body", "c")
        self.button("VER DE NOVO", cx - 214, 470, 200, d.toggle_pause, True, h=52, size=24)
        self.button("OUTROS REPLAYS", cx + 14, 470, 200, lambda: close_replay(self.game), h=52, size=24)
