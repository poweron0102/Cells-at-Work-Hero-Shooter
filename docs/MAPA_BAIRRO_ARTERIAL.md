# Bairro Arterial — pipeline do mapa

Mapa construído do zero no Blender (5.2) a partir de `referencias/` e de
`docs/PLANO_MAPA.md`. Toda a geometria é gerada por script, então qualquer ajuste
de layout é reprodutível.

## Arquivos

| Arquivo | Função |
| --- | --- |
| `scripts/distrito_geo.py` | Primitivas e arquitetura (caixas, arcos, escadas com rampa de colisão, guarda-corpos, fachadas com sacadas, árvores, postes, barreiras). |
| `scripts/distrito_layout.py` | Layout por zonas, marcadores (spawns, escolta, rotas das hemácias, destinos A/B/C, posto de reconhecimento, sugestões de colônia). |
| `scripts/build_distrito.py` | Monta a cena no Blender: coleções **Arte**, **Colisao** e **Marcadores**. |
| `scripts/export_distrito.py` | Salva o `.blend`, exporta o GLB e escreve `runtime.json`. |
| `scripts/build_navmesh.py` | Gera `nav.json` (grade em camadas para os bots) a partir da colisão. |
| `scripts/rebuild_distrito.py` | Monta e exporta em um único processo do Blender sem janela. |
| `scripts/check_map_overlaps.py` | Detecta faces coplanares sobrepostas (z-fight); também roda em `tests/test_map_geometry.py`. |
| `scripts/render_district.py` | Vistas do mapa pelo motor do jogo, incluindo cada captura de `capturas/` (`cap00`, `cap01`...). |
| `Assets/Maps/BairroArterial/` | `BairroArterial.blend`, `.glb`, `runtime.json`, `nav.json`. |

## Coordenadas

O layout é escrito nas coordenadas do jogo: **x leste, y cima, z sul**. No Blender
isso vira `(x, -z, y)` (norte = +Y). A base das células fica ao sul (+z) e a
ferida ao norte (−z).

## Regenerar

No Blender aberto (console Python ou MCP):

```python
REPO = r'C:\caminho\do\repo'
exec(open(REPO + r'\scripts\build_distrito.py', encoding='utf-8').read(), {'REPO': REPO})
exec(open(REPO + r'\scripts\export_distrito.py', encoding='utf-8').read(), {'REPO': REPO})
```

Em segundo plano:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python scripts\build_distrito.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background Assets\Maps\BairroArterial\BairroArterial.blend --python scripts\export_distrito.py
.venv\Scripts\python.exe scripts\build_navmesh.py
```

`nav.json` guarda o hash de `runtime.json`; se ficar desatualizado, o jogo
reconstrói a navegação na primeira partida (cerca de 1 s).

Ajustes feitos à mão no `.blend` também são exportados: a arte vem da coleção
**Arte**, a colisão da coleção **Colisao** e os marcadores das *empties* em
**Marcadores**. Rotas e destinos ficam no texto `marcadores.json` do arquivo.

## Cores e padrões

Cada face guarda uma cor por vértice (sRGB) e, em `UV.x`, o id de um padrão
desenhado pelo shader de `UserComponents/cells/scenery.py`:

| id | padrão | id | padrão |
| --- | --- | --- | --- |
| 0 | liso | 9 | metal |
| 1 | tijolo | 10 | terra/obra |
| 2 | pedras irregulares | 11 | telhado |
| 3 | ladrilho pastel | 12 | rede de coágulo |
| 4 | tábuas de madeira | 13 | luz (sem sombreamento) |
| 5 | água animada | 14 | listras de alerta |
| 6 | cantaria do canal | 15 | folhagem |
| 7 | reboco | 16 | tecido da ferida |
| 8 | janela | 17 | vidro |

A exportação junta as faces por zona em blocos de até 60 mil vértices (limite de
índices de 16 bits do raylib), mantendo poucos *draw calls*.

## Regras que a geometria precisa manter

- Pisos decorativos usam `g.overlay(...)` com prioridade: a exportação recorta os
  de menor prioridade, então dois acabamentos nunca ficam no mesmo plano.
- Nada fica coplanar com cor/padrão diferente (`check_map_overlaps.py` deve dar 0).
- Uma fileira contínua de prédios (`perimeter`) fecha os quatro lados fora da área
  jogável; ruas, pátios e margens sempre terminam em fachada, nunca no vazio. O
  canal segue para um túnel de tijolos escuro além das grades.
- Os prédios do horizonte não se sobrepõem e são rebaixados para não cruzar os
  vasos gigantes do céu.
- O jogo usa plano de recorte próximo de 8 cm (`scenery.configure_depth`).

Os testes de `tests/test_traversal.py` verificam: spawns sobre chão seguro;
marcadores sobre superfícies caminháveis; rampas que tiram o herói mais lento do
canal; as três pontes atravessáveis; passagem sob a ponte central; escadas das
passarelas; navegação das duas bases a todos os objetivos e sugestões de colônia;
e ausência de linha de visão direta entre as bases.

O controlador de personagem não sobe degraus: toda escada visível tem uma rampa de
colisão invisível com no máximo ~27°.
