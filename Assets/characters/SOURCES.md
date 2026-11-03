# Referências e modelos

Acervo das páginas oficiais de personagens, arquivado em 13/09/2026:

- [Primeira temporada](https://cellsatwork-anime.com/1st/character/)
- [Segunda temporada](https://cellsatwork-anime.com/character/)

Os arquivos originais ficam em `official/`. `manifest.json` registra as páginas
consultadas, a URL original, o tamanho e o SHA256 de cada imagem. O campo
`portraits` identifica exatamente a origem de cada um dos dez retratos usados
pelo jogo. As imagens são preservadas sem alterações; o jogo só ajusta sua
filtragem durante a renderização.

© Akane Shimizu / KODANSHA, Aniplex, davidproduction.
Imagens de terceiros utilizadas como retratos e referências neste protótipo de fã.
Reproduzir o acervo: `python scripts/fetch_references.py` (requer internet).

## Modelos 3D (Blender)

Os dez personagens 3D (`neutrophil`, `macrophage`, `b_cell`, `killer_t`, `pneumococcus`,
`staphylococcus`, `pseudomonas`, `streptococcus`, `red_blood_cell`, `platelet`) são modelados do
zero no Blender por `scripts/build_characters.py`, usando apenas as imagens desta pasta e de
`referencias/` como referência visual. Não há malhas importadas nem código copiado de outro projeto.

- Geometria: primitivas procedurais (lathe, tubos varridos, elipsoides, placas extrudadas) e
  modificadores do Blender (Bevel/Subdivision) aplicados antes da exportação.
- Cores: atributo de cor por canto (byte color, sRGB). O exportador glTF grava `COLOR_0`
  linear (normalizado, u16), e o shader toon (`UserComponents/cells/model_lighting.py`) volta
  para sRGB. Um único material simples; cada parte = um draw call.
- Saída: `Assets/Characters3D/<chave>.glb` + `<chave>.json`. O JSON lista as partes
  (`body`, `arm_l`, `arm_r`, `leg_l`, `leg_r`, `weapon`, `tail`, `tentacles_*`, `head`, `braid`,
  `leg_l1`...), o índice da malha em `model.meshes` do raylib (calculado lendo o GLB como o
  `LoadGLTF` do raylib faz), o pivô da articulação, a família de animação (`swing`), a defasagem
  (`phase`), a amplitude (`amp`) e a reação ao ataque (`action`). O campo `convention` descreve
  os eixos: Y para cima, frente +Z, pés em y=0, `_l` = +X (esquerda do personagem).
- Jogo: `UserComponents/cells/models.py` carrega o GLB sob demanda (cache por chave) e anima as
  partes proceduralmente (caminhada, respiração, cauda/tentáculos, golpe).

Regenerar (Blender 5.2, sem interface), a partir da raiz do repositório:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup `
    --python scripts\build_characters.py -- [--only neutrophil,b_cell] [--no-preview]
```

Prévias do Blender (Workbench) vão para `.scratch/characters/`; a conferência no jogo é
`python scripts/check_art.py` (PNGs em `.scratch/art-upgrade/`) e os testes sem GPU ficam em
`tests/test_character_assets.py`.

Outros arquivos procedurais:

- `art.py`: MeshBuilder e primitivas adaptados do renderizador de Cellular-Odyssey-2 (não é mais
  usado pelos personagens).
- `scenery.py`: composição de fachadas, cornijas, janelas, tubulações e pavimentação inspirada no
  renderizador distrital original.

Arquivos de origem do material adaptado: `UserComponents/cellular/visuals.py`, no projeto
autorizado pelo usuário: `C:/Users/Tecnologia/PycharmProjects/Cellular-Odyssey-2`.
Revisão de origem: `c27ff3a180f169e9d609bae805dc4c51dc6fee53`.
Nenhum arquivo do projeto de origem foi alterado. O jogo não depende desse caminho.
