"""Monta e exporta o Bairro Arterial em um unico processo do Blender (sem janela).

    & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python scripts\rebuild_distrito.py
Depois rode scripts\build_navmesh.py para atualizar a navegacao dos bots.
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for name in ('build_distrito.py', 'export_distrito.py'):
    with open(os.path.join(REPO, 'scripts', name), encoding='utf-8') as source:
        exec(source.read(), {'REPO': REPO, '__name__': 'rebuild'})
