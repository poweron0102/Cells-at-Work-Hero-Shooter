"""Render every hero, the NPCs and an action-pose row in a hidden GPU window for visual review.

Saídas em .scratch/art-upgrade/: immune-models.png, bacterial-models.png, npc-models.png,
action-models.png, walk-models.png e (se o mapa carregar) as vistas do distrito.
"""
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyray as rl
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.models import CharacterModel, release_models
from UserComponents.cells.catalog import HEROES

INK = rl.Color(30, 62, 55, 255)


def lineup(output, name, title, keys, views, labels=None, **draw_kw):
    """Desenha os personagens lado a lado (câmera ortográfica) e salva um PNG."""
    n = len(keys)
    spacing = 1.75
    camera = rl.Camera3D(rl.Vector3(0, 2.0, 12), rl.Vector3(0, 1.0, 0), rl.Vector3(0, 1, 0), 2.75,
                         rl.CameraProjection.CAMERA_ORTHOGRAPHIC)
    # Mantém todos no quadro: a altura visível cresce com o número de colunas.
    camera.fovy = max(2.75, n * spacing * 900 / 1600 + 0.2)
    models = [CharacterModel(k) for k in keys]
    for _ in range(2):
        rl.begin_drawing()
        rl.clear_background(rl.Color(225, 232, 219, 255))
        rl.begin_mode_3d(camera)
        for i, model in enumerate(models):
            x = (i - (n - 1) / 2) * spacing
            rl.draw_cylinder(rl.Vector3(x, -.06, 0), .62, .62, .1, 40, rl.Color(194, 209, 191, 255))
            kw = dict(draw_kw)
            if callable(kw.get('action')):
                kw['action'] = kw['action'](i)
            model.draw(Vec3(x, 0, 0), views[i % len(views)], kw.pop('phase', .4), kw.pop('moving', True), **kw)
        rl.end_mode_3d()
        rl.draw_text(title, 50, 36, 28, INK)
        for i, key in enumerate(keys):
            pos = rl.get_world_to_screen(rl.Vector3((i - (n - 1) / 2) * spacing, -.25, 0), camera)
            label = (labels or {}).get(key, key)
            rl.draw_text(label, int(pos.x) - rl.measure_text(label, 18) // 2, int(pos.y), 18, INK)
        rl.end_drawing()
    path = output / f'{name}.png'
    rl.take_screenshot(str(path))
    assert path.exists(), name


def main():
    os.chdir(ROOT)
    output = Path('.scratch/art-upgrade')
    output.mkdir(parents=True, exist_ok=True)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN | rl.ConfigFlags.FLAG_MSAA_4X_HINT)
    rl.init_window(1600, 900, 'Art verification')
    heroes = list(HEROES)
    labels = {k: h.name for k, h in HEROES.items()}
    labels.update(red_blood_cell='RED BLOOD CELL', platelet='PLATELET')
    scene = None
    try:
        # O modelo olha para o "forward" de gameplay (sin(yaw), 0, -cos(yaw)); yaw = pi -> câmera.
        lineup(output, 'immune-models', 'CHARACTER WORKSHOP / IMMUNE', heroes[:4], [math.pi], labels)
        lineup(output, 'bacterial-models', 'CHARACTER WORKSHOP / BACTERIA', heroes[4:], [math.pi], labels)
        lineup(output, 'npc-models', 'CHARACTER WORKSHOP / NPC', ['red_blood_cell', 'platelet', 'red_blood_cell',
                                                                  'platelet'],
               [math.pi, math.pi, math.pi - .8, math.pi + .8], labels, action=lambda i: [0, 0, 0, .8][i])
        # Golpe a meio caminho, de perfil (yaw = pi/2 -> olhando para +X / direita da tela).
        lineup(output, 'action-models', 'ACTION POSE (action=.45, facing right)', heroes, [math.pi / 2], labels,
               action=.45, moving=False)
        lineup(output, 'walk-models', 'WALK CYCLE (phase=1.3, 3/4 view)', heroes + ['red_blood_cell', 'platelet'],
               [math.pi - .7], labels, phase=1.3)
        print('PASS: eight hero models, two NPC models, action and walk poses rendered', flush=True)
        try:
            from UserComponents.cells.scenery import DistrictScenery
            scene = DistrictScenery()
        except Exception as exc:  # o mapa está sendo reconstruído em paralelo
            print(f'WARNING: district scenery skipped ({type(exc).__name__}: {exc})', flush=True)
            return
        shots = [('district-overview', (90, 106, 112), (0, 0, 0), 55),
                 ('street', (0, 2.6, 36), (0, 3, 18), 70),
                 ('high-ground', (-20, 4.6, -30), (-12, 2, -15), 70)]
        try:
            for name, position, target, fov in shots:
                camera = rl.Camera3D(rl.Vector3(*position), rl.Vector3(*target), rl.Vector3(0, 1, 0), fov,
                                     rl.CameraProjection.CAMERA_PERSPECTIVE)
                for _ in range(2):
                    rl.begin_drawing()
                    rl.clear_background(rl.Color(199, 220, 214, 255))
                    rl.begin_mode_3d(camera)
                    scene.render()
                    rl.end_mode_3d()
                    rl.end_drawing()
                rl.take_screenshot(str(output / f'{name}.png'))
            print('PASS: three district views rendered', flush=True)
        except Exception as exc:
            print(f'WARNING: district views failed ({type(exc).__name__}: {exc})', flush=True)
    finally:
        from UserComponents.cells.model_lighting import release
        release_models()
        release()
        if scene is not None:
            try:
                scene.on_destroy()
            except Exception:
                pass
        rl.close_window()


if __name__ == '__main__':
    main()
