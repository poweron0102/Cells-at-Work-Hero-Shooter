"""Monta e exporta um mapa em um unico processo do Blender (sem janela).

    & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python referencias\scripts\mapa\rebuild_distrito.py -- --map timo

Sem ``--map`` monta o Bairro Arterial. Depois rode
``.venv\Scripts\python.exe referencias\scripts\mapa\build_navmesh.py --map timo`` para a navegacao dos bots.
"""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
MAP = argv[argv.index('--map')+1] if '--map' in argv else 'bairro'
for name in ('build_distrito.py', 'export_distrito.py'):
    with open(os.path.join(REPO, 'referencias', 'scripts', 'mapa', name), encoding='utf-8') as source:
        exec(source.read(), {'REPO': REPO, 'MAP': MAP, '__name__': 'rebuild'})
