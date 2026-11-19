"""Monta e exporta o Bairro Arterial em um unico processo do Blender (sem janela).

    & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python referencias\scripts\mapa\rebuild_distrito.py
Depois rode referencias\scripts\mapa\build_navmesh.py para atualizar a navegacao dos bots.
"""
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
for name in ('build_distrito.py', 'export_distrito.py'):
    with open(os.path.join(REPO, 'referencias', 'scripts', 'mapa', name), encoding='utf-8') as source:
        exec(source.read(), {'REPO': REPO, '__name__': 'rebuild'})
