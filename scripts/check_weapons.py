"""Capturas das armas em primeira pessoa (e de um oponente em terceira) numa partida de treino real.

    .venv\\Scripts\\python.exe scripts\\check_weapons.py [--only neutrophil,b_cell] [--third]

Salva PNGs em .scratch/weapons-game/. Para cada herói: parado, atirando (projétil em voo),
recarregando, golpeando e correndo. Bots ficam parados. Com --third, também fotografa cada herói
de frente/lado, atirando, visto por outro jogador.
"""
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyray as rl  # noqa: E402
from EasyCells3D import Game  # noqa: E402
from EasyCells3D.Components import Component  # noqa: E402
from EasyCells3D.Geometry import Vec3  # noqa: E402
from UserComponents.cells.catalog import HEROES, CELLS  # noqa: E402
from UserComponents.cells.session import connect  # noqa: E402

OUT = ROOT / '.scratch' / 'weapons-game'
SPOT = (0, 1, 60)
YAW, PITCH = 0.0, -0.06
# (frame relativo, nome, controles extras ou None para só fotografar)
STEPS = [
    (40, 'idle', None),
    (41, None, dict(fire=True)),
    (43, 'fire1', None),
    (44, 'fire2', None),
    (47, 'fire3', None),
    (60, None, dict()),
    (70, None, dict(reload=True)),
    (95, 'reload', dict()),
    (110, 'reload2', None),
    (130, None, dict(secondary=True)),
    (133, 'melee1', dict()),
    (136, 'melee2', None),
    (139, 'melee3', None),
    (142, 'melee4', None),
    (160, None, dict(z=1.0, sprint=True)),
    (186, 'sprint', dict(z=1.0, sprint=True)),
    (190, None, dict()),
]
CYCLE = 200


class Probe(Component):
    def __init__(self, heroes, third):
        self.frame = 0
        self.heroes = heroes
        self.third = third
        self.override = {}

    def setup(self, game, arena, hero):
        roster = game.session.roster.value
        team = HEROES[hero].team
        if self.third:
            # Câmera num jogador do outro time; o herói testado é um bot à frente, atirando de lado.
            slot = next(s for s, p in sorted(roster.items()) if p['team'] != team)
            target = next(s for s, p in sorted(roster.items()) if p['team'] == team)
        else:
            slot, target = next(s for s, p in sorted(roster.items()) if p['team'] == team), None
        for s, p in roster.items():
            p['owner'] = 0 if s != slot else game.session.manager.id
            p['bot'] = s != slot
        if target is None:
            roster[slot]['hero'] = hero
        actor = arena.actors[slot]
        actor.spawn(Vec3(*SPOT))
        actor.weapon.ammo = HEROES[actor.hero].magazine
        if target is not None:
            roster[target]['hero'] = hero
            other = arena.actors[target]
            other.spawn(Vec3(SPOT[0] - .3, SPOT[1], SPOT[2] - 2.6))
            other.weapon.ammo = HEROES[hero].magazine
        self.target = target
        return slot, target

    def bot_command(self, actor):
        if self.third and actor.slot == getattr(self, 'target', None):
            yaw = 1.25
            local = (self.frame - 30) % CYCLE
            fire = 41 <= local < 60 and (actor.hero != 'b_cell' or local % 2 == 1)
            return dict(yaw=yaw, pitch=0.0, fire=fire)
        return dict(yaw=actor.yaw)

    def loop(self):
        self.frame += 1
        game = self.game
        arena = getattr(game.session, 'arena', None) if getattr(game, 'session', None) else None
        if arena is None or not hasattr(game, 'inputs'):
            return
        index, local = divmod(self.frame - 30, CYCLE)
        if self.frame < 30:
            return
        if index >= len(self.heroes):
            game.running = False
            return
        hero = self.heroes[index]
        if local == 0:
            self.slot, _ = self.setup(game, arena, hero)
            game.inputs.yaw, game.inputs.pitch = YAW, PITCH
        actor = arena.actors[self.slot]
        actor.weapon.timer = min(actor.weapon.timer, .02) if hero == 'b_cell' else actor.weapon.timer
        game.inputs.yaw, game.inputs.pitch = YAW, PITCH
        for frame, name, controls in STEPS:
            if local == frame:
                if controls is not None and not self.third:
                    self.override = controls
                if name:
                    tag = '3p_' if self.third else ''
                    rl.take_screenshot(f'.scratch/weapons-game/{tag}{hero}_{name}.png')
                    print('shot', hero, name, 'fps', rl.get_fps(), 'ms', round(rl.get_frame_time() * 1000, 1), flush=True)
        if hero == 'b_cell' and 41 <= local < 60:
            self.override = dict(fire=local % 2 == 1)
        if 'secondary' in self.override and local > 131:
            self.override = {}
        if 'reload' in self.override and local > 71:
            self.override = {}


def main():
    argv = sys.argv[1:]
    heroes = list(HEROES)
    if '--only' in argv:
        heroes = argv[argv.index('--only') + 1].split(',')
    third = '--third' in argv
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
    game = Game('menu', 'Weapon views', screen_resolution=(1280, 720), target_fps=60)
    connect(game, '127.0.0.1', 0, True, 'Worker 1146')
    game.session.start(True)
    game.new_game('lobby', supress=True)
    probe = Probe(heroes, third)
    item = game.CreateItem()
    item.destroy_on_load = False
    item.AddComponent(probe)
    import UserComponents.cells.player as player_module
    import UserComponents.cells.bots as bots_module
    original = player_module.PlayerInput.init
    original_loop = player_module.PlayerInput.loop

    def init(self):
        original(self)
        game.inputs = self

    def loop(self):
        original_loop(self)
        slot = game.session.local_slot
        actor = self.arena.actors.get(slot)
        if actor is not None and actor.alive:
            actor.controls.update(probe.override)
            actor.controls['yaw'], actor.controls['pitch'] = self.yaw, self.pitch

    player_module.PlayerInput.init = init
    player_module.PlayerInput.loop = loop
    bots_module.BotBrain.command = lambda self, actor: probe.bot_command(actor)
    try:
        game.run()
    finally:
        game.close()


if __name__ == '__main__':
    main()
