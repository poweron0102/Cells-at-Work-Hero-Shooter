"""HUD de combate, estilo "Arena" (B): placar e objetivo no topo, vida em blocos a esquerda,
especial circular no centro, habilidades inclinadas + municao a direita, marcadores com estados
sobre as cabecas, cartao do kit (segurar F1), respawn/espectador, pausa e minimapa.

Cores fixas por equipe RELATIVA a quem joga: a propria equipe e sempre turquesa e a inimiga
sempre vermelha (dos dois lados). Dourado = especial.
"""
import math
import re
from contextlib import contextmanager
from pathlib import Path
import pyray as rl
from EasyCells3D.Geometry import Vec3
from .ui_base import Canvas
from .catalog import HEROES, KIT, ICONS, CELLS, BALANCE, can_select, unlocked
from .screens import leave
from .options import open_settings
from .cursor import set_cursor_captured
from .hud_portraits import draw_face
from .hud_icons import draw_icon
from .visuals import color
from . import layout

INK = (24, 37, 49)
PAPER = (240, 244, 247)
WHITE = (255, 255, 255)
MUTED = (154, 174, 188)
PANEL = (10, 20, 28)
TEAL = (26, 167, 161)
TEAL_L = (111, 214, 210)
RED = (200, 67, 74)
RED_L = (255, 75, 85)
GOLD = (250, 199, 55)
SKY = (143, 208, 255)
PINK = (255, 143, 147)
PURPLE = (176, 120, 220)
SKEW = .25  # tan(14 graus)
SKEW_MAX = 18  # deslocamento maximo: paineis altos nao inclinam ate o texto vazar
AMMO_W = 72  # largura da barra de municao (cabe entre o tile E e a borda)

SHORT = {'neutrophil': 'NEU', 'macrophage': 'MAC', 'b_cell': 'BCL', 'killer_t': 'KTC', 'pneumococcus': 'PNE',
         'staphylococcus': 'STA', 'pseudomonas': 'PSE', 'streptococcus': 'STR'}
EFFECTS = (('haste', 'VELOZ', TEAL), ('frenzy', 'FURIA', TEAL), ('guard', 'PROTEGIDO', GOLD),
           ('shield_hold', 'ESCUDO', SKY), ('slow', 'LENTO', RED), ('root', 'PRESO', RED),
           ('marked', 'MARCADO', (70, 140, 210)), ('antiheal', 'SEM CURA', PURPLE))
STATUS_ICONS = (('marked', 'mark', SKY), ('root', 'net', WHITE), ('perforin', 'drop', RED_L),
                ('antiheal', 'toxin', PURPLE), ('ult', 'burst', GOLD))


def ascii_upper(text):
    """Maiusculas sem acento: a fonte da HUD so tem ASCII."""
    import unicodedata
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper()


class CombatHUD(Canvas):
    def __init__(self, arena, player_input):
        super().__init__()
        self.arena, self.player_input = arena, player_input
        self.face_until = 0
        self.face_state = 'normal'
        self.previous = None
        self.minimap = None
        self.fonts = {}
        self.ult_max = 1.0
        self.kill_text = ""
        self.feed_seen = 0

    def init(self):
        super().init()
        for key, name, size in (('b', 'BarlowCondensed-ExtraBoldItalic', 72), ('m', 'BarlowCondensed-SemiBoldItalic', 48)):
            path = Path('Assets/fonts')/f'{name}.ttf'
            if path.exists():
                font = rl.load_font_ex(str(path), size, rl.ffi.NULL, 0)
                rl.set_texture_filter(font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
                self.fonts[key] = font
            else:
                self.fonts[key] = self.font

    # -- layout ancorado -------------------------------------------------------------------
    # O espaco virtual tem altura (ou largura) minima de 720 (1280) e se estende para cobrir a
    # janela inteira: W x H. Cada bloco do HUD desenha nas coordenadas de referencia 1280x720 e
    # e deslocado pela ancora (0 = esquerda/topo, .5 = centro, 1 = direita/base).
    def layout(self):
        sw, sh = rl.get_screen_width(), rl.get_screen_height()
        self.scale = min(sw/1280, sh/720)
        self.W, self.H = sw/self.scale, sh/self.scale
        self.ox = self.oy = 0.0
        self.controls = []

    @contextmanager
    def anchor(self, ax, ay):
        old = self.ox, self.oy
        self.ox = (self.W-1280)*ax*self.scale
        self.oy = (self.H-720)*ay*self.scale
        try:
            yield
        finally:
            self.ox, self.oy = old

    def full(self, tint, alpha):
        rl.draw_rectangle(0, 0, rl.get_screen_width(), rl.get_screen_height(), color(tint, alpha))

    # -- primitivas (espaco virtual 1280x720) ------------------------------------------
    def P(self, x, y):
        return rl.Vector2(self.ox+x*self.scale, self.oy+y*self.scale)

    def tx(self, value, x, y, size=16, tint=WHITE, font='b', align='l', shadow=True, alpha=255):
        value = str(value).upper()
        f = self.fonts.get(font, self.font)
        spacing = size*.03
        width = rl.measure_text_ex(f, value, size, spacing).x
        if align == 'c':
            x -= width/2
        elif align == 'r':
            x -= width
        if shadow:
            rl.draw_text_ex(f, value, self.P(x+1, y+1.5), size*self.scale, spacing*self.scale, color((0, 0, 0), alpha*.6))
        rl.draw_text_ex(f, value, self.P(x, y), size*self.scale, spacing*self.scale, color(tint, alpha))
        return width

    def measure(self, value, size, font='b'):
        return rl.measure_text_ex(self.fonts.get(font, self.font), str(value).upper(), size, size*.03).x

    def fit(self, value, x, y, width, size=16, tint=WHITE, font='b', align='l', alpha=255):
        m = self.measure(value, size, font)
        return self.tx(value, x, y, min(size, size*width/max(1, m)), tint, font, align, alpha=alpha)

    def tri(self, a, b, c, tint, alpha=255):
        if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) > 0:
            b, c = c, b
        rl.draw_triangle(self.P(*a), self.P(*b), self.P(*c), color(tint, alpha))

    def seg(self, x1, y1, x2, y2, w, tint, alpha=255):
        rl.draw_line_ex(self.P(x1, y1), self.P(x2, y2), w*self.scale, color(tint, alpha))

    def ring(self, cx, cy, r0, r1, a0, a1, tint, alpha=255):
        rl.draw_ring(self.P(cx, cy), max(0, r0)*self.scale, r1*self.scale, a0, a1, 40, color(tint, alpha))

    def rect(self, x, y, w, h, tint=None, alpha=255):
        if tint is None:
            return super().rect(x, y, w, h)
        self.panel(x, y, w, h, tint, alpha)

    def sk(self, x, y, w, h, tint, alpha=255):
        s = min(h*SKEW, SKEW_MAX)
        tl, tr, br, bl = (x+s, y), (x+w+s, y), (x+w, y+h), (x, y+h)
        self.tri(tl, bl, br, tint, alpha)
        self.tri(tl, br, tr, tint, alpha)

    def skout(self, x, y, w, h, tint, thick=2, alpha=255):
        s = min(h*SKEW, SKEW_MAX)
        pts = [(x+s, y), (x+w+s, y), (x+w, y+h), (x, y+h), (x+s, y)]
        for a, b in zip(pts, pts[1:]):
            self.seg(a[0], a[1], b[0], b[1], thick, tint, alpha)

    def chip(self, text, x, y, tint, size=14, alpha=230, text_tint=WHITE, h=None):
        h = h or size+6
        w = self.measure(text, size)+16
        self.sk(x, y, w, h, tint, alpha)
        self.tx(text, x+8+h*SKEW*.5, y+(h-size)/2-1, size, text_tint, shadow=False)
        return w

    def key(self, text, x, y, size=12):
        w = max(16, self.measure(text, size)+8)
        self.rect(x, y, w, size+4, WHITE, 240)
        self.tx(text, x+w/2, y+1, size, INK, align='c', shadow=False)
        return w

    def vgrad(self, x, y, w, h, tint, a0, a1):
        r = super().rect(x, y, w, h)
        rl.draw_rectangle_gradient_v(int(r.x), int(r.y), int(r.width), int(r.height), color(tint, a0), color(tint, a1))

    def hgrad(self, x, y, w, h, tint, a0, a1):
        r = super().rect(x, y, w, h)
        rl.draw_rectangle_gradient_h(int(r.x), int(r.y), int(r.width), int(r.height), color(tint, a0), color(tint, a1))

    def vignette(self, tint, alpha, depth=90):
        W, H = self.W, self.H
        self.vgrad(0, 0, W, depth, tint, alpha, 0)
        self.vgrad(0, H-depth, W, depth, tint, 0, alpha)
        self.hgrad(0, 0, depth, H, tint, alpha, 0)
        self.hgrad(W-depth, 0, depth, H, tint, 0, alpha)

    def world_to_screen(self, position):
        camera = self.player_input.camera
        if (position-camera.transform.position).dot(camera.transform.forward) <= 0:
            return None
        p = rl.get_world_to_screen(position.to_raylib(), camera.rl_camera)
        return (p.x-self.ox)/self.scale, (p.y-self.oy)/self.scale

    def team_tint(self, actor, other_team, light=False):
        if actor.team == other_team:
            return TEAL_L if light else TEAL
        return RED_L if light else RED

    # -- minimapa -------------------------------------------------------------------------
    def build_minimap(self):
        from .scenery import draw_district, prepare
        prepare()
        X0, Z0, X1, Z1 = layout.X0, layout.Z0, layout.X1, layout.Z1
        w, h = 496, int(496*(Z1-Z0)/(X1-X0))
        target = rl.load_render_texture(w, h)
        cx = (X0+X1)/2
        cam = rl.Camera3D(rl.Vector3(cx, 300, (Z0+Z1)/2), rl.Vector3(cx, 0, (Z0+Z1)/2), rl.Vector3(0, 0, -1),
                          Z1-Z0, rl.CameraProjection.CAMERA_ORTHOGRAPHIC)
        rl.begin_texture_mode(target)
        rl.clear_background(rl.Color(60, 70, 74, 255))
        rl.begin_mode_3d(cam)
        draw_district(rl.Vector3(0, 300, 0), 0, .0001, lit=False)
        rl.end_mode_3d()
        rl.end_texture_mode()
        rl.set_texture_wrap(target.texture, rl.TextureWrap.TEXTURE_WRAP_CLAMP)
        rl.set_texture_filter(target.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
        self.minimap = (target, w, h)

    def loop(self):
        super().loop()
        if self.minimap is None:
            try:
                self.build_minimap()
            except Exception:  # noqa: BLE001 - minimap is optional decoration
                self.minimap = False

    def draw_minimap(self, actor, s):
        x, y, size = 16, 16, 176
        self.rect(x-2, y-2, size+4, size+4, PANEL, 200)
        cx, cy = x+size/2, y+size/2
        p = actor.transform.position if actor.alive else Vec3(*(self.arena.path.at(s.escort) if self.arena.path.points
                                                                   else layout.RECON))
        center = (p.x, p.z)
        span = 80.0
        scale = size/span
        if self.minimap:
            X0, Z0, X1, Z1 = layout.X0, layout.Z0, layout.X1, layout.Z1
            texture, w, h = self.minimap
            u = (center[0]-span/2-X0)/(X1-X0)*w
            v = (center[1]-span/2-Z0)/(Z1-Z0)*h
            src = rl.Rectangle(u, h-v-span/(Z1-Z0)*h, span/(X1-X0)*w, -span/(Z1-Z0)*h)
            rl.draw_texture_pro(texture.texture, src, super().rect(x, y, size, size), rl.Vector2(0, 0), 0,
                                rl.Color(200, 210, 215, 255))

        def dot(wx, wz, r, tint):
            px, py = cx+(wx-center[0])*scale, cy+(wz-center[1])*scale
            if x+3 < px < x+size-3 and y+3 < py < y+size-3:
                self.circle(px, py, r, tint)
        path = self.arena.path
        if self.arena.mode != 'training':
            for k in range(0, int(s.escort_total), 3):
                q = path.at(k)
                dot(q[0], q[2], 1.2, TEAL_L if k < s.escort else (230, 230, 230))
            head = path.at(s.escort)
            dot(head[0], head[2], 5, RED_L if s.blocked_by or s.blocked_valve >= 0 else GOLD)
        for v in self.arena.valves:
            opened = self.arena.valve_open.get(v['id'], True)
            dot(v['pos'][0], v['pos'][2], 4, PURPLE if v['id'] in s.jammed else (TEAL_L if opened else RED_L))
        for letter, doors in layout.DESTINATIONS.items():
            n = layout.RBC_NODES[doors[0]]
            dot(n[0], n[2], 3, SKY)
        for cell in self.arena.rbc_view.cells.values():
            if cell['state'] not in ('dead', 'inside'):
                dot(cell['pos'][0], cell['pos'][2], 2, (236, 80, 76))
        for colony in s.colonies:
            if actor.team != CELLS or s.reveal > 0 or math.dist(colony['pos'], actor.feet) < 25:
                dot(colony['pos'][0], colony['pos'][2], 4, TEAL_L if actor.team != CELLS else RED_L)
        for m in self.arena.minions.values():
            owner = self.arena.actors.get(m['slot'])
            if owner is not None and owner.team == actor.team:
                dot(m['pos'][0], m['pos'][2], 3, TEAL_L)
        if s.recon_available():
            dot(layout.RECON[0], layout.RECON[2], 4, SKY)
        for target in self.arena.actors.values():
            if target.slot != actor.slot and target.alive and (target.team == actor.team or target.reveal > 0 or target.marked > 0
                                                               or actor.reveal > 0 or (actor.team == CELLS and s.reveal > 0)):
                dot(target.transform.x, target.transform.z, 3, TEAL_L if target.team == actor.team else RED_L)
        fwd = self.player_input.camera.transform.forward
        self.circle(cx, cy, 5, WHITE)
        self.seg(cx, cy, cx+fwd.x*12, cy+fwd.z*12, 2, WHITE)
        self.tx(ascii_upper(layout.MAP_INFO.title), x+4, y+size+4, 12, MUTED, font='m')
        if self.arena.valves:
            self.ecg(x, y+size+22, size, s)

    def ecg(self, x, y, w, s):
        """Coracao: tracado do batimento (pico na sistole) e o estado das valvas."""
        from .heart import beat
        h = 40
        self.rect(x-2, y-2, w+4, h+4, PANEL, 200)
        systole, frac, left = beat(s.elapsed)
        period = BALANCE['heart_period']
        pts = []
        for i in range(61):
            t = s.elapsed-period*1.6*(1-i/60)
            ph = (t % period)/period
            spike = 0.0
            if ph < .05:
                spike = math.sin(ph/.05*math.pi)*.95
            elif ph < .09:
                spike = -math.sin((ph-.05)/.04*math.pi)*.35
            elif .3 < ph < .42:
                spike = math.sin((ph-.3)/.12*math.pi)*.22
            pts.append((x+4+(w-8)*i/60, y+h*.55-spike*h*.42))
        for a, b in zip(pts, pts[1:]):
            self.seg(a[0], a[1], b[0], b[1], 2, RED_L if systole else TEAL_L)
        self.circle(pts[-1][0], pts[-1][1], 3, WHITE)
        label = "SISTOLE" if systole else "DIASTOLE"
        self.tx(f"{label} {left:.1f}s", x+4, y+2, 11, RED_L if systole else TEAL_L, font='m')
        names = {'av': 'tricuspide', 'semilunar': 'pulmonar'}
        yy = y+h+4
        for v in self.arena.valves:
            opened = self.arena.valve_open.get(v['id'], True)
            state = "EMPERRADA" if v['id'] in s.jammed else ("aberta" if opened else "fechada")
            tint = PURPLE if v['id'] in s.jammed else (TEAL_L if opened else RED_L)
            self.rect(x-2, yy, w+4, 16, PANEL, 180)
            self.tx(f"valva {names.get(v.get('kind'), v['id'])}: {state}", x+4, yy+2, 11, tint, font='m')
            yy += 17

    # -- topo: placar e objetivo ------------------------------------------------------------
    def team_tile(self, a, x, y, me, net):
        friendly = a.team == me.team
        fill = (TEAL if friendly else RED) if a.alive else (70, 74, 78)
        self.sk(x, y, 46, 40, fill, 235)
        ult = a.fx.get('ult', 0) > 0
        self.skout(x, y, 46, 40, GOLD if ult else (WHITE if a.alive else (130, 130, 130)), 2)
        if a.alive:
            label = "VOCE" if a is me else SHORT.get(a.hero, '?')
            self.tx(label, x+23+5, y+22, 13, WHITE, align='c', shadow=False)
            if friendly:
                k = max(0.0, min(1.0, a.health.value/HEROES[a.hero].health))
                self.sk(x+2, y+42, 42, 4, PANEL, 200)
                self.sk(x+2, y+42, 42*k, 4, WHITE if k > .35 else RED_L, 240)
        else:
            self.tx("X", x+28, y+8, 24, (200, 200, 200), align='c', shadow=False)

    def top_bar(self, me, s, net):
        actors = self.arena.actors
        own = sorted((a for a in actors.values() if a.team == me.team), key=lambda a: a.slot)
        foe = sorted((a for a in actors.values() if a.team != me.team), key=lambda a: a.slot)
        for i, a in enumerate(own):
            self.team_tile(a, 476-len(own)*52+i*52, 16, me, net)
        for i, a in enumerate(foe):
            self.team_tile(a, 812+i*52, 16, me, net)
        x0, w = 490, 300
        cells = me.team == CELLS
        pulse = .5+.5*math.sin(s.elapsed*8)
        mode = self.arena.mode
        if cells:
            if s.wound_closed:
                title, big, sub = layout.label('sealed'), f"{len(s.colonies)}", "colonias restantes"
                frac, tint = 1.0, TEAL
            elif mode == 'training':
                title = "FORMATURA"
                big, sub = f"{int(s.escort)}/{int(s.escort_total)}", "eritroblastos formados"
                frac, tint = s.escort/max(1, s.escort_total), TEAL
            else:
                remaining = max(0, s.escort_total-s.escort)
                if s.blocked_by:
                    title = "BLOQUEADO" if mode == 'convoy' else "BLOQUEADA"
                elif s.blocked_valve >= 0:
                    title = "VALVA EMPERRADA" if s.blocked_valve in s.jammed else "VALVA FECHADA"
                else:
                    title = layout.label('objective')
                big, sub = f"{int(100*s.escort/s.escort_total)}%", f"{layout.label('target')} a {int(remaining)} m"
                frac, tint = s.escort/s.escort_total, TEAL
        else:
            title, big = "INFECCAO", f"{int(s.infection())}/{BALANCE['infection_goal']}"
            sub = f"{len(s.colonies)} colonias"
            frac, tint = s.infection()/BALANCE['infection_goal'], TEAL
        tw = self.measure(title, 15)+self.measure(big, 30)+self.measure(sub, 13, 'm')+52
        bx = 640-tw/2
        self.sk(bx, 18, tw, 38, PANEL, 205)
        alert = title in ("BLOQUEADA", "BLOQUEADO", "VALVA EMPERRADA")
        title_tint = RED_L if alert else (GOLD if title == "VALVA FECHADA" else TEAL_L)
        cx = bx+16
        cx += self.tx(title, cx, 29, 15, title_tint, alpha=int(255*(.6+.4*pulse)) if alert else 255)+12
        cx += self.tx(big, cx, 20, 30, WHITE)+12
        self.tx(sub, cx, 31, 13, MUTED, font='m')
        # Barra segmentada.
        segs = 20
        for i in range(segs):
            filled = (i+1)/segs <= frac+1e-6
            partial = not filled and i/segs < frac
            self.sk(x0+i*15, 62, 13, 8, tint if filled else (PANEL if not partial else TEAL_L), 230 if filled else 150)
        # Linha secundaria.
        rec = s.recognition
        goal = BALANCE['unlock_b_cell'] if rec < BALANCE['unlock_b_cell'] else BALANCE['unlock_killer_t']
        rec_text = f"{int(rec)}/{goal}" if rec < BALANCE['unlock_killer_t'] else "completo"
        if cells:
            a_txt, a_tint = f"infeccao {int(s.infection())}/{BALANCE['infection_goal']}", PINK
            b_txt, b_tint = f"reconhecimento {rec_text}", SKY
        else:
            if s.wound_closed:
                esc = layout.label('sealed_short')
            elif mode == 'training':
                esc = f"formatura {int(s.escort)}/{int(s.escort_total)}"
            else:
                esc = f"{layout.label('payload')} {int(100*s.escort/s.escort_total)}%"
            stopped = (s.blocked_by or s.blocked_valve >= 0) and not s.wound_closed
            a_txt = esc+((" - parado" if mode == 'convoy' else " - paradas") if stopped else "")
            a_tint = TEAL_L if stopped else PINK
            b_txt, b_tint = f"reconhec. inimigo {rec_text}", SKY
        wa, wb = self.measure(a_txt, 13), self.measure(b_txt, 13)
        self.tx(a_txt, 640-(wa+wb+14)/2, 76, 13, a_tint)
        self.tx(b_txt, 640-(wa+wb+14)/2+wa+14, 76, 13, b_tint)
        if s.reveal > 0:
            self.tx(f"colonias reveladas {int(s.reveal)}s", 640, 92, 12, SKY, align='c')
        if s.notice_time > 0 and s.notice:
            self.tx(s.notice, 640, 108, 17, GOLD, align='c')

    def killfeed(self, me, s):
        lines = [l for l in s.feed[-5:] if ' eliminou ' in l][-4:]
        y = 70
        own_names = {HEROES[a.hero].name for a in self.arena.actors.values() if a.team == me.team}
        for line in lines:
            killer, victim = line.split(' eliminou ', 1)
            tint = TEAL if killer in own_names else RED
            text = f"{re.sub(r' [0-9]+$', '', killer)}  >  {re.sub(r' [0-9]+$', '', victim)}"
            w = self.measure(text, 14)+20
            self.chip(text, 1262-w, y, tint, 14, 215)
            y += 24

    # -- economia (bacterias) -----------------------------------------------------------------
    def economy(self, me, s):
        if me.team == CELLS:
            if s.wound_closed:
                status = (f"canalizando {int(100*s.recon/BALANCE['recon_channel'])}%" if s.recon > 0 else
                          "disponivel na torre" if s.recon_available() else f"recarga {int(s.recon_cooldown)}s")
                y = 222+(44+17*len(self.arena.valves)+20 if self.arena.valves else 0)
                self.chip("reconhecimento", 16, y, PANEL, 13, 210, SKY)
                self.tx(status, 20, y+24, 15, WHITE)
            return
        carried = s.resources.get(me.slot, 0)
        x, y = 28, 436
        self.sk(x, y, 210, 30, PANEL, 205)
        self.tx("recursos", x+12, y+8, 14, PINK)
        self.tx(str(carried), x+82, y+1, 26, WHITE)
        self.tx(f"colonia custa {BALANCE['colony_cost']}", x+110, y+10, 12, MUTED, font='m')
        yy = y+36
        for colony in s.colonies[:4]:
            hp = colony['hp']/BALANCE['colony_health']
            self.sk(x, yy, 210, 20, PANEL, 160)
            self.tx(f"c{colony['id']}", x+8, yy+3, 13, TEAL_L)
            self.sk(x+36, yy+7, 90, 6, (40, 40, 40), 200)
            self.sk(x+36, yy+7, 90*hp, 6, TEAL if hp > .35 else RED_L, 240)
            self.tx(f"dev {int(colony['dev'])}/{BALANCE['colony_dev_cap']}", x+136, yy+3, 12, WHITE, font='m')
            yy += 23

    # -- vida (inferior esquerdo) ---------------------------------------------------------------
    def health(self, me, kit, s):
        snapshot = (me.hero, me.health.value, me.ability_cd, me.charge)
        if self.previous and self.previous[0] == me.hero:
            if me.health.value < self.previous[1]:
                self.face_state, self.face_until = 'hurt', s.elapsed+.65
            elif me.ability_cd > self.previous[2] or me.charge < self.previous[3]-50:
                self.face_state, self.face_until = 'special', s.elapsed+1.2
        else:
            self.face_until = 0
        self.previous = snapshot
        low = me.health.value <= kit.health*.3
        expression = self.face_state if s.elapsed < self.face_until else 'low' if low else 'normal'
        x, y = 28, 600
        light = tuple(int(c*.35+255*.65) for c in kit.color)
        self.sk(x, y, 80, 80, light, 245)
        draw_face(self, me.hero, expression, x+10, y+5, 72)
        self.skout(x, y, 80, 80, WHITE, 3)
        hx = x+100
        # Estados ativos.
        cx = hx
        for attr, label, tint in EFFECTS:
            value = getattr(me, attr, 0)
            if value > 0:
                cx += self.chip(f"{label} {max(1, math.ceil(value))}", cx, y-30, tint, 13, 230)+6
        if me.in_zone('cloud', enemy=True):
            self.chip("nuvem", cx, y-30, PURPLE, 13, 230)
        # Numero.
        hp = max(0, math.ceil(me.health.value))
        w = self.tx(hp, hx, y-2, 42, RED_L if low else WHITE)
        self.tx(f"/ {kit.health}", hx+w+6, y+18, 18, (220, 220, 220), font='m')
        if me.shield.value >= 1:
            self.tx(f"+{int(me.shield.value)}", hx+w+70, y+14, 20, SKY)
        # Blocos de 25.
        n = math.ceil(kit.health/25)
        shield_n = math.ceil(me.shield.value/25) if me.shield.value >= 1 else 0
        total = n+shield_n
        pw = max(6.0, min(24.0, (280-(total-1)*3)/max(1, total)))
        for i in range(n):
            v = max(0.0, min(1.0, (me.health.value-i*25)/25))
            px = hx+i*(pw+3)
            self.sk(px, y+50, pw, 16, (0, 0, 0), 120)
            if v > 0:
                self.sk(px, y+50, pw*v, 16, RED_L if low else WHITE, 245 if v >= 1 else 150)
        hold = me.shield_hold > 0
        for j in range(shield_n):
            v = max(0.0, min(1.0, (me.shield.value-j*25)/25))
            px = hx+(n+j)*(pw+3)
            self.sk(px, y+50, pw*v, 16, GOLD if hold else SKY, 245)
        self.tx(kit.name, hx, y+70, 13, MUTED, font='m')

    # -- especial (centro) -----------------------------------------------------------------------
    def ultimate_meter(self, me, kit, s):
        cx, cy, r = 640, 640, 46
        if me.ult > self.ult_max or not me.ult_on:
            self.ult_max = max(.1, me.ult if me.ult_on else 1.0)
        self.circle(cx, cy, r+2, PANEL, 170)
        self.ring(cx, cy, r-3, r+3, 0, 360, WHITE, 60)
        ready = me.charge >= 100 and not me.ult_on
        if me.ult_on:
            frac = me.ult/self.ult_max if self.ult_max else 0
            self.ring(cx, cy, r-4, r+4, -90, -90+360*frac, GOLD, 255)
            self.tx(f"{me.ult:.1f}", cx, cy-22, 30, GOLD, align='c')
            self.fit(kit.ultimate, cx, cy+8, 70, 12, WHITE, align='c')
        else:
            frac = me.charge/100
            self.ring(cx, cy, r-3, r+3, -90, -90+360*frac, GOLD, 255)
            if ready:
                pulse = .5+.5*math.sin(s.elapsed*6)
                self.ring(cx, cy, r+5, r+9+3*pulse, 0, 360, GOLD, int(120+100*pulse))
                self.tx("pronto", cx, cy-20, 24, GOLD, align='c')
            else:
                w = self.tx(int(me.charge), cx-6, cy-24, 34, WHITE, align='c')
                self.tx("%", cx-6+w/2+1, cy-12, 16, WHITE)
            self.fit(kit.ultimate, cx, cy+10, 70, 12, GOLD, align='c')
        self.key("F", cx-8, cy+r-6, 13)
        if me.ult_on and me.hero == 'macrophage':
            self.tx(f"F  cuspir  -  {int(me.feast)} engolido", cx, cy-r-30, 18, GOLD, align='c')

    # -- habilidades + municao (inferior direito) -------------------------------------------------
    def tile(self, x, y, keyname, name, cd, me, active=False, bar=None, count=None, count_tint=WHITE, locked=False):
        ready = cd <= 0 and me.alive and not locked
        w, h = 66, 56
        if active:
            self.sk(x, y, w, h, TEAL, 230)
        else:
            self.sk(x, y, w, h, PANEL, 165 if ready else 215)
        self.skout(x, y, w, h, WHITE if ready or active else (110, 120, 128), 2)
        icon_tint = WHITE if ready or active else (120, 130, 138)
        if cd > 0 and not active:
            draw_icon(self, ICONS.get(name, ''), x+w/2+h*SKEW/2, y+h/2, 30, (70, 80, 88))
            self.tx(math.ceil(cd), x+w/2+h*SKEW/2, y+11, 30, WHITE, align='c')
        else:
            draw_icon(self, ICONS.get(name, ''), x+w/2+h*SKEW/2, y+h/2, 30, icon_tint)
        if count is not None:
            self.tx(count, x+w-6, y+2, 16, count_tint, align='r')
        if bar is not None:
            k, tint = bar
            self.sk(x-2, y+h+3, w, 5, (0, 0, 0), 150)
            self.sk(x-2, y+h+3, w*max(0.0, min(1.0, k)), 5, tint, 240)
        self.key(keyname, x-6, y-8, 11)
        self.fit(name, x+w/2, y+h+10, w+8, 13, WHITE if ready or active else MUTED, align='c')

    def abilities(self, me, kit, s):
        x0, y = 922, 610
        h = me.hero
        # RMB
        active = bool(me.front) or me.punch > 0 or me.aiming or me.zoom
        bar = None
        if h == 'macrophage':
            bar = (me.engulf_energy/BALANCE['engulf_time'] if me.ult <= 0 else 1.0, GOLD if me.ult > 0 else (255, 140, 190))
        elif h == 'pneumococcus':
            bar = (me.barrier_hp/BALANCE['barrier_health'], (190, 140, 255))
        elif h == 'killer_t' and me.punch > 0:
            bar = (me.punch, GOLD)
        lock = me.engulf_lock if h == 'macrophage' else me.barrier_lock if h == 'pneumococcus' else 0
        self.tile(x0, y, "RMB", kit.secondary, max(me.secondary_cd, lock), me, active, bar)
        # Q
        count, ctint, qcd = None, WHITE, me.ability_cd
        if h == 'streptococcus':
            count = me.q_charges
            qcd = me.q_recharge if me.q_charges == 0 else 0
            bar = (1-me.q_recharge/kit.ability_cd, TEAL_L) if me.q_charges < 2 else None
        elif h == 'neutrophil' and me.dash_charges > 0:
            count, ctint, qcd = me.dash_charges, GOLD, 0
            bar = None
        else:
            bar = None
        self.tile(x0+80, y, "Q", kit.ability, qcd, me, bool(me.placing), bar, count, ctint)
        # E
        self.tile(x0+160, y, "E", kit.ability2, me.ability2_cd, me)
        # Passiva
        passive = KIT[h]['passive'][0]
        draw_icon(self, ICONS.get(passive, ''), x0+12, y-30, 16, GOLD)
        self.tx(f"passiva - {passive}", x0+26, y-38, 13, GOLD, font='m')
        # Municao
        ax = 1252
        mag = kit.magazine
        ammo = me.weapon.ammo
        self.tx(ammo, ax, y-6, 50, RED_L if ammo == 0 else WHITE, align='r')
        if me.weapon.reload_time > 0:
            k = 1-me.weapon.reload_time/1.6
            self.sk(ax-AMMO_W, y+50, AMMO_W-2, 6, (0, 0, 0), 150)
            self.sk(ax-AMMO_W, y+50, (AMMO_W-2)*k, 6, TEAL_L, 240)
            self.tx("recarregando", ax, y+58, 13, TEAL_L, align='r')
        else:
            # Largura fixa (AMMO_W) entre o tile E e a borda: pentes grandes agrupam balas por pip.
            n = min(mag, 16)
            per = mag/n
            gap = 2 if n > 8 else 3
            pw = (AMMO_W-(n-1)*gap)/n
            for i in range(n):
                on = ammo > i*per
                self.rect(ax-AMMO_W+i*(pw+gap), y+48, pw, 14, WHITE, 240 if on else 70)
            self.tx(f"/ {mag}", ax, y+66, 13, (220, 220, 220), font='m', align='r')
        if not me.can_fire() and me.alive and (me.front or me.ult > 0 and h == 'b_cell'):
            self.tx("sem tiro", ax, y-24, 12, PINK, align='r')

    # -- mira e sobreposicoes ---------------------------------------------------------------
    def crosshair(self, me, s):
        if me.hero == 'b_cell' and me.zoom:
            self.full((6, 10, 14), 70)
            self.ring(640, 360, 228, math.hypot(self.W, self.H)/2+20, 0, 360, (6, 10, 14), 235)
            self.ring(640, 360, 226, 229, 0, 360, WHITE, 120)
            self.seg(420, 360, 620, 360, 2, WHITE)
            self.seg(660, 360, 860, 360, 2, WHITE)
            self.seg(640, 150, 640, 340, 2, WHITE)
            self.seg(640, 380, 640, 570, 2, WHITE)
            self.circle(640, 360, 3, RED_L)
        else:
            self.circle(640, 360, 3.5, (0, 0, 0), 140)
            self.circle(640, 360, 2.5, WHITE)
        if me.hit_marker > 0:
            tint = RED_L if me.kill_marker > 0 else WHITE
            k = 1+(me.kill_marker > 0)*.5
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                self.seg(640+sx*7*k, 360+sy*7*k, 640+sx*14*k, 360+sy*14*k, 3, tint)
        if me.kill_marker > 0:
            self.tx("eliminado", 640, 448, 22, RED_L, align='c')
            if me.hero == 'neutrophil' and me.dash_kill > 0:
                self.tx("+ avanco recarregado", 640, 474, 15, GOLD, align='c')
            if me.hero == 'macrophage':
                self.tx("fagocitose", 640, 474, 15, TEAL_L, align='c')
        if me.absorbed_fx > 0:
            self.tx("engolido", 640, 318, 14, (255, 160, 200), align='c')
        elif me.absorbed > 0:
            self.tx("escudo", 640, 318, 13, SKY, align='c')

    def damage_direction(self, me, s):
        fwd = self.player_input.camera.transform.forward
        yaw = math.atan2(fwd.x, -fwd.z)
        p = me.transform.position
        for ox, oz, t in me.hurt_from:
            age = s.elapsed-t
            if age > 1.2 or age < 0:
                continue
            ang = math.degrees(math.atan2(ox-p.x, -(oz-p.z))-yaw)-90
            self.ring(640, 360, 112, 122, ang-22, ang+22, RED_L, int(210*(1-age/1.2)))

    def overlays(self, me, s):
        if me.in_zone('cloud', enemy=True):
            self.full((110, 80, 140), 150)
        if me.hurt > 0:
            self.vignette(RED_L, int(170*min(1.0, me.hurt*4)), 110)
        elif me.health.value <= HEROES[me.hero].health*.3:
            self.vignette(RED, int(70+40*math.sin(s.elapsed*4)), 120)
        if me.ult_on:
            self.vignette(GOLD, 70, 70)
        if me.front == 'engulf' and me.third_person < .3:
            self.vignette((255, 120, 170), 120, 140)
            self.ring(self.W/2, self.H/2, 300, 312, 0, 360, (255, 150, 190), 70)
        if me.front == 'barrier' and me.third_person < .3:
            self.vignette((170, 120, 255), 90, 90)

    def prompts(self, me, s):
        if not me.alive:
            return
        y = 500
        if me.placing:
            ok = me.place is not None and me.place[1]
            what = "torreta" if me.placing == 'turret' else "parede de coagulo"
            self.tx(f"posicionar {what}", 640, y, 20, WHITE if ok else RED_L, align='c')
            self.tx("lmb confirmar  -  rmb / q cancelar" if ok else "local invalido", 640, y+24, 14,
                    TEAL_L if ok else RED_L, align='c')
            return
        if me.aiming:
            self.tx("solte rmb para lancar", 640, y, 15, (190, 255, 120), align='c')
        if me.hero == 'b_cell' and me.ult > 0:
            self.tx(f"chuva de anticorpos  {me.ult:.1f}s", 640, y, 20, SKY, align='c')
        if me.team == CELLS:
            return
        if me.build:
            k = me.build['progress']/BALANCE['colony_build_time']
            self.tx("construindo colonia", 640, y, 16, WHITE, align='c')
            self.sk(540, y+22, 200, 8, PANEL, 200)
            self.sk(540, y+22, 200*k, 8, TEAL, 240)
        elif me.controls.get('build') and me.build_problem:
            self.tx(me.build_problem, 640, y, 15, RED_L, align='c')
        elif me.deliverable():
            self.tx("[g] entregar recursos", 640, y, 16, WHITE, align='c')
        elif s.resources.get(me.slot, 0) >= BALANCE['colony_cost']:
            self.tx("[g] segurar - construir colonia", 640, y, 14, TEAL_L, align='c')

    # -- marcadores no mundo ----------------------------------------------------------------
    def marker(self, position, title, tint, size=13, arrow=True):
        p = self.world_to_screen(position)
        if p is None:
            return None
        x, y = p
        if not (10 < x < self.W-10 and 10 < y < self.H-10):
            return None
        if title:
            self.tx(title, x, y-24, size, tint, align='c')
        if arrow:
            self.tri((x-6, y-8), (x+6, y-8), (x, y), tint)
        return p

    def pips(self, x, y, frac, tint, n=6):
        w = 10
        x0 = x-(n*(w+2))/2
        for i in range(n):
            v = max(0.0, min(1.0, frac*n-i))
            self.sk(x0+i*(w+2), y, w, 7, (0, 0, 0), 130)
            if v > 0:
                self.sk(x0+i*(w+2), y, w*v, 7, tint, 240)

    def world_markers(self, me, s, net):
        a = self.arena
        cam = self.player_input.camera.transform.position
        cells = me.team == CELLS
        if not s.wound_closed and a.mode != 'training':
            head = a.path.at(s.escort)
            d = math.dist(head, me.feet)
            tint = TEAL_L if cells else RED_L
            stopped = " - bloqueado" if a.mode == 'convoy' else " - bloqueadas"
            if s.blocked_valve >= 0 and not s.blocked_by:
                stopped = " - valva emperrada" if s.blocked_valve in s.jammed else " - esperando a valva"
            label = f"{layout.label('payload')} {int(d)}m" + (stopped if s.blocked_by or s.blocked_valve >= 0 else "")
            self.marker(Vec3(head[0], head[1]+2.6, head[2]), label, RED_L if s.blocked_by and cells else tint, 14)
        elif s.recon_available() and cells:
            self.marker(Vec3(layout.RECON[0], layout.RECON[1]+2.5, layout.RECON[2]), "reconhecimento", SKY, 14)
        for colony in s.colonies:
            near = math.dist(colony['pos'], me.feet)
            if not cells or near < 25 or s.reveal > 0:
                tint = TEAL_L if not cells else RED_L
                p = self.marker(Vec3(colony['pos'][0], colony['pos'][1]+3.4, colony['pos'][2]),
                                f"colonia {colony['id']} - {int(near)}m", tint, 13)
                if p:
                    self.pips(p[0], p[1]-46, colony['hp']/BALANCE['colony_health'], tint, 8)
        for v in a.valves:
            d = math.dist(v['pos'], me.feet)
            if v['id'] in s.jammed and d < 60:
                self.marker(Vec3(v['pos'][0], v['pos'][1]+v.get('height', 6)+.8, v['pos'][2]),
                            "valva emperrada" if cells else "valva emperrada - proteja a colonia", PURPLE, 13)
        if a.mode == 'training' and cells:
            for cell in a.rbc_view.cells.values():
                if cell['state'] in ('flee', 'hide') and math.dist(cell['pos'], me.feet) < 45:
                    self.marker(Vec3(cell['pos'][0], cell['pos'][1]+1.9, cell['pos'][2]), "socorro!", GOLD, 12, False)
        if not cells:
            tag = "caixa" if a.mode == 'training' else "o2"
            for cell in a.rbc_view.cells.values():
                if cell['state'] not in ('dead', 'inside', 'cry') and math.dist(cell['pos'], me.feet) < 30:
                    top = 2.2*cell.get('scale', 1.0)
                    self.marker(Vec3(cell['pos'][0], cell['pos'][1]+top, cell['pos'][2]), tag, PINK, 12, False)
        for drop in a.drops:
            if math.dist(drop['pos'], me.feet) < 25:
                res = drop['kind'] == 'resource'
                self.marker(Vec3(drop['pos'][0], drop['pos'][1]+1.2, drop['pos'][2]), "recurso" if res else "antigeno",
                            PINK if res else TEAL_L, 12, False)
        for m in a.minions.values():
            owner = a.actors.get(m['slot'])
            if owner is None:
                continue
            tint = TEAL_L if owner.team == me.team else RED_L
            x, y, z = m['pos']
            if math.dist((x, y, z), cam.to_tuple) < 40 and a.clear_line(cam.to_tuple, (x, y+1, z)):
                p = self.marker(Vec3(x, y+1.6, z), "", tint, arrow=False)
                if p:
                    self.pips(p[0], p[1], m['hp']/m['max'], tint, 5 if m['kind'] == 'turret' else 3)
        for target in a.actors.values():
            if target.slot == me.slot or not target.alive:
                continue
            ally = target.team == me.team
            hp = target.health.value/HEROES[target.hero].health
            pos = target.transform.position
            dist = (pos-cam).magnitude()
            receptor = me.hero == 'neutrophil' and not ally and hp < .5 and dist < 40
            seen = dist < 35 and a.clear_line(cam.to_tuple, (pos+Vec3(0, .6, 0)).to_tuple)
            revealed = target.reveal > 0 or target.marked > 0 or me.reveal > 0 or receptor
            if not ally and not (seen or revealed):
                continue
            tint = TEAL_L if ally else RED_L
            p = self.world_to_screen(pos+Vec3(0, 1.45, 0))
            if p is None or not (10 < p[0] < self.W-10 and 30 < p[1] < self.H-10):
                continue
            x, y = p
            # Inimigos: contorno vermelho + silhueta atraves da parede (outline.py), sem barra.
            if ally:
                self.tx(net.roster.value[target.slot]["name"][:10], x, y-30, 12, tint, align='c')
                if hp < 1:
                    self.pips(x, y-14, hp, WHITE, 5)
            # Estados sobre a cabeca.
            icons = [(icon, tint_i) for kind, icon, tint_i in STATUS_ICONS
                     if (target.marked > 0 if kind == 'marked' else target.fx.get(kind, 0) > 0)]
            ix = x-(len(icons)-1)*11
            for icon, tint_i in icons:
                self.circle(ix, y-46, 10, PANEL, 200)
                draw_icon(self, icon, ix, y-46, 13, tint_i)
                ix += 22

    # -- cartao do kit (F1) ---------------------------------------------------------------------
    def kit_card(self, me, kit):
        info = KIT[me.hero]
        x, y, w, h = 230, 96, 820, 520
        self.sk(x, y, w, h, PANEL, 235)
        self.skout(x, y, w, h, TEAL_L, 3)
        light = tuple(int(c*.35+255*.65) for c in kit.color)
        self.sk(x+150, y+18, 110, 110, light, 255)
        draw_face(self, me.hero, 'normal', x+165, y+24, 100)
        self.tx(kit.name, x+290, y+26, 44, WHITE)
        self.tx(kit.role, x+292, y+78, 18, TEAL_L, font='m')
        self.tx(f"{kit.health} hp  -  velocidade {kit.speed:.1f}", x+292, y+102, 15, MUTED, font='m')
        rows = (("passiva", info['passive'], None), ("lmb", info['lmb'], None),
                ("rmb", info['rmb'], kit.secondary_cd or None), ("q", info['q'], kit.ability_cd),
                ("e", info['e'], kit.ability2_cd), ("f", info['f'], None))
        yy = y+146
        for i, (keyname, (name, desc), cd) in enumerate(rows):
            rx = x+120-i*0  # alinhado
            special = keyname == 'f'
            passive = keyname == 'passiva'
            self.sk(rx, yy, 640, 46, (20, 34, 44) if not special else (60, 48, 14), 220)
            self.key(keyname.upper(), rx+10, yy+15, 13)
            draw_icon(self, ICONS.get(name, ''), rx+92, yy+23, 30, GOLD if special or passive else WHITE)
            self.tx(name, rx+122, yy+4, 20, GOLD if special or passive else WHITE)
            self.fit(desc, rx+122, yy+26, 470, 14, (210, 220, 228), font='m')
            if cd:
                self.tx(f"{cd:g}s", rx+628, yy+12, 18, MUTED, align='r')
            elif special:
                self.tx(f"{kit.ult_time:g}s" if kit.ult_time else "", rx+628, yy+12, 18, GOLD, align='r')
            yy += 52
        self.tx(f"dica: {info['tip']}", x+120, yy+4, 15, TEAL_L, font='m')
        self.tx("solte f1 para voltar", x+w-20, y+h-28, 13, MUTED, align='r')

    # -- respawn / espectador / pausa ---------------------------------------------------------
    def sbutton(self, title, x, y, w, h, action, selected=False, enabled=True):
        r = super().rect(x, y, w, h)
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), r)
        fill = TEAL if selected else (40, 56, 66) if hover and enabled else (22, 34, 42)
        self.sk(x, y, w, h, fill if enabled else (30, 30, 34), 235)
        self.skout(x, y, w, h, WHITE if selected or hover and enabled else (90, 100, 110), 2)
        self.fit(title, x+14, y+(h-20)/2, w-24, 20, WHITE if enabled else (110, 110, 110))
        if enabled:
            self.controls.append((r, action))

    def respawn(self, me):
        net, s = self.game.session, self.arena.state
        x, y = 200, 250
        self.sk(x, y, 880, 270, PANEL, 230)
        if me.waiting:
            self.tx("aguardando uma colonia", x+40, y+20, 36, RED_L)
            self.tx("sem entrada nem colonia: um aliado vivo pode construir e resgatar voce.", x+42, y+64, 16, MUTED, font='m')
        else:
            self.tx(f"reforco em {max(1, int(me.respawn)+1)}s", x+40, y+20, 36, WHITE)
            self.tx("escolha o heroi e, como bacteria, onde renascer.", x+42, y+64, 16, MUTED, font='m')
        heroes = [h for h in HEROES if HEROES[h].team == me.team]
        for i, key in enumerate(heroes):
            enabled = can_select(key, me.team, net.roster.value, s.recognition, me.slot)
            self.sbutton(HEROES[key].name.split()[0], x+40+i*205, y+100, 190, 46, lambda h=key: net.choose(h),
                         net.roster.value[me.slot]["hero"] == key, enabled)
        if me.team != CELLS:
            options = me.spawn_options()
            for i, option in enumerate(options[:5]):
                label = "entrada" if option[0] == 'entrance' else f"colonia {option[1]}"
                chosen = me.spawn_choice == option or (me.spawn_choice not in options and i == 0)
                self.sbutton(label, x+40+i*160, y+160, 150, 38, lambda o=option: setattr(me, 'spawn_choice', o), chosen)
        if self.player_input.spectate_reason:
            self.tx(self.player_input.spectate_reason, x+42, y+212, 15, MUTED, font='m')
        target = self.player_input.camera_target
        if target is not None and target in self.arena.actors:
            self.tx(f"camera: {net.roster.value[target]['name']}", x+42, y+234, 15, WHITE, font='m')
        self.tx(f"b cell: {BALANCE['unlock_b_cell']}% antigeno  /  killer t: {BALANCE['unlock_killer_t']}%",
                x+850, y+234, 13, MUTED, font='m', align='r')

    # -- render -------------------------------------------------------------------------------
    def render(self):
        self.layout()
        net, a = self.game.session, self.arena
        s = a.state
        me = a.actors.get(net.local_slot)
        if me is None:
            set_cursor_captured(False)
            with self.anchor(.5, .5):
                self.sk(420, 320, 440, 60, PANEL, 230)
                self.tx("sincronizando com o servidor...", 640, 338, 22, WHITE, align='c')
            return
        if not me.alive or self.player_input.paused or net.error:
            set_cursor_captured(False)
        kit = HEROES[me.hero]
        if me.alive:
            self.overlays(me, s)
            self.world_markers(me, s, net)
            with self.anchor(.5, .5):
                self.crosshair(me, s)
                self.damage_direction(me, s)
        with self.anchor(.5, 0):
            self.top_bar(me, s, net)
        with self.anchor(1, 0):
            self.killfeed(me, s)
        self.draw_minimap(me, s)
        with self.anchor(0, 0 if me.team == CELLS else 1):
            self.economy(me, s)
        if me.alive:
            with self.anchor(0, 1):
                self.health(me, kit, s)
            with self.anchor(.5, 1):
                self.ultimate_meter(me, kit, s)
            with self.anchor(.5, .5):
                self.prompts(me, s)
            with self.anchor(1, 1):
                self.abilities(me, kit, s)
                self.tx("f1 kit", 1262, 696-0, 11, MUTED, font='m', align='r')
            if self.player_input.kit_card and not self.player_input.paused:
                self.full((4, 8, 12), 175)
                with self.anchor(.5, .5):
                    self.kit_card(me, kit)
        if not me.alive and not s.winner:
            self.full((4, 8, 12), 110)
            with self.anchor(.5, .5):
                self.respawn(me)
        if self.player_input.paused or net.error:
            self.full((4, 8, 12), 170)
        with self.anchor(.5, .5):
            self._center_modals(me, s, net)

    def _center_modals(self, me, s, net):
        if self.player_input.paused or net.error:
            self.sk(340, 230, 600, 260, PANEL, 240)
            self.tx("operacao em andamento", 380, 254, 34, WHITE)
            self.tx("a partida em rede continua durante este menu.", 382, 300, 17, MUTED, font='m')
            if net.error:
                self.fit(net.error, 382, 330, 520, 15, RED_L, font='m')
            self.sbutton("continuar", 380, 380, 160, 48, lambda: setattr(self.player_input, "paused", False), True)
            self.sbutton("configuracoes", 556, 380, 180, 48, lambda: open_settings(self.game))
            self.sbutton("sair da partida", 752, 380, 148, 48, lambda: leave(self.game))
        if s.winner:
            won = s.winner == me.team
            self.sk(330, 300, 620, 100, TEAL if won else RED, 235)
            self.tx("infeccao contida" if s.winner == CELLS else "infeccao estabelecida", 640, 318, 40, WHITE, align='c')
            self.tx("vitoria" if won else "derrota", 640, 362, 20, WHITE, align='c', font='m')

    def on_destroy(self):
        if self.minimap:
            rl.unload_render_texture(self.minimap[0])
        for key, font in self.fonts.items():
            if font is not self.font:
                rl.unload_font(font)
        self.fonts = {}
        super().on_destroy()
