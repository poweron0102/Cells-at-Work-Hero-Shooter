"""Render all HUD portraits and live states in a hidden GPU window.

Run from the repository with .venv/Scripts/python.exe scripts/check_hud.py.
Captures are written to .scratch/hud; no multiplayer peers are needed.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyray as rl
from EasyCells3D import Game
from EasyCells3D.Components import Component
from UserComponents.cells.catalog import HEROES
from UserComponents.cells.hud import CombatHUD, INK, WHITE
from UserComponents.cells.hud_portraits import FACES, ROOT as FACE_ROOT, draw_face
from UserComponents.cells.network import connect


class HUDProbe(Component):
    def __init__(self):
        self.frame = 0

    def loop(self):
        self.frame += 1
        if self.frame == 2:
            connect(self.game, '127.0.0.1', 0, True, 'HUD probe')
            self.game.session.start(True)
            self.game.new_game('abrasion')
        if self.frame < 10:
            return
        hud = next(r for camera in self.game.cameras for r in getattr(camera, 'renderables', [])
                   if isinstance(r, CombatHUD))
        arena = hud.arena
        arena.authority = False  # Freeze the simulation while exercising display snapshots.
        actor = arena.actors[self.game.session.local_slot]
        state = arena.state
        index, step = divmod(self.frame-10, 8)
        if index >= len(HEROES):
            # Draw the actual runtime source crops, including every state mapping.
            rl.begin_drawing()
            rl.clear_background(rl.Color(*INK, 255))
            hud.layout()
            for row, hero in enumerate(HEROES):
                hud.text(hero, 24, row*86+24, 16, WHITE)
                for col, expression in enumerate(('normal', 'low', 'hurt', 'special', 'success')):
                    x, y = 220+col*200, row*86+4
                    draw_face(hud, hero, expression, x, y, 64)
                    hud.text(expression, x+72, y+24, 12, WHITE)
            rl.rl_draw_render_batch_active()
            rl.take_screenshot('.scratch/hud/expressions.png')
            rl.end_drawing()
            self.game.running = False
            return
        hero = list(HEROES)[index]
        kit = HEROES[hero]
        if step == 0:
            actor.hero, actor.team, actor.health = hero, kit.team, kit.health
            actor.alive, actor.shield, actor.neutralized = True, 0, 0
            actor.ability_cd = actor.special_cd = 0
            actor.weapon.ammo, actor.weapon.reload_time = kit.magazine, 0
            state.immune_cooldown = state.notice_time = 0
            state.phase, state.elapsed, state.stress = 1, 100, 46
            state.capture, state.recognition, state.maturity = [100, 100, 0], 55, 24
            state.event = ''
        elif step == 2:
            rl.take_screenshot(f'.scratch/hud/{hero}-ready.png')
            actor.health, actor.hurt = kit.health*.2, .25
            actor.weapon.ammo, actor.weapon.reload_time = 0, 1.4
            actor.ability_cd = 6.2
            actor.special_cd = state.immune_cooldown = 24
            state.stress = 92
            state.maturity = 45
        elif step == 4:
            assert hud.face_state == 'hurt', hero
            rl.take_screenshot(f'.scratch/hud/{hero}-hurt.png')
            state.elapsed += 2
            actor.hurt = 0
        elif step == 6:
            rl.take_screenshot(f'.scratch/hud/{hero}-critical.png')
            actor.health = kit.health
            actor.ability_cd = 9
        elif step == 7:
            assert hud.face_state == 'special', hero


def main():
    os.chdir(ROOT)
    (ROOT/'.scratch/hud').mkdir(parents=True, exist_ok=True)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
    game = Game('menu', 'HUD verification', screen_resolution=(1280, 720), target_fps=60)
    try:
        assert set(FACES) == set(HEROES)
        for folder, regions, states in FACES.values():
            source = rl.load_image(str(FACE_ROOT/folder/'up.png'))
            try:
                assert source.width > 0
                for x, y, w, h in regions:
                    assert 0 <= x < x+w <= source.width and 0 <= y < y+h <= source.height
                assert all(0 <= i < len(regions) for i in states.values())
            finally:
                rl.unload_image(source)
        item = game.CreateItem()
        item.destroy_on_load = False
        item.AddComponent(HUDProbe())
        game.run()
    finally:
        game.close()
    print('PASS: eight official face sheets, crop bounds, damage/special transitions, HUD state captures')


if __name__ == '__main__':
    main()
