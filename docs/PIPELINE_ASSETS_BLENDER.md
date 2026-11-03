# Pipeline de assets do Blender para o jogo

O mapa ativo é o **Bairro Arterial**. O Bairro dos Canais, seus atlas com bake
e suas ferramentas exclusivas foram removidos. A organização de mapas,
personagens, armas e áudio está em [Assets/README.md](../Assets/README.md).

## Fonte e exports

`Assets/Maps/BairroArterial/BairroArterial.blend` é a fonte editável.
O jogo carrega `BairroArterial.glb`, `runtime.json` e `nav.json` dessa pasta;
Blender não é necessário para jogar.

A cena separa as coleções `Arte`, `Colisao` e `Marcadores`. O exportador gera
geometria visual com cores por vértice, normais e o identificador do padrão
em UV.x. `UserComponents/cells/scenery.py` usa esses atributos para desenhar
tijolos, madeira, água e outros padrões. Não há atlas de iluminação nesse mapa.

`runtime.json` contém triângulos de colisão, marcadores, rotas e metadados.
As posições são convertidas de `(X, Y, Z)` do Blender para `(X, Z, -Y)` no jogo,
em metros. `nav.json` é gerado a partir da colisão exportada.

## Atualizar o mapa

Após editar a fonte, exporte e regenere a navegação na raiz do projeto:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background Assets\Maps\BairroArterial\BairroArterial.blend --python scripts\export_distrito.py
.venv\Scripts\python.exe scripts\build_navmesh.py
```

Para reconstruir a cena a partir dos scripts, use `scripts/rebuild_distrito.py`
no Blender. Esse comando recria a fonte; preserve edições manuais antes de usá-lo.
Veja [MAPA_BAIRRO_ARTERIAL.md](MAPA_BAIRRO_ARTERIAL.md) para o fluxo completo.

## Verificação e manutenção

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts\check_scenes.py
.venv\Scripts\python.exe scripts\render_district.py
```

Os testes verificam os atributos do GLB, o limite de vértices por lote do
Raylib, a geometria, as regras e a navegação. As vistas do mapa são gravadas
em `.scratch/district/`. Confira também os spawns, rampas, pontes e passagens
inferiores no jogo ao alterar arte ou colisão.

Mantenha fonte, export e metadados coerentes. Backups `.blend1`, `.blend2`, logs
e capturas ficam fora do versionamento. Não adicione novamente exports ou
atlas do mapa retirado.
