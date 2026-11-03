"""HUD de combate: objetivos, economia, efeitos, respawn/espectador e minimapa."""
import math
import pyray as rl
from EasyCells3D.Geometry import Vec3
from .ui_base import Canvas
from .catalog import HEROES, CELLS, BALANCE, can_select, unlocked
from .screens import leave
from .cursor import set_cursor_captured
from .hud_portraits import draw_face
from .layout import X0, X1, Z0, Z1, RECON, RBC_NODES, DESTINATIONS

INK = (24, 37, 49)
PAPER = (240, 244, 247)
WHITE = (255, 255, 255)
MUTED = (154, 174, 188)
TEAL = (30, 216, 209)
GOLD = (250, 199, 55)
RED = (228, 76, 81)
PURPLE = (176, 120, 220)
SKY = (111, 197, 244)

EFFECTS = (('slow', 'LENTO', (237, 184, 77)), ('haste', 'VELOZ', TEAL), ('guard', 'PROTEGIDO', GOLD),
           ('marked', 'MARCADO', SKY), ('capsule', 'CAPSULA', PURPLE), ('boost', 'ATIVADO', RED))


class CombatHUD(Canvas):
    def __init__(self, arena, player_input):
        super().__init__()
        self.arena, self.player_input = arena, player_input
        self.face_until = 0
        self.face_state = 'normal'
        self.previous = None
        self.minimap = None

    # -- utilitarios ------------------------------------------------------
    def fitted(self, value, x, y, width, size=14, tint=WHITE):
        measured = rl.measure_text_ex(self.font, str(value), size, .4).x
        self.text(value, x, y, min(size, size*width/max(1, measured)), tint)

    def frame(self, x, y, w, h, tint=INK, alpha=235):
        self.panel(x, y, w, h, MUTED, alpha)
        self.panel(x+1, y+1, w-2, h-2, tint, alpha)

    def world_to_screen(self, position):
        camera = self.player_input.camera
        if (position-camera.transform.position).dot(camera.transform.forward) <= 0:
            return None
        p = rl.get_world_to_screen(position.to_raylib(), camera.rl_camera)
        return (p.x-self.ox)/self.scale, (p.y-self.oy)/self.scale

    def marker(self, position, title, tint, icon=None):
        p = self.world_to_screen(position)
        if p is None:
            return
        x, y = p
        if not (20 < x < 1260 and 20 < y < 700):
            return
        if icon:
            self.circle(x, y-16, 6, tint)
            self.circle(x, y-16, 3, INK)
        width = rl.measure_text_ex(self.font, title, 12, .4).x
        self.text(title, x-width/2+1, y-7, 12, INK)
        self.text(title, x-width/2, y-8, 12, tint)

    # -- minimapa ---------------------------------------------------------
    def build_minimap(self):
        from .scenery import draw_district
        w, h = 496, int(496*(Z1-Z0)/(X1-X0))
        target = rl.load_render_texture(w, h)
        cam = rl.Camera3D(rl.Vector3(0, 300, (Z0+Z1)/2), rl.Vector3(0, 0, (Z0+Z1)/2), rl.Vector3(0, 0, -1),
                          Z1-Z0, rl.CameraProjection.CAMERA_ORTHOGRAPHIC)
        rl.begin_texture_mode(target)
        rl.clear_background(rl.Color(60, 70, 74, 255))
        rl.begin_mode_3d(cam)
        draw_district(rl.Vector3(0, 300, 0), 0, .0001)
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

    def map_point(self, wx, wz, cx, cy, center, scale):
        return cx+(wx-center[0])*scale, cy+(wz-center[1])*scale

    def draw_minimap(self, actor, s):
        x, y, size = 1036, 20, 224
        self.frame(x, y, size, size+30)
        cx, cy = x+size/2, y+size/2+2
        p = actor.transform.position if actor.alive else Vec3(*self.arena.path.at(s.escort))
        center = (p.x, p.z)
        span = 90.0
        scale = size/span
        if self.minimap:
            texture, w, h = self.minimap
            u = (center[0]-span/2-X0)/(X1-X0)*w
            v = (center[1]-span/2-Z0)/(Z1-Z0)*h
            src = rl.Rectangle(u, h-v-span/(Z1-Z0)*h, span/(X1-X0)*w, -span/(Z1-Z0)*h)
            rl.draw_texture_pro(texture.texture, src, self.rect(x+2, y+2, size-4, size-4), rl.Vector2(0, 0), 0, rl.WHITE)

        def inside(px, py):
            return x+4 < px < x+size-4 and y+4 < py < y+size-2

        def dot(wx, wz, r, tint):
            px, py = self.map_point(wx, wz, cx, cy, center, scale)
            if inside(px, py):
                self.circle(px, py, r, tint)
        path = self.arena.path
        for k in range(0, int(s.escort_total), 3):
            q = path.at(k)
            dot(q[0], q[2], 1.2, TEAL if k < s.escort else (230, 230, 230))
        head = path.at(s.escort)
        dot(head[0], head[2], 5, RED if s.blocked_by else GOLD)
        for letter, doors in DESTINATIONS.items():
            n = RBC_NODES[doors[0]]
            px, py = self.map_point(n[0], n[2], cx, cy, center, scale)
            if inside(px, py):
                self.panel(px-6, py-7, 12, 13, SKY)
                self.text(letter, px-4, py-7, 12, INK)
        for cell in self.arena.rbc_view.cells.values():
            if cell['state'] not in ('dead', 'inside'):
                dot(cell['pos'][0], cell['pos'][2], 2, (236, 80, 76))
        for colony in s.colonies:
            if actor.team != CELLS or s.reveal > 0 or math.dist(colony['pos'], actor.feet) < 25:
                dot(colony['pos'][0], colony['pos'][2], 4, PURPLE)
        if s.recon_available():
            dot(RECON[0], RECON[2], 4, SKY)
        for target in self.arena.actors.values():
            if target.slot != actor.slot and target.alive and (target.team == actor.team or target.reveal > 0 or target.marked > 0
                                                               or (actor.team == CELLS and s.reveal > 0)):
                dot(target.transform.x, target.transform.z, 3, TEAL if target.team == actor.team else RED)
        self.circle(cx, cy, 5, WHITE)
        self.circle(cx, cy, 2, INK)
        fwd = self.player_input.camera.transform.forward
        self.circle(cx+fwd.x*9, cy+fwd.z*9, 2, WHITE)
        self.text("BAIRRO ARTERIAL", x+8, y+size+6, 13, WHITE)
        self.text("N", x+size/2-4, y+4, 12, WHITE)

    # -- paineis ----------------------------------------------------------
    def objective(self, actor, s):
        x, y, w = 20, 20, 330
        self.frame(x, y, w, 176)
        if s.wound_closed:
            self.panel(x+1, y+1, w-2, 26, TEAL)
            self.text("FERIDA FECHADA", x+10, y+4, 18, INK)
        else:
            self.panel(x+1, y+1, w-2, 26, GOLD)
            self.text("ESCOLTA DAS PLAQUETAS", x+10, y+4, 18, INK)
            self.text(f"{int(100*s.escort/s.escort_total)}%", x+w-50, y+4, 18, INK)
        self.bar(x+10, y+34, w-20, s.escort/s.escort_total, RED if s.blocked_by else TEAL, 8)
        if s.blocked_by and not s.wound_closed:
            names = ", ".join(HEROES[self.arena.actors[sl].hero].name.split()[0] for sl in s.blocked_by if sl in self.arena.actors)
            self.fitted(f"BLOQUEADA: {names} a frente", x+10, y+46, w-20, 14, RED)
        elif not s.wound_closed:
            self.fitted("Avancando - bacterias a frente param as plaquetas", x+10, y+46, w-20, 13, MUTED)
        else:
            self.fitted("Renascimento pela entrada cortado", x+10, y+46, w-20, 13, MUTED)
        # Infection
        infection = s.infection()
        self.text("INFECCAO", x+10, y+68, 13, PURPLE)
        self.text(f"{int(infection)}/{BALANCE['infection_goal']}", x+w-70, y+66, 15, WHITE)
        self.bar(x+80, y+72, w-160, infection/BALANCE['infection_goal'], PURPLE, 8)
        self.text(f"Colonias: {len(s.colonies)}", x+10, y+86, 13, WHITE)
        if s.reveal > 0:
            self.text(f"REVELADAS {int(s.reveal)}s", x+130, y+86, 13, SKY)
        # Recognition (antigens) and unlocks
        self.text("ANTIGENO", x+10, y+108, 13, TEAL)
        bx, bw = x+80, w-90
        self.bar(bx, y+112, bw, s.recognition/100, TEAL, 8)
        for hero in ("b_cell", "killer_t"):
            key = 'unlock_'+hero
            mx = bx+bw*BALANCE[key]/100
            self.panel(mx-1, y+108, 2, 16, WHITE)
            ok = unlocked(hero, s.recognition)
            self.text(HEROES[hero].name.split()[0]+(" OK" if ok else ""), mx-24, y+124, 11, GOLD if ok else MUTED)
        task = self.task(actor, s)
        self.panel(x+1, y+146, w-2, 29, PAPER)
        self.fitted(task, x+10, y+152, w-20, 14, INK)

    def task(self, actor, s):
        if actor.team == CELLS:
            if not s.wound_closed:
                return "Libere a escolta, proteja hemacias, ataque colonias"
            if s.recon_available():
                return "Ocupe o posto da torre para revelar colonias"
            return "Destrua colonias e elimine as bacterias restantes"
        if not s.wound_closed:
            return "Bloqueie a escolta, cace hemacias, construa colonias"
        return "Desenvolva colonias e defenda a rede (meta de infeccao)"

    def economy(self, actor, s):
        x, y = 1036, 282
        if actor.team == CELLS:
            if s.wound_closed:
                self.frame(x, y, 224, 46)
                status = (f"Canalizando {int(100*s.recon/BALANCE['recon_channel'])}%" if s.recon > 0 else
                          "Disponivel na torre" if s.recon_available() else f"Recarga {int(s.recon_cooldown)}s")
                self.text("RECONHECIMENTO", x+8, y+4, 13, SKY)
                self.fitted(status, x+8, y+22, 208, 14, WHITE)
            return
        carried = s.resources.get(actor.slot, 0)
        own = len(s.colonies_of(actor.slot))
        self.frame(x, y, 224, 78)
        self.text("RECURSOS", x+8, y+4, 13, (236, 110, 90))
        self.text(str(carried), x+90, y, 22, WHITE)
        self.text(f"custo {BALANCE['colony_cost']}", x+140, y+6, 12, MUTED)
        self.text(f"Suas colonias {own}/{BALANCE['colony_limit']}", x+8, y+28, 14, WHITE)
        self.fitted("[G] segurar: construir   [E] entregar recursos", x+8, y+52, 208, 12, MUTED)

    def health(self, actor, kit, s):
        snapshot = (actor.hero, actor.health.value, actor.ability_cd, actor.charge)
        if self.previous and self.previous[0] == actor.hero:
            if actor.health.value < self.previous[1]:
                self.face_state, self.face_until = 'hurt', s.elapsed+.65
            elif actor.ability_cd > self.previous[2] or actor.charge < self.previous[3]-50:
                self.face_state, self.face_until = 'special', s.elapsed+1.2
        else:
            self.face_until = 0
        self.previous = snapshot
        low = actor.health.value <= kit.health*.3
        expression = self.face_state if s.elapsed < self.face_until else 'low' if low else 'normal'
        x, y = 20, 612
        self.frame(x, y, 300, 88, PAPER)
        self.panel(x+6, y+6, 72, 76, INK)
        draw_face(self, actor.hero, expression, x+6, y+6, 72)
        self.text(str(max(0, math.ceil(actor.health.value))), x+88, y+1, 40, RED if low else INK)
        self.text(f'/ {kit.health} HP', x+158, y+18, 17, INK)
        self.bar(x+88, y+44, 200, actor.health.value/kit.health, RED if low else TEAL, 10)
        if actor.shield.value:
            self.bar(x+88, y+56, 200*min(1, actor.shield.value/200), 1, SKY, 4)
            self.text(f'+{int(actor.shield.value)}', x+252, y+8, 12, INK)
        self.fitted(kit.name, x+88, y+63, 196, 16, INK)
        # Active effects with remaining time.
        ex = x
        for attr, label, tint in EFFECTS:
            value = getattr(actor, attr, 0)
            if value > 0:
                self.panel(ex, y-26, 90, 20, tint)
                self.text(f"{label} {value:.0f}s", ex+5, y-24, 12, INK)
                ex += 94
        if actor.in_zone('cloud', enemy=True):
            self.panel(ex, y-26, 90, 20, PURPLE)
            self.text("NUVEM", ex+5, y-24, 12, INK)

    def loadout(self, actor, kit, s):
        x, y, w = 1016, 556, 244
        self.frame(x, y, w, 144, PAPER)
        self.text(f'{actor.weapon.ammo:02}', x+12, y+2, 36, RED if actor.weapon.ammo == 0 else INK)
        self.text(f'/ {kit.magazine:02}', x+60, y+16, 18, INK)
        if actor.weapon.reload_time > 0:
            self.text(f'RECARGA {actor.weapon.reload_time:.1f}s', x+120, y+14, 13, INK)
        slots = (('RMB', kit.secondary, actor.secondary_cd, False), ('Q', kit.ability, actor.ability_cd, False),
                 ('F', kit.ultimate, 0 if actor.charge >= 100 else 100-actor.charge, True))
        for i, (key, label, cd, special) in enumerate(slots):
            sx = x+2+i*80
            self.panel(sx, y+46, 78, 96, INK)
            ready = cd <= 0 and actor.alive
            tint = TEAL if ready else MUTED
            if special:
                tint = GOLD if ready else MUTED
            self.text(key, sx+6, y+50, 14, WHITE)
            if special:
                self.text(f"{int(actor.charge)}%", sx+30, y+66, 20, tint)
                self.bar(sx+6, y+92, 66, actor.charge/100, GOLD, 5)
            elif cd > 0:
                self.text(f"{cd:.1f}", sx+28, y+66, 20, WHITE)
            else:
                self.text("OK", sx+30, y+66, 20, tint)
            self.fitted(label, sx+5, y+108, 70, 12, WHITE)
            self.fitted("PRONTO" if ready else ("CARGA" if special else "RECARGA"), sx+5, y+124, 70, 11, tint)

    def crosshair(self, actor):
        if actor.hero == 'b_cell' and actor.zoom:
            # Scope: dark vignette with a precise reticle.
            self.panel(0, 0, 1280, 720, (10, 14, 18), 90)
            self.circle(640, 360, 220, (10, 14, 18), 0)
            self.panel(400, 359, 480, 2, WHITE)
            self.panel(639, 140, 2, 440, WHITE)
            self.circle(640, 360, 3, RED)
            return
        cross = (240, 190, 124) if actor.hit_marker > 0 else WHITE
        self.panel(629, 359, 7, 2, cross)
        self.panel(645, 359, 7, 2, cross)
        self.panel(639, 349, 2, 7, cross)
        self.panel(639, 365, 2, 7, cross)
        if actor.hit_marker > 0:
            for i in range(5):
                for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    self.panel(640+sx*(8+i)-1, 360+sy*(8+i)-1, 3, 3, RED if actor.kill_marker > 0 else WHITE)
        if actor.kill_marker > 0:
            self.text("ELIMINADO", 598, 384, 15, RED)
        if actor.absorbed > 0:
            self.text("ABSORVIDO", 600, 330, 13, SKY)

    def damage_direction(self, actor, s):
        camera = self.player_input.camera
        fwd = camera.transform.forward
        yaw = math.atan2(fwd.x, -fwd.z)
        p = actor.transform.position
        for ox, oz, t in actor.hurt_from:
            age = s.elapsed-t
            if age > 1.2 or age < 0:
                continue
            ang = math.atan2(ox-p.x, -(oz-p.z))-yaw
            alpha = int(220*(1-age/1.2))
            for k in range(-3, 4):
                a = ang+k*.06
                self.circle(640+math.sin(a)*120, 360-math.cos(a)*120, 5, RED, alpha)

    def prompts(self, actor, s):
        if actor.team == CELLS or not actor.alive:
            return
        if actor.build:
            k = actor.build['progress']/BALANCE['colony_build_time']
            self.frame(520, 420, 240, 36)
            self.text("CONSTRUINDO COLONIA", 532, 424, 13, WHITE)
            self.bar(532, 442, 216, k, PURPLE, 6)
        elif actor.controls.get('build') or (actor.previous.get('build')):
            if actor.build_problem:
                self.frame(500, 420, 280, 30)
                self.fitted(actor.build_problem, 512, 427, 256, 14, RED)
        else:
            colony = self.arena.nearest_colony(actor.feet, 3.5)
            if colony and s.resources.get(actor.slot, 0) > 0 and colony['dev'] < BALANCE['colony_dev_cap']:
                self.frame(520, 420, 240, 30)
                self.text("[E] Entregar recursos", 534, 426, 14, WHITE)

    def world_markers(self, actor, s, net):
        a = self.arena
        if not s.wound_closed:
            head = a.path.at(s.escort)
            self.marker(Vec3(head[0], head[1]+2.6, head[2]), "PLAQUETAS" + (" - BLOQUEADAS" if s.blocked_by else ""),
                        RED if s.blocked_by else GOLD, True)
        elif s.recon_available() and actor.team == CELLS:
            self.marker(Vec3(RECON[0], RECON[1]+2.5, RECON[2]), "RECONHECIMENTO", SKY, True)
        for colony in s.colonies:
            mine = actor.team != CELLS
            near = math.dist(colony['pos'], actor.feet) < 25
            if mine or near or s.reveal > 0:
                hp = int(colony['hp'])
                prot = int(100*s.protection(colony['id']))
                self.marker(Vec3(colony['pos'][0], colony['pos'][1]+3.4, colony['pos'][2]),
                            f"COLONIA {hp} HP  dev {int(colony['dev'])}  prot {prot}%", PURPLE, True)
        if actor.team != CELLS:
            for cell in a.rbc_view.cells.values():
                if cell['state'] not in ('dead', 'inside') and math.dist(cell['pos'], actor.feet) < 30:
                    self.marker(Vec3(cell['pos'][0], cell['pos'][1]+2.2, cell['pos'][2]), "O2", (236, 110, 90))
        for drop in a.drops:
            if math.dist(drop['pos'], actor.feet) < 25:
                label = "RECURSO" if drop['kind'] == 'resource' else "ANTIGENO"
                self.marker(Vec3(drop['pos'][0], drop['pos'][1]+1.2, drop['pos'][2]), label,
                            (236, 110, 90) if drop['kind'] == 'resource' else TEAL)
        for target in a.actors.values():
            if target.slot == actor.slot or not target.alive:
                continue
            chemotaxis = actor.hero == "neutrophil" and target.health.value < HEROES[target.hero].health*.5 and \
                (target.transform.position-actor.transform.position).magnitude() < 15
            if target.team == actor.team or target.reveal > 0 or target.marked > 0 or chemotaxis:
                hp = f"  {int(target.health.value)} HP" if target.health.value < HEROES[target.hero].health else ""
                self.marker(target.transform.position+Vec3(0, 1.4, 0), net.roster.value[target.slot]["name"][:9]+hp,
                            (142, 239, 204) if target.team == actor.team else (255, 171, 127))

    def feed(self, s):
        if s.notice_time > 0:
            self.frame(390, 20, 500, 30)
            self.fitted(s.notice, 402, 27, 476, 15, GOLD)
        for i, line in enumerate(reversed(s.feed[-4:-1] if s.notice_time > 0 else s.feed[-3:])):
            self.fitted(line, 404, 56+i*17, 470, 12, PAPER)

    # -- respawn / espectador -------------------------------------------------
    def respawn(self, actor):
        net, s = self.game.session, self.arena.state
        self.panel(240, 300, 800, 250, PAPER, 240)
        if actor.waiting:
            self.text("AGUARDANDO UMA COLONIA", 266, 316, 28, RED)
            self.text("Sem entrada nem colonia: um aliado vivo pode construir e resgatar voce.", 268, 356, 15, MUTED)
        else:
            self.text(f"REFORCO EM {max(1, int(actor.respawn)+1)}s", 266, 316, 28)
            self.text("Escolha o heroi e, como bacteria, onde renascer.", 268, 356, 15, MUTED)
        heroes = [h for h in HEROES if HEROES[h].team == actor.team]
        for i, key in enumerate(heroes):
            enabled = can_select(key, actor.team, net.roster.value, s.recognition, actor.slot)
            self.button(HEROES[key].name.split()[0], 262+i*190, 384, 180, lambda h=key: net.choose(h),
                        net.roster.value[actor.slot]["hero"] == key, enabled, h=40)
        if actor.team != CELLS:
            options = actor.spawn_options()
            for i, option in enumerate(options[:5]):
                label = "ENTRADA" if option[0] == 'entrance' else f"COLONIA {option[1]}"
                chosen = actor.spawn_choice == option or (actor.spawn_choice not in options and i == 0)
                self.button(label, 262+i*152, 440, 144, lambda o=option: setattr(actor, 'spawn_choice', o), chosen, h=36)
        if self.player_input.spectate_reason:
            self.text(self.player_input.spectate_reason, 268, 492, 14, MUTED)
        target = self.player_input.camera_target
        if target is not None and target in self.arena.actors:
            self.text(f"Camera: {net.roster.value[target]['name']}", 268, 512, 14, INK)
        self.text(f"B CELL: {BALANCE['unlock_b_cell']}% antigeno  /  KILLER T: {BALANCE['unlock_killer_t']}%", 700, 512, 12, MUTED)

    # -- render -----------------------------------------------------------
    def render(self):
        self.layout()
        net, a = self.game.session, self.arena
        s = a.state
        actor = a.actors.get(net.local_slot)
        if actor is None:
            set_cursor_captured(False)
            self.panel(400, 300, 480, 100, INK)
            self.text("SINCRONIZANDO COM O SERVIDOR...", 425, 339, 20, WHITE)
            return
        if not actor.alive or self.player_input.paused or net.error:
            set_cursor_captured(False)
        kit = HEROES[actor.hero]
        if actor.alive:
            self.world_markers(actor, s, net)
            if actor.in_zone('cloud', enemy=True):
                self.panel(0, 0, 1280, 720, (128, 115, 149), 150)
            self.crosshair(actor)
            self.damage_direction(actor, s)
            if actor.hurt > 0:
                self.panel(0, 0, 1280, 8, RED, 180)
                self.panel(0, 712, 1280, 8, RED, 180)
        self.objective(actor, s)
        self.draw_minimap(actor, s)
        self.economy(actor, s)
        self.feed(s)
        self.health(actor, kit, s)
        self.loadout(actor, kit, s)
        self.prompts(actor, s)
        if not actor.alive and not s.winner:
            self.respawn(actor)
        if self.player_input.paused or net.error:
            self.panel(0, 0, 1280, 720, INK, 160)
            self.panel(350, 224, 580, 278, PAPER)
            self.text("OPERACAO EM ANDAMENTO", 383, 250, 29)
            self.text("A partida em rede continua durante este menu.", 386, 299, 17, MUTED)
            if net.error:
                self.text(net.error[:66], 381, 338, 14, RED)
            self.button("CONTINUAR", 383, 384, 238, lambda: setattr(self.player_input, "paused", False), True)
            self.button("SAIR DA PARTIDA", 640, 384, 255, lambda: leave(self.game))
        if s.winner:
            self.panel(310, 318, 660, 84, INK, 245)
            self.text("INFECCAO CONTIDA" if s.winner == CELLS else "INFECCAO ESTABELECIDA", 348, 340, 32, WHITE)

    def on_destroy(self):
        if self.minimap:
            rl.unload_render_texture(self.minimap[0])
        super().on_destroy()
