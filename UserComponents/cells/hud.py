"""Combat HUD, first-person weapon silhouette and respawn selection."""
import math
import pyray as rl
from EasyCells3D.Geometry import Vec3
from .ui_base import Canvas
from .catalog import HEROES, CELLS, POINTS, CORE_POSITIONS, PHASE_NAMES, can_select
from .screens import leave
from .layout import SOLIDS, RAMPS
from .cursor import set_cursor_captured
from .hud_portraits import draw_face

# Combat-only palette: menu styling remains owned by Canvas.
INK = (24, 37, 49)
PAPER = (240, 244, 247)
WHITE = (255, 255, 255)
MUTED = (154, 174, 188)
TEAL = (30, 216, 209)
GOLD = (250, 199, 55)
RED = (228, 76, 81)


class CombatHUD(Canvas):
    def __init__(self, arena, player_input):
        super().__init__()
        self.arena, self.player_input = arena, player_input
        self.face_until = 0
        self.face_state = 'normal'
        self.previous = None
        self.colony_until = 0

    def fitted(self, value, x, y, width, size=14, tint=WHITE):
        measured = rl.measure_text_ex(self.font, str(value), size, .4).x
        self.text(value, x, y, min(size, size*width/max(1, measured)), tint)

    def frame(self, x, y, w, h, tint=INK):
        # Six-pixel chamfers, solid fill and a restrained one-pixel edge.
        for inset, fill in ((0, MUTED), (1, tint)):
            xx, yy, ww, hh = x+inset, y+inset, w-2*inset, h-2*inset
            self.panel(xx+6, yy, ww-12, hh, fill)
            self.panel(xx, yy+6, ww, hh-12, fill)
            for row in range(6):
                self.panel(xx+6-row, yy+row, ww-12+row*2, 1, fill)
                self.panel(xx+6-row, yy+hh-row-1, ww-12+row*2, 1, fill)

    def objective(self, actor, s):
        x, y, w = 24, 24, 304
        self.frame(x, y, w, 152)
        self.panel(x+1, y+6, 35, 38, GOLD)
        self.text(f'{s.phase+1:02}', x+6, y+13, 23, INK)
        self.fitted(PHASE_NAMES[s.phase], x+44, y+8, 184, 20)
        seconds = int(max(0, s.remaining))
        self.text(f'{seconds//60:02}:{seconds%60:02}', x+242, y+10, 18, GOLD)
        task = ('Defenda A, B e C' if actor.team == CELLS else 'Contamine duas entradas') if s.phase == 0 else (
            'Colete antigenos / destrua nucleos' if actor.team == CELLS else 'Proteja os nucleos de colonia')
        self.fitted(task, x+44, y+33, 250, 15)
        self.line(x+1, y+55, w-2, MUTED)
        for i, progress in enumerate(s.capture):
            cx = x+51+i*101
            tint = GOLD if progress >= 100 else WHITE
            self.circle(cx, y+75, 12, tint)
            self.circle(cx, y+75, 10, INK)
            self.text('ABC'[i], cx-6, y+64, 18, tint)
            label = 'TOMADO' if progress >= 100 else f'{int(progress)}%'
            self.text(label, cx-(26 if progress >= 100 else 12), y+91, 13, tint)
        self.panel(x+1, y+113, w-2, 24, PAPER)
        self.text(f'Nucleos {sum(hp > 0 for hp in s.cores)}/2', x+10, y+116, 15, INK)
        self.text(f'Colonizacao {int(s.maturity)}%', x+137, y+116, 15,
                  RED if s.elapsed < self.colony_until else INK)
        self.text(f'ANTIGENO {int(s.recognition)}%', x+10, y+136, 12, TEAL)
        self.bar(x+114, y+142, 180, s.recognition/100, TEAL, 3)

    def minimap(self, actor, s):
        x, y, w, cx, cy = 1064, 24, 192, 1160, 116
        self.frame(x, y, w, 236)
        for solid in SOLIDS:
            if solid.name == 'Perimeter':
                continue
            sx, _, sz = solid.position
            sw, _, sd = solid.size
            self.panel(cx+(sx-sw/2)*1.3, cy+(sz-sd/2)*1.3, sw*1.3, sd*1.3,
                       (77, 108, 127) if solid.top >= 4 else (47, 68, 85))
        for ramp in RAMPS:
            self.panel(cx+(ramp.x-2.5)*1.3, cy+min(ramp.start_z, ramp.end_z)*1.3,
                       6.5, abs(ramp.end_z-ramp.start_z)*1.3, (150, 140, 89))
        positions = POINTS if s.phase == 0 else [p for i, p in enumerate(CORE_POSITIONS) if s.cores[i] > 0]
        for i, (px, pz) in enumerate(positions):
            self.panel(cx+px*1.3-4, cy+pz*1.3-4, 8, 8, GOLD)
        for target in self.arena.actors.values():
            if target.slot != actor.slot and target.alive and (target.team == actor.team or actor.reveal > 0):
                self.circle(cx+target.transform.x*1.3, cy+target.transform.z*1.3, 3,
                            TEAL if target.team == actor.team else RED)
        px, py = cx+actor.transform.x*1.3, cy+actor.transform.z*1.3
        self.circle(px, py, 5, WHITE)
        self.circle(px, py, 2, INK)
        forward = self.player_input.camera.transform.forward
        self.circle(px+forward.x*8, py+forward.z*8, 2, WHITE)
        self.panel(x+1, y+184, w-2, 45, PAPER)
        stress_color = RED if s.stress >= 80 else GOLD if s.stress >= 50 else TEAL
        self.text('Systemic Stress', x+10, y+188, 16, INK)
        self.text(f'{int(s.stress)}%', x+148, y+188, 18, INK)
        self.bar(x+10, y+214, w-20, s.stress/100, stress_color, 7)
        if s.stress >= 80:
            self.circle(x+w-8, y+232, 2+math.sin(s.elapsed*3)*.5, RED)

    def health(self, actor, kit, s):
        special = s.immune_cooldown if actor.team == CELLS else actor.special_cd
        snapshot = (actor.hero, actor.health, actor.ability_cd, special, s.phase, s.maturity)
        if self.previous and self.previous[0] == actor.hero:
            if actor.health < self.previous[1]:
                self.face_state, self.face_until = 'hurt', s.elapsed+.65
            elif actor.ability_cd > self.previous[2] or special > self.previous[3]:
                self.face_state, self.face_until = 'special', s.elapsed+1.2
            elif s.phase != self.previous[4]:
                self.face_state, self.face_until = 'success', s.elapsed+1.8
            if s.maturity > self.previous[5]:
                self.colony_until = s.elapsed+1
        else:
            self.face_until = 0
            self.colony_until = 0
        self.previous = snapshot
        low = actor.health <= kit.health*.3
        expression = self.face_state if s.elapsed < self.face_until else 'low' if low else 'normal'
        x, y = 24, 608
        self.frame(x, y, 304, 88, PAPER)
        self.panel(x+6, y+6, 72, 76, INK)
        draw_face(self, actor.hero, expression, x+6, y+6, 72)
        self.text(str(max(0, math.ceil(actor.health))), x+88, y+1, 40, RED if low else INK)
        self.text(f'/ {kit.health} HP', x+158, y+18, 17, INK)
        self.bar(x+88, y+44, 202, actor.health/kit.health, RED if low else TEAL, 10)
        self.fitted(kit.name, x+88, y+61, 198, 16, INK)
        if actor.shield:
            self.text(f'+{int(actor.shield)}', x+252, y+8, 12, INK)
        if low and actor.alive:
            self.text('VIDA BAIXA', x+8, y-19, 14, RED)

    def skill_icon(self, hero, special, x, y, tint):
        # Small biological glyphs, one silhouette per kit, drawn as native UI.
        kind = list(HEROES).index(hero)
        if kind in (0, 3, 7):
            for i in range(3):
                self.panel(x-12+i*8, y-9+i*3, 5, 18-i*3, tint)
        elif kind == 2:
            self.panel(x-2, y-1, 4, 14, tint)
            for i in range(10):
                self.panel(x-i-2, y-i-2, 4, 4, tint)
                self.panel(x+i-2, y-i-2, 4, 4, tint)
        else:
            self.circle(x, y, 11, tint)
            self.circle(x, y, 6, INK)
            for i in range(4+kind):
                angle = i*math.tau/(4+kind)
                self.circle(x+math.cos(angle)*15, y+math.sin(angle)*15, 2, tint)
        if special:
            self.panel(x+10, y-15, 9, 3, GOLD)
            self.panel(x+13, y-18, 3, 9, GOLD)

    def loadout(self, actor, kit, s):
        x, y, w = 1016, 536, 240
        self.frame(x, y, w, 160, PAPER)
        for i in range(3):
            self.panel(x+14+i*7, y+17, 4, 18, INK)
        self.text(f'{actor.weapon.ammo:02}', x+44, y+3, 40, RED if actor.weapon.ammo == 0 else INK)
        self.text(f'/ {kit.magazine:02}', x+96, y+20, 20, INK)
        self.panel(x+201, y+12, 23, 25, INK)
        self.text('R', x+207, y+15, 17, WHITE)
        if actor.weapon.reload_time > 0:
            self.text('RECARGA', x+148, y+9, 10, INK)
            self.text(f'{actor.weapon.reload_time:.1f}s', x+149, y+23, 14, INK)
        self.line(x+8, y+48, w-16, MUTED)
        for i, (key, label, cd) in enumerate((('Q', kit.ability, actor.ability_cd),
                ('F', kit.ultimate, s.immune_cooldown if actor.team == CELLS else actor.special_cd))):
            sx = x+1+i*119
            self.panel(sx, y+50, 119, 102, INK)
            tint = MUTED if cd > 0 or actor.neutralized > 0 or not actor.alive else TEAL
            self.text(key, sx+9, y+58, 16, WHITE)
            self.skill_icon(actor.hero, i == 1, sx+61, y+75, tint)
            if cd > 0:
                self.panel(sx+44, y+66, 34, 21, INK)
                self.text(str(math.ceil(cd)), sx+49, y+66, 18, WHITE)
            self.fitted(label, sx+7, y+100, 105, 14, WHITE)
            status = f'{cd:.1f}s' if cd > 0 else 'BLOQUEADA' if actor.neutralized > 0 else 'PRONTO' if actor.alive else 'INATIVA'
            self.fitted(status, sx+14, y+125, 96, 14, tint)
        self.panel(x+119, y+50, 1, 102, MUTED)

    def interaction(self, actor, s):
        if not actor.alive or actor.team != CELLS or s.phase == 0 or self.player_input.paused:
            return
        for sample in self.arena.samples:
            delta = Vec3(*sample['pos'])-actor.transform.position
            distance = delta.magnitude()
            if distance <= 2.8 and (distance < .001 or self.game.physics_world.raycast(actor.transform.position, delta, distance, 1) is None):
                self.frame(548, 408, 184, 30)
                self.text('[E] Coletar antigeno', 559, 414, 14, WHITE)
                break

    def marker(self, position, title, tint):
        camera = self.player_input.camera
        if (position-camera.transform.position).dot(camera.transform.forward) <= 0:
            return
        p = rl.get_world_to_screen(position.to_raylib(), camera.rl_camera)
        x, y = (p.x-self.ox)/self.scale, (p.y-self.oy)/self.scale
        if (x < 380 and y < 192) or (x > 1016 and y < 276) or (x > 968 and y > 520):
            return
        if 30 < x < 1250 and 145 < y < 570:
            width = rl.measure_text_ex(self.font, title, 12, .4).x
            self.text(title, x-width/2+1, y-9, 12, INK)
            self.text(title, x-width/2, y-10, 12, tint)

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
        # Respawn and pause controls are screen-space UI, so release capture
        # here as well as in PlayerInput. This also covers the frame in which
        # the server reports a death or a network error.
        if not actor.alive or self.player_input.paused or net.error:
            set_cursor_captured(False)
        kit = HEROES[actor.hero]
        self.objective(actor, s)
        self.minimap(actor, s)
        for i, (x, z) in enumerate(POINTS):
            if s.phase == 0:
                self.marker(Vec3(x, 2.6, z), f"{'ABC'[i]} / {int(s.capture[i])}%", (162, 237, 209))
        for i, (x, z) in enumerate(CORE_POSITIONS):
            if s.phase >= 1 and s.cores[i] > 0:
                self.marker(Vec3(x, 2.8, z), f"{int(s.cores[i])} HP", (241, 178, 125))
        for target in a.actors.values():
            if target.slot == actor.slot or not target.alive:
                continue
            chemotaxis = actor.hero == "neutrophil" and target.health < HEROES[target.hero].health*.5 and (target.transform.position-actor.transform.position).magnitude() < 15
            if target.team == actor.team or actor.reveal > 0 or chemotaxis:
                self.marker(target.transform.position+Vec3(0, 1.4, 0), net.roster[target.slot]["name"][:9] + (f"  {int(target.health)} HP" if target.health < HEROES[target.hero].health else ""), (142, 239, 204) if target.team == actor.team else (255, 171, 127))
        if actor.alive:
            # Stylized viewmodel, tied to local weapon shot and reload state.
            bob = math.sin(s.elapsed*8)*2
            recoil = 10 if actor.weapon.timer > 0.05 or actor.hit_marker > 0 else 0
            self.panel(893, 548+bob+recoil, 140, 191, kit.color)
            self.panel(951, 451+bob+recoil, 86, 178, (51, 70, 66))
            self.panel(971, 419+bob+recoil, 46, 96, (80, 96, 83))
            self.panel(982, 414+bob+recoil, 25, 23, (27, 39, 36))
            self.panel(913, 580+bob+recoil, 109, 26, (226, 206, 172))
            cross = (240, 190, 124) if actor.hit_marker > 0 else WHITE
            self.panel(629, 359, 7, 2, cross)
            self.panel(645, 359, 7, 2, cross)
            self.panel(639, 349, 2, 7, cross)
            self.panel(639, 365, 2, 7, cross)
            self.circle(640, 360, 1.5, cross)
            if actor.hurt > 0:
                self.panel(0, 0, 1280, 9, RED, 180)
                self.panel(0, 711, 1280, 9, RED, 180)
            in_cloud = any(z["kind"] == "cloud" and (actor.transform.position-Vec3(*z["pos"])).magnitude() < z["radius"] for z in a.zones)
            if in_cloud:
                self.panel(0, 150, 1280, 450, (128, 115, 149), 90)
        self.health(actor, kit, s)
        self.loadout(actor, kit, s)
        self.interaction(actor, s)
        if s.notice_time > 0:
            self.frame(400, 192, 480, 32)
            self.fitted(s.notice, 412, 200, 456, 14, GOLD)
        if s.event:
            self.frame(440, 232, 400, 30)
            self.fitted(f"{s.event.upper()}  /  {'INICIA EM '+str(int(s.event_warning)+1)+'s' if s.event_warning > 0 else str(int(s.event_time)+1)+'s'}", 452, 239, 376, 14, GOLD)
        if not actor.alive:
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

    def respawn(self, actor):
        self.panel(260, 317, 760, 214, PAPER)
        self.text(f"REFORCO CHEGANDO EM {max(1, int(actor.respawn)+1)}s", 286, 335, 29)
        self.text("Escolha seu proximo personagem entre as vagas disponiveis.", 288, 378, 16, MUTED)
        net, s = self.game.session, self.arena.state
        for i, key in enumerate(h for h in HEROES if HEROES[h].team == actor.team):
            enabled = can_select(key, actor.team, net.roster, s.recognition, s.infected, actor.slot)
            self.button(HEROES[key].name.split()[0], 284+i*183, 420, 170, lambda h=key: net.choose(h), net.roster[actor.slot]["hero"] == key, enabled)
        self.text("B CELL: 50% antigeno    /    KILLER T: tecido infectado    /    Limites por equipe ativos", 288, 490, 13, MUTED)
