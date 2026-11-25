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

MAP_VIEWS = {}
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


MAP_VIEWS['bairro'] = VIEWS
MAP_VIEWS['timo'] = {
    'dormitorio': ((0, 1.7, 58), (3, 3, 30), 70),
    'campo': ((-24, 5, 44), (6, 1, 20), 70),
    'labirinto': ((40, 7.5, 0), (0, 0, -6), 70),
    'labirinto_dentro': ((3, 1.7, 13), (3, 1.5, 0), 75),
    'trilha': ((-36, 1.7, 50), (-36, 2, 10), 70),
    'patio': ((14, 4, -30), (-20, 3, -50), 70),
    'cratera': ((0, 6, -48), (0, -1, -74), 70),
    'aerea': ((80, 80, 100), (0, 0, -4), 55),
    'base_inimiga': ((0, 1.2, -74), (0, 2, -30), 75),
}

MAP_VIEWS['medula'] = {
    'alojamento': ((0, 1.7, 58), (0, 3, 30), 70),
    'gramado': ((24, 6, 56), (-14, 4, 40), 70),
    'cidade': ((-4.5, 1.7, 33), (-4.5, 1.5, 0), 75),
    'cidade_alto': ((-30, 14, 40), (2, 0, 0), 65),
    'arcada': ((32, 1.7, 30), (36, 2, -10), 70),
    'canal': ((-30, 3, -10), (-45, 0, -26), 70),
    'praca_norte': ((30, 4, -30), (-17, 2, -52), 70),
    'fratura': ((16, 6, -48), (16, -1, -74), 70),
    'aerea': ((80, 80, 100), (0, 0, -4), 55),
}

MAP_VIEWS['coracao'] = {
    'veia_cava': ((0, 1.7, 56), (0, 4, 20), 70),
    'templo': ((-16, 4, 44), (0, 6, 14), 70),
    'salao_templo': ((0, 1.7, 20), (0, 2.5, 8), 75),
    'valva_tricuspide': ((0, 2.2, 8), (0, 3, -6), 70),
    'tunel_torii': ((0, 1.7, -5), (0, 1.8, -30), 70),
    'ventriculo': ((14, 5.6, -34), (-6, 3, -48), 75),
    'arteria': ((0, 1.7, -50), (0, 2.5, -66), 70),
    'pulmao': ((-16, 3, -70), (8, 3, -84), 70),
    'aerea': ((80, 80, 100), (0, 0, -6), 55),
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
    args = sys.argv[1:]
    key = 'bairro'
    if '--map' in args:
        i = args.index('--map')
        key = args[i+1]
        del args[i:i+2]
    from UserComponents.cells import layout
    layout.select(key)
    prefix = '' if key == 'bairro' else key+'_'
    from UserComponents.cells.scenery import draw_district, release, configure_depth, prepare
    out = ROOT/'.scratch/district'
    out.mkdir(parents=True, exist_ok=True)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN | rl.ConfigFlags.FLAG_MSAA_4X_HINT)
    rl.init_window(1280, 720, 'District views')
    configure_depth()
    prepare()
    views = dict(MAP_VIEWS.get(key, {}))
    if key == 'bairro':
        views.update(load_captures())
    background = layout.EXTRA.get('background', (244, 233, 213))
    try:
        names = args or list(views)
        for name in names:
            pos, target, fov = views[name]
            cam = rl.Camera3D(rl.Vector3(*pos), rl.Vector3(*target), rl.Vector3(0, 1, 0), fov, rl.CameraProjection.CAMERA_PERSPECTIVE)
            for _ in range(2):
                rl.begin_drawing()
                rl.clear_background(rl.Color(*background, 255))
                rl.begin_mode_3d(cam)
                draw_district(cam.position, 3.0)
                rl.end_mode_3d()
                rl.end_drawing()
            rl.take_screenshot(str((out/f'{prefix}{name}.png').relative_to(ROOT)).replace('\\', '/'))
            print('view', name, flush=True)
    finally:
        release()
        rl.close_window()


if __name__ == '__main__':
    main()
