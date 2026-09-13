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

Os modelos 3D são geometria procedural, independente das imagens na execução:

- `appearance.py`: presets copiados de Cellular-Odyssey-2 e ampliados.
- `art.py`: MeshBuilder e primitivas adaptados do renderizador do projeto de origem.
- `models.py`: articulações do neutrófilo, hemácia, plaqueta, célula comum e pneumococo reaproveitadas; novos modelos para Macrophage, B Cell, Killer T, Staphylococcus, Pseudomonas e Streptococcus baseados nas referências arquivadas.
- `scenery.py`: nova composição de fachadas, cornijas, janelas, tubulações e pavimentação inspirada no renderizador distrital original.

Arquivos de origem: `UserComponents/cellular/appearance.py` e
`UserComponents/cellular/visuals.py`, no projeto autorizado pelo usuário:
`C:/Users/Tecnologia/PycharmProjects/Cellular-Odyssey-2`.
Revisão de origem: `c27ff3a180f169e9d609bae805dc4c51dc6fee53`.
Nenhum arquivo do projeto de origem foi alterado. O jogo não depende desse caminho.
