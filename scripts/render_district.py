"""Renderiza vistas do Bairro Arterial no motor do jogo (janela oculta).

    .venv\\Scripts\\python.exe scripts\\render_district.py [nome ...]
Salva PNGs em .scratch/district/.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyray as rl  # noqa: E402

VIEWS = {
    'avenida': ((0, 1.7, 70), (0, 5, 30), 70),
    'praca': ((-24, 5, 34), (0, 2, 12), 70),
    'canal': ((-30, -0.4, 0), (10, 0, 0), 70),
    'ponte_oeste': ((-30, 3, 18), (-40, 2, 0), 70),
    'obra': ((0, 6, -46), (0, -1, -78), 70),
    'tunel': ((48, 1.7, -62), (20, 2, -62), 70),
    'aerea': ((90, 80, 110), (0, 0, 0), 55),
    'base_inimiga': ((0, 1.2, -84), (0, 2, -40), 75),
    'rua_norte': ((-40, 1.7, -14), (20, 2, -24), 70),
}


def load_captures():
    """Freecam captures in capturas/ become extra views named cap00, cap01..."""
    import json
    views = {}
    for i, folder in enumerate(sorted((ROOT/'capturas').glob('*/'))):
        data = json.loads((folder/'camera.json').read_text(encoding='utf-8'))
        p, t = data.get('position'), data.get('target')
        if p and t:
            views[f'cap{i:02}'] = (tuple(p), tuple(t), data.get('vertical_fov_degrees', 60))
    return views


def main():
    os.chdir(ROOT)
    from UserComponents.cells.scenery import draw_district, release, configure_depth
    out = ROOT/'.scratch/district'
    out.mkdir(parents=True, exist_ok=True)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN | rl.ConfigFlags.FLAG_MSAA_4X_HINT)
    rl.init_window(1280, 720, 'District views')
    configure_depth()
    extra = load_captures()
    VIEWS.update(extra)
    try:
        names = sys.argv[1:] or list(VIEWS)
        for name in names:
            pos, target, fov = VIEWS[name]
            cam = rl.Camera3D(rl.Vector3(*pos), rl.Vector3(*target), rl.Vector3(0, 1, 0), fov, rl.CameraProjection.CAMERA_PERSPECTIVE)
            for _ in range(2):
                rl.begin_drawing()
                rl.clear_background(rl.Color(244, 233, 213, 255))
                rl.begin_mode_3d(cam)
                draw_district(cam.position, 3.0)
                rl.end_mode_3d()
                rl.end_drawing()
            rl.take_screenshot(str((out/f'{name}.png').relative_to(ROOT)).replace('\\', '/'))
            print('view', name, flush=True)
    finally:
        release()
        rl.close_window()


if __name__ == '__main__':
    main()
