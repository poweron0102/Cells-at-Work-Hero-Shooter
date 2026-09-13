"""Render every hero and the district in a hidden GPU window for visual review."""
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyray as rl
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.models import CharacterModel
from UserComponents.cells.scenery import DistrictScenery
from UserComponents.cells.catalog import HEROES


def main():
    os.chdir(ROOT)
    output = Path('.scratch/art-upgrade')
    output.mkdir(parents=True, exist_ok=True)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN | rl.ConfigFlags.FLAG_MSAA_4X_HINT)
    rl.init_window(1600, 900, 'Art verification')
    scene = DistrictScenery()
    try:
        for name, heroes in (('immune-models', list(HEROES)[:4]), ('bacterial-models', list(HEROES)[4:])):
            camera = rl.Camera3D(rl.Vector3(0, 2.8, 9), rl.Vector3(0, 1, 0), rl.Vector3(0, 1, 0), 4.3,
                                 rl.CameraProjection.CAMERA_ORTHOGRAPHIC)
            models = [CharacterModel(h) for h in heroes]
            for _ in range(2):
                rl.begin_drawing()
                rl.clear_background(rl.Color(225, 232, 219, 255))
                rl.begin_mode_3d(camera)
                for i, model in enumerate(models):
                    x = (i-1.5)*1.8
                    rl.draw_cylinder(rl.Vector3(x, -.06, 0), .72, .72, .1, 48, rl.Color(194, 209, 191, 255))
                    model.draw(Vec3(x, 0, 0), math.pi, .4, True)
                rl.end_mode_3d()
                rl.draw_text('ABRASION / CHARACTER WORKSHOP', 65, 50, 30, rl.Color(30, 62, 55, 255))
                for i, hero in enumerate(heroes):
                    pos = rl.get_world_to_screen(rl.Vector3((i-1.5)*1.8, -.4, 0), camera)
                    label = HEROES[hero].name
                    rl.draw_text(label, int(pos.x)-rl.measure_text(label, 20)//2, int(pos.y), 20, rl.Color(30, 62, 55, 255))
                rl.end_drawing()
            rl.take_screenshot(str(output / f'{name}.png'))
            assert (output / f'{name}.png').exists(), name
        shots = [('district-overview', (90, 106, 112), (0, 0, 0), 55),
                 ('street', (-25, 2.6, 45), (-10, 3, 0), 70),
                 ('high-ground', (18, 8, 30), (32, 6, 20), 70)]
        for name, position, target, fov in shots:
            camera = rl.Camera3D(rl.Vector3(*position), rl.Vector3(*target), rl.Vector3(0, 1, 0), fov,
                                 rl.CameraProjection.CAMERA_PERSPECTIVE)
            for _ in range(2):
                rl.begin_drawing()
                rl.clear_background(rl.Color(199, 220, 214, 255))
                rl.begin_mode_3d(camera)
                scene.render()
                rl.end_mode_3d()
                rl.draw_rectangle(35, 30, 630, 70, rl.Color(27, 53, 48, 230))
                rl.draw_text('ABRASION / EPITHELIAL DISTRICT', 55, 45, 26, rl.RAYWHITE)
                rl.draw_text('96 x 120m  /  Streets, galleries and receptor towers', 55, 78, 16, rl.RAYWHITE)
                rl.end_drawing()
            rl.take_screenshot(str(output / f'{name}.png'))
            assert (output / f'{name}.png').exists(), name
        print('PASS: eight hero models and three district views rendered', flush=True)
    finally:
        from UserComponents.cells.model_lighting import release
        release()
        scene.on_destroy()
        rl.close_window()


if __name__ == '__main__':
    main()
