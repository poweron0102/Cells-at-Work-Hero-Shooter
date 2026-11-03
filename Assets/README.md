# Organização dos assets

| Pasta | Conteúdo | Geração / documentação |
| --- | --- | --- |
| `Maps/BairroArterial/` | Único mapa ativo: fonte `.blend`, modelo `.glb`, colisão e marcadores em `runtime.json`, navegação em `nav.json`. | [Mapa e exportação](../docs/MAPA_BAIRRO_ARTERIAL.md) |
| `Characters3D/` | Modelos `.glb` dos heróis e NPCs, com metadados `.json`. | `scripts/build_characters.py` |
| `Weapons/` | Modelos `.glb` e metadados `.json` das armas. | `scripts/build_weapons.py` |
| `characters/` | Retratos 2D e referências usadas para os personagens. | [Fontes e geração](characters/SOURCES.md) |
| `audio/` | Efeitos sonoros do jogo. | `scripts/build_audio.py` |

O jogo usa os exports e metadados diretamente; Blender só é necessário para
editar ou regenerar modelos. Mantenha cada export junto de seus metadados.
Os caminhos usados pelo jogo permanecem estáveis.

O Bairro dos Canais e suas ferramentas exclusivas foram retirados. Seus atlas,
renders e exports não devem ser adicionados novamente. O Bairro Arterial usa
cores por vértice com iluminação pré-calculada e padrões no shader, sem os
atlas do mapa anterior. O bake é refeito por `scripts/bake_distrito.py` no
Blender e também faz parte da exportação padrão.

Backups do Blender (`.blend1`, `.blend2`, etc.), logs e capturas de validação
são arquivos locais ignorados pelo Git. Salve capturas em `.scratch/` ou
`capturas/`. Mantenha arquivos individuais abaixo de 100 MiB; os assets atuais
cabem no Git normal, sem Git LFS.
