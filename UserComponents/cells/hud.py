"""Combat HUD, first-person weapon silhouette and respawn selection."""
import math
import pyray as rl
from EasyCells3D.Geometry import Vec3
from .ui_base import Canvas, INK, MUTED, PAPER, TEAL, RED, LINE, WHITE
from .catalog import HEROES, CELLS, POINTS, CORE_POSITIONS, PHASE_NAMES, can_select
from .screens import leave
from .layout import SOLIDS, RAMPS
from .cursor import set_cursor_captured


class CombatHUD(Canvas):
    def __init__(self, arena, player_input):
        super().__init__()
        self.arena, self.player_input = arena, player_input

    def marker(self, position, title, tint):
        camera = self.player_input.camera
        if (position-camera.transform.position).dot(camera.transform.forward) <= 0:
            return
        p = rl.get_world_to_screen(position.to_raylib(), camera.rl_camera)
        x, y = (p.x-self.ox)/self.scale, (p.y-self.oy)/self.scale
        if 30 < x < 1250 and 145 < y < 570:
            self.panel(x-36, y-14, 72, 27, INK, 215)
            self.text(title, x-28, y-10, 13, tint)

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
        self.panel(26, 22, 305, 75, INK, 235)
        self.text("ABRASION", 43, 31, 22, WHITE)
        self.text("DEFESA IMUNE" if actor.team == CELLS else "INVASAO BACTERIANA", 44, 64, 13, (123, 210, 185))
        self.panel(361, 22, 558, 75, INK, 240)
        self.text(f"0{s.phase+1}  /  {PHASE_NAMES[s.phase]}", 380, 33, 23, WHITE)
        self.text(f"{int(max(0, s.remaining))//60:02}:{int(max(0,s.remaining))%60:02}", 829, 34, 25, WHITE)
        task = ("Defenda A, B e C" if actor.team == CELLS else "Contamine 2 das 3 entradas") if s.phase == 0 else (
            "E: colete antigenos / destrua nucleos" if actor.team == CELLS else "Proteja os dois nucleos de colonia")
        self.text(task, 381, 69, 14, (184, 216, 197))
        self.panel(949, 22, 305, 75, INK, 235)
        self.text(f"SYSTEMIC STRESS   {int(s.stress)}%", 967, 34, 17, WHITE)
        self.bar(968, 66, 266, s.stress/100, RED if s.stress > 60 else (205, 177, 97))
        self.panel(26, 109, 305, 42, INK, 220)
        self.text(f"ANTIGEN RECOGNITION  {int(s.recognition)}%", 42, 118, 14, WHITE)
        self.bar(43, 143, 270, s.recognition/100, (92, 192, 173), 3)
        for i in range(3):
            x = 439+i*138
            self.panel(x, 110, 125, 36, INK, 220)
            self.text(f"{'ABC'[i]}   {int(s.capture[i])}%", x+15, 117, 17, (240, 165, 115) if s.capture[i] >= 100 else WHITE)
        if s.phase >= 1:
            self.panel(420, 158, 438, 35, INK, 230)
            self.text(f"NUCLEOS {sum(hp > 0 for hp in s.cores)}/2    COLONIZACAO {int(s.maturity)}%", 444, 165, 16, WHITE)
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
                self.marker(target.transform.position+Vec3(0, 1.4, 0), net.roster[target.slot]["name"][:9], (142, 239, 204) if target.team == actor.team else (255, 171, 127))
        # Schematic minimap always uses the same team and objective colors.
        self.panel(1090, 111, 164, 182, INK, 225)
        self.text("DISTRITO / ALT. " + str(max(0, round(actor.transform.y-.95))) + "m", 1102, 120, 10, WHITE)
        for solid in SOLIDS:
            if solid.name == 'Perimeter':
                continue
            x, y, z = solid.position
            w, h, d = solid.size
            self.panel(1172+(x-w/2)*1.15, 213+(z-d/2)*1.15, w*1.15, d*1.15,
                       (85, 119, 107) if solid.top >= 4 else (60, 83, 74))
        for ramp in RAMPS:
            self.panel(1172+(ramp.x-2.5)*1.15, 213+min(ramp.start_z, ramp.end_z)*1.15,
                       5*1.15, abs(ramp.end_z-ramp.start_z)*1.15, (170, 155, 99))
        for target in a.actors.values():
            if target.alive and (target.team == actor.team or actor.reveal > 0):
                self.circle(1172+target.transform.x*1.15, 213+target.transform.z*1.15, 3 if target.slot != actor.slot else 5,
                            (130, 234, 192) if target.team == actor.team else (241, 133, 97))
        for x, z in POINTS:
            self.panel(1169+x*1.15, 210+z*1.15, 6, 6, (236, 213, 141))
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
            if actor.hurt > 0:
                self.panel(0, 0, 1280, 9, RED, 180)
                self.panel(0, 711, 1280, 9, RED, 180)
            in_cloud = any(z["kind"] == "cloud" and (actor.transform.position-Vec3(*z["pos"])).magnitude() < z["radius"] for z in a.zones)
            if in_cloud:
                self.panel(0, 150, 1280, 450, (128, 115, 149), 90)
        self.panel(26, 592, 350, 101, INK, 240)
        self.text(kit.name, 43, 603, 17, WHITE)
        self.text(f"{int(actor.health):03}", 43, 624, 40, WHITE)
        self.text(f"/ {kit.health} HP", 122, 648, 14, (182, 208, 191))
        if actor.shield:
            self.text(f"+ {int(actor.shield)} CAPSULE", 223, 645, 13, (137, 213, 237))
        self.bar(44, 681, 312, actor.health/kit.health, (105, 208, 177))
        for label, key, cd, x in [(kit.ability, "Q", actor.ability_cd, 397),
                                   (kit.ultimate, "F", s.immune_cooldown if actor.team == CELLS else actor.special_cd, 644)]:
            self.panel(x, 630, 229, 63, INK, 240)
            self.text(key, x+12, 639, 30, WHITE)
            self.text(f"{int(cd)+1}s" if cd > 0 else "PRONTO", x+54, 638, 16, (230, 191, 115) if cd > 0 else (125, 222, 184))
            self.text(label[:26], x+13, 674, 11, WHITE)
        self.panel(1064, 616, 190, 77, INK, 240)
        self.text(f"{actor.weapon.ammo:02} / {kit.magazine}", 1093, 626, 32, WHITE)
        self.text("RECARREGANDO" if actor.weapon.reload_time > 0 else "R  RECARREGAR", 1083, 668, 13, (184, 216, 197))
        self.text(f"WASD mover   SHIFT correr   ESPACO salto {kit.jump_height:.1f}m   E coletar   RMB secundario   ESC menu", 30, 566, 12, WHITE)
        if s.notice_time > 0:
            self.panel(280, 215, 720, 38, INK, 235)
            self.text(s.notice[:85], 300, 225, 16, (227, 221, 157))
        if s.event:
            self.panel(365, 274, 550, 30, INK, 225)
            self.text(f"{s.event.upper()}  /  {'INICIA EM '+str(int(s.event_warning)+1)+'s' if s.event_warning > 0 else str(int(s.event_time)+1)+'s'}", 389, 279, 17, (238, 198, 118))
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
