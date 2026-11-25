# Bairro Arterial — pipeline do mapa

> Os scripts deste pipeline servem a todos os mapas (`--map timo|medula|coracao`); os mapas
> novos estão descritos em [MAPAS_NOVOS.md](MAPAS_NOVOS.md).

Mapa construído do zero no Blender (5.2) a partir de `referencias/imagens/` e de
`docs/PLANO_MAPA.md`. Toda a geometria é gerada por script, então qualquer ajuste
de layout é reprodutível.

## Arquivos

| Arquivo | Função |
| --- | --- |
| `referencias/scripts/mapa/distrito_geo.py` | Primitivas e arquitetura (caixas, arcos, escadas com rampa de colisão, guarda-corpos, fachadas com sacadas, árvores, postes, barreiras). |
| `referencias/scripts/mapa/distrito_layout.py` | Layout por zonas, marcadores (spawns, escolta, rotas das hemácias, destinos A/B/C, posto de reconhecimento, sugestões de colônia). |
| `referencias/scripts/mapa/build_distrito.py` | Monta a cena no Blender: coleções **Arte**, **Colisao** e **Marcadores**. |
| `referencias/scripts/mapa/export_distrito.py` | Salva o `.blend`, exporta o GLB e escreve `runtime.json`. |
| `referencias/scripts/mapa/build_navmesh.py` | Gera `nav.json` (grade em camadas para os bots) a partir da colisão. |
| `referencias/scripts/mapa/rebuild_distrito.py` | Monta e exporta em um único processo do Blender sem janela. |
| `scripts/check_rbc_routes.py` | Confere se cada trecho das rotas das hemácias tem chão contínuo e corredor livre (também em `tests/test_traversal.py`). |
| `scripts/check_map_overlaps.py` | Detecta faces coplanares sobrepostas (z-fight); também roda em `tests/test_map_geometry.py`. |
| `scripts/render_district.py` | Vistas do mapa pelo motor do jogo, incluindo cada captura de `capturas/` (`cap00`, `cap01`...). |
| `referencias/blender/BairroArterial.blend` | Fonte editável do mapa. |
| `Assets/Maps/BairroArterial/` | `BairroArterial.glb`, `runtime.json`, `nav.json` (carregados pelo jogo). |

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
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python referencias\scripts\mapa\build_distrito.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background referencias\blender\BairroArterial.blend --python referencias\scripts\mapa\export_distrito.py
.venv\Scripts\python.exe referencias\scripts\mapa\build_navmesh.py
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
|  |  | 18 | alambrado (tela vazada) |

A exportação junta as faces por zona em blocos de até 60 mil vértices (limite de
índices de 16 bits do raylib), mantendo poucos *draw calls*.

## Iluminação

A luz não vem do Blender: `UserComponents/cells/lighting.py` "assa" tudo no jogo ao
carregar o mapa (≈0,5 s, só com GPU), a partir da própria geometria do GLB:

- **Sol** (`lighting.SUN`, do sudoeste, ~53° de altura): mapa de sombra de 4096 px
  sobre a área jogável e o começo do horizonte. A sombra projetada tem borda nítida
  (cel) e o mesmo tom lavanda das faces de costas para o sol.
- **Céu**: volume de visibilidade do céu (voxels de 0,5 m). Túneis, o vão sob pontes,
  passarelas e pilotis escurecem para um tom quente e profundo; ruas abertas não.
  Objetos com menos de ~1 m de largura (fios, corrimãos, postes) são ignorados aqui.
- **Postes**: as cabeças com padrão 13 viram luzes quentes, visíveis só onde falta céu.
- Água (5) e lanternas (13) não fazem sombra; redes (12) fazem sombra quadriculada.
- **Contorno de nanquim** (`scenery.py`): a cada quadro um passe grava normal e
  distância do mapa numa textura do tamanho da tela; o shader traça onde a superfície
  termina (silhueta) ou dobra (quina). O traço tem 1 px a cada 1080 linhas e fica mais
  leve ao longe. A água não recebe traço. `draw_district(..., ink=False)` desliga.

Personagens e a arma em primeira pessoa usam as mesmas texturas
(`model_lighting.py`), então escurecem junto com o cenário. O minimapa é desenhado
sem essa luz e sem contorno. Para mudar o horário, altere `SUN` (personagens acompanham) e a paleta
`SUN_COLOR`/`SHADE_COLOR`/`DEEP_COLOR` no mesmo arquivo; não é preciso reexportar.

## Regras que a geometria precisa manter

- Pisos decorativos usam `g.overlay(...)` com prioridade: a exportação recorta os
  de menor prioridade, então dois acabamentos nunca ficam no mesmo plano.
- Nada fica coplanar com cor/padrão diferente (`check_map_overlaps.py` deve dar 0).
- Uma fileira contínua de prédios (`perimeter`) fecha os quatro lados fora da área
  jogável; ruas, pátios e margens sempre terminam em fachada, nunca no vazio. O
  canal segue para um túnel de tijolos escuro além das grades.
- Os prédios do horizonte não se sobrepõem e são rebaixados para não cruzar os
  vasos gigantes do céu.
- Fachadas são decoradas no fim do build (`g.flush_facades()`), quando todos os volumes
  já foram registrados com `g.solid(...)` (`g.block` registra sozinho). Uma sacada só
  aparece se houver 1 m livre à frente dela: nunca invade outro prédio nem outra sacada.
- Placas na parede usam `g.keep_clear(...)`, que tira as janelas atrás delas.
- Escadas ficam fora das ruas e chegam de frente na borda do patamar (com abertura no
  guarda-corpo): o controlador não sobe degraus, então chegar pela lateral não funciona.
  As hemácias andam em linha reta
  entre os nós de `rbc_edges`, então todo trecho precisa passar em `check_rbc_routes.py`.
- O jogo usa plano de recorte próximo de 8 cm (`scenery.configure_depth`).

Os testes de `tests/test_traversal.py` verificam: spawns sobre chão seguro;
marcadores sobre superfícies caminháveis; rampas que tiram o herói mais lento do
canal; as três pontes atravessáveis; passagem sob a ponte central; escadas das
passarelas; navegação das duas bases a todos os objetivos e sugestões de colônia;
e ausência de linha de visão direta entre as bases.

O controlador de personagem não sobe degraus: toda escada visível tem uma rampa de
colisão invisível com no máximo ~27°.
