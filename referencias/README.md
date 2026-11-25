# Referências e pipeline de assets

`Assets/` contém **apenas arquivos que o jogo carrega**. Tudo que serve para criar,
buscar ou editar esses arquivos fica aqui em `referencias/`.

## O que o jogo carrega (`Assets/`)

| Pasta | Conteúdo | Gerado por |
| --- | --- | --- |
| `Maps/BairroArterial/` | `BairroArterial.glb`, colisão e marcadores em `runtime.json`, navegação em `nav.json`. | `scripts/mapa/` ([detalhes](../docs/MAPA_BAIRRO_ARTERIAL.md)) |
| `Maps/Timo/`, `Maps/MedulaOssea/`, `Maps/Coracao/` | Os mapas novos, no mesmo formato (o `runtime.json` traz também o modo, as valvas e a colisão vazada dos alambrados). | `scripts/mapa/` ([detalhes](../docs/MAPAS_NOVOS.md)) |
| `Characters3D/` | Modelos `.glb` dos heróis e NPCs + metadados `.json`. | `scripts/personagens/build_characters.py`, `export_macrophage.py` e `tripo_characters.py` |
| `Weapons/` | Modelos `.glb` das armas + metadados `.json`. | `scripts/personagens/build_weapons.py` |
| `characters/` | Retratos 2D (`<herói>.png`) dos menus. | `scripts/personagens/fetch_references.py` |
| `characters/faces/` | Folhas de expressão (`<herói>.png`) recortadas pela HUD (`hud_portraits.py`). | `scripts/personagens/fetch_references.py` |
| `audio/` | Efeitos sonoros procedurais (`.wav`). | `scripts/audio/build_audio.py` |
| `audio/voice/` | Falas recortadas do anime, `ja/` e `en/` (`.ogg`). | `scripts/audio/build_voices.py` |
| `fonts/` | Fontes `.ttf` (com a licença OFL de cada família, exigida para redistribuir). | — |

## O que fica aqui (`referencias/`)

| Pasta | Conteúdo |
| --- | --- |
| `imagens/` | Capturas do anime e key visual usados como referência visual do mapa e da arte. |
| `Timo/`, `MedulaOssea/`, `Coracao/` | Quadros do anime usados em cada mapa novo, com um README dizendo o que cada um inspirou. |
| `personagens_oficiais/` | Acervo das páginas oficiais de personagens (`1st/`, `assets/`), `manifest.json` e [SOURCES.md](personagens_oficiais/SOURCES.md). |
| `audio/` | `voice_clips.json` (episódio, tempos e textos de cada fala) e [SOURCES.md](audio/SOURCES.md). |
| `blender/` | Fontes editáveis: `BairroArterial.blend`, `Timo.blend`, `MedulaOssea.blend` e `Coracao.blend` (mapas), `macrophage.blend` e as cenas geradas de `b_cell`, `red_blood_cell` e `platelet` (esqueleto e ações). |
| `Tripo 3D assets/` | Modelos do Tripo com esqueleto Mixamo (hemácia, plaqueta, Célula B, Macrófaga e a escopeta). |
| `animacoes/mesh2motion/` | Clipes CC0 do Mesh2Motion usados nos modelos do Tripo ([SOURCES.md](animacoes/mesh2motion/SOURCES.md)). |
| `scripts/mapa/` | Montagem dos mapas no Blender (`build_distrito`, a biblioteca `distrito_geo` e um layout por mapa: `distrito_layout`, `timo_layout`, `medula_layout`, `coracao_layout`), exportação (`export_distrito`, `rebuild_distrito`) e navegação (`build_navmesh`). Todos aceitam `--map`. |
| `scripts/personagens/` | Modelagem dos personagens e armas no Blender e download do acervo oficial. |
| `scripts/audio/` | Síntese dos efeitos sonoros e recorte das falas. |

Ferramentas de verificação e captura (`check_*`, `render_district`, `map_check`, `plot_map`, `build_player_guide`)
continuam em `scripts/` na raiz, pois validam o jogo em vez de gerar assets.

## Comandos (da raiz do repositório)

```powershell
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
# Mapa (Bairro Arterial)
& $blender --background referencias\blender\BairroArterial.blend --python referencias\scripts\mapa\export_distrito.py
.venv\Scripts\python.exe referencias\scripts\mapa\build_navmesh.py
# Mapas novos (timo, medula, coracao): monta + exporta, depois a navegacao
& $blender --background --factory-startup --python referencias\scripts\mapa\rebuild_distrito.py -- --map coracao
.venv\Scripts\python.exe referencias\scripts\mapa\build_navmesh.py --map coracao
# Personagens e armas
& $blender --background --factory-startup --python referencias\scripts\personagens\build_characters.py
& $blender --background --factory-startup --python referencias\scripts\personagens\tripo_characters.py
& $blender --background --factory-startup --python referencias\scripts\personagens\build_weapons.py
# Retratos e faces (requer internet)
.venv\Scripts\python.exe referencias\scripts\personagens\fetch_references.py
# Áudio
.venv\Scripts\python.exe referencias\scripts\audio\build_audio.py
```

Backups do Blender (`.blend1`, `.blend2`...), logs e capturas de validação são
locais e ignorados pelo Git; salve capturas em `.scratch/` ou `capturas/`.
Mantenha arquivos abaixo de 100 MiB (sem Git LFS). O Bairro dos Canais foi
retirado; não adicione de novo seus atlas, renders ou exports.
