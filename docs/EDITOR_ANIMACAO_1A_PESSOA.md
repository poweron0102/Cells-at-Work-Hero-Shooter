# Editor de animação de 1ª pessoa

As poses de primeira pessoa de todos os heróis (mãos na arma e recarga) ficam em
`Assets/Weapons/<herói>_fp_anim.json`. O jogo lê esse arquivo (`UserComponents/cells/fp_arms.py`)
e o relê sozinho quando ele muda, então dá para ajustar com o jogo aberto: a mudança aparece na
próxima recarga.

## Abrir o editor

Dê dois cliques em `Editor Animacao 1a Pessoa.bat`, na raiz do projeto (ou rode
`.venv\Scripts\python.exe scripts\editor_fp\server.py`). O navegador abre sozinho em
`http://127.0.0.1:8765/`. Deixe a janela preta aberta enquanto edita. A página baixa o three.js da
internet (jsdelivr).

O servidor calcula cada pose com o código do jogo (`fp_arms.Arms`, `weapons.gun_matrix`): o
que aparece no editor é o que aparece no jogo. **Salvar no jogo** grava o JSON. Antes de gravar,
o editor copia a versão anterior para `.scratch/fp_anim_backups/`.

## Conceitos

- **Empunhadura** (`grips`): um cilindro preso à arma ou a uma peça animada (`part`: `pump`,
  `mag`, `bolt`). A palma encosta no cilindro e os dedos fecham sozinhos em volta dele. Se você
  mudar uma empunhadura, mudam todas as chaves que a usam.
- **Trilha da mão** (`tracks.L`, `tracks.R`): uma lista de chaves no tempo da recarga (0 a 1).
  Em cada chave, a mão está numa empunhadura. Entre duas chaves, a mão viaja até a próxima, com
  arco opcional, e os dedos abrem no caminho. A **primeira chave** de cada mão também é a pose
  parada, fora da recarga.
- **Ajuste fino da chave**: deslocamento, rotação da mão (com pivô no punho) e ângulos de dedos
  manuais, somados à pose da empunhadura.
- **Pulso** (por chave): a mão manda e o antebraço sai do punho conforme o pulso, dentro do que uma
  mão de verdade alcança. `[flexão, desvio]` em graus, a partir da mão reta com o antebraço:
  flexão (X) de **-40 a +50** (+ = dedos para o lado da palma) e desvio (Y) de **-40 a +10**
  (+ = para o polegar, - = para o mindinho; igual nas duas mãos). O pulso não torce: o antebraço torce
  junto com a mão. Sem valor na chave, o pulso é **automático**: segue a direção do ombro (IK) até o
  limite e, se com isso o cotovelo aparecer na tela, dobra o que os limites deixarem para tirá-lo de
  vista (por baixo ou pelos lados; `fp_arms.offscreen`). Se o ombro pedir mais do que o limite, o
  antebraço sai da direção do ombro e o painel da chave avisa — gire a mão na empunhadura
  (giro/palma), mova o ombro ou mexa a arma na recarga (`tilt`). O teste
  `test_elbows_stay_off_screen` confere todos os heróis. No editor: caixa **manual**
  em "Pulso" e o gizmo **Pulso** (R). Limites em `fp_arms.WRIST_X` / `WRIST_Y`.
- **Curvas** (`curves`): `tilt` (peso de 0 a 1 da inclinação da arma definida em `tilt`), `bolt`
  (bomba/ferrolho), `mag` (carregador), `bump` (pulo da arma em metros) e `squeeze` (aperto da
  bolsa das armas orgânicas: 0 = normal, 1 = encolhe 45%). O editor só mostra as curvas das peças
  que a arma tem.
- **Cartucho** (`shell`): janelas de tempo em que a mão esquerda segura um cartucho.

## Formato do JSON

As distâncias são em metros e os ângulos em graus. "Espaço da arma" segue o glTF: +X é a
esquerda da arma, +Y é para cima e +Z é a frente (o cano). "Espaço da vista" tem a câmera na
origem, olhando para +Z.

```jsonc
{
  "hero": "macrophage",
  "notes": "texto livre",
  "duration": 1.6,                       // só para a prévia; no combate a recarga dura 1,6 s
  "grips": {
    "pump": {
      "c": [0.004, 0.071, 0.372],        // centro do cilindro (espaço da arma ou da peça)
      "axis": [0, 0, 1],                 // direção do cilindro; o polegar aponta para este lado
      "palm": [0.39, -0.92, 0],          // do eixo para a palma (de que lado a mão encosta)
      "r": [0.04, 0.05],                 // raio na direção da palma e raio lateral
      "part": "pump",                    // peça que a mão acompanha (null = arma)
      "tilt": 34.4,                      // giro da mão sobre o cilindro
      "opp": 63.0,                       // oposição do polegar
      "fix": {"index": [7, 31, 20]},     // dedos fixos (polegar: [oposição, base, meio, ponta])
      "reach": null                      // limite de curvatura por falange (null = 95, 105, 80)
    }
  },
  "shoulders": {"R": [x, y, z], "L": [x, y, z]},  // ombros (espaço da vista, fora da tela)
  "poles": {"R": [x, y, z], "L": [x, y, z]},      // para onde cada cotovelo dobra
  "tracks": {
    "R": [{"t": 0, "grip": "grip"}],
    "L": [
      {"t": 0, "grip": "pump"},
      {"t": 0.19, "grip": "pouch",
       "arc": [0.02, -0.04, -0.06],      // desvio no meio do caminho até esta chave (arma)
       "offset": [0, 0.01, 0],           // deslocamento extra da mão (arma)
       "rot": [0, 0, 15],                // gira a mão no punho: X lateral, Y costas da mão, Z dedos (ordem XYZ)
       "wrist": [20, -10],               // pulso [flexão -40..50, desvio -40..10]; ausente = automático
       "fingers": {"thumb": [40, 0, 10, 10]},   // dedos manuais nesta chave
       "open": 0.7,                      // quanto os dedos abrem no caminho (padrão 0,7 se troca de empunhadura)
       "ease": "smooth"}                 // smooth | linear | in | out | step
    ]
  },
  "shell": [[0.17, 0.41]],
  "tilt": [roll, pitch, yaw, x, y, z],   // inclinação máxima da arma (graus, metros)
  "curves": {
    "tilt": [[0, 0], [0.14, 1], [0.84, 1], [1, 0]],   // [tempo, valor] ou [tempo, valor, ease]
    "bolt": [...], "mag": [...], "bump": [...], "squeeze": [...]
  }
}
```

Só `t` e `grip` são obrigatórios numa chave. Entre dois pontos, as curvas usam `smooth`
(smoothstep), a não ser que o ponto de chegada indique outro `ease`.

## Para um agente aplicar uma animação exportada

1. Copie o JSON exportado para `Assets/Weapons/<herói>_fp_anim.json`. Não é preciso mudar código.
2. Valide e rode os testes:
   `.venv\Scripts\python.exe -m unittest tests.test_fp_arms tests.test_weapon_assets`.
   `fp_arms.parse_config` explica o que estiver inválido.
3. Se quiser conferir em imagem: `.venv\Scripts\python.exe scripts\check_weapons.py --only <herói>`.

## Malhas dos braços

Os braços com esqueleto (`Assets/Weapons/<herói>_arms.glb`) vêm de
`referencias/scripts/personagens/build_fp_arms.py`, com um estilo por herói (`STYLES`: manga, pele,
luva, punho, anéis, dedos sem malha, garras). As armas desses heróis são exportadas sem os braços
rígidos (`build_weapons.py` ignora as peças `arm_*` de quem tem estilo em `STYLES`).

A animação de terceira pessoa da Macrófaga é feita no Blender
(`referencias/scripts/personagens/animate_macrophage.py`) e não lê este arquivo.
