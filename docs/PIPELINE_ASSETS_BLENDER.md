# Pipeline de assets do Blender para o jogo

Os mapas são o **Bairro Arterial**, o **Timo**, a **Medula Óssea** e o **Coração**
([MAPAS_NOVOS.md](MAPAS_NOVOS.md)); todos usam o mesmo pipeline, escolhido com `--map`.
O Bairro dos Canais, seus atlas com bake e suas ferramentas exclusivas foram removidos. A organização de mapas,
personagens, armas e áudio está em [referencias/README.md](../referencias/README.md).

## Fonte e exports

`referencias/blender/BairroArterial.blend` é a fonte editável.
O jogo carrega `BairroArterial.glb`, `runtime.json` e `nav.json` de
`Assets/Maps/BairroArterial/`;
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
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background referencias\blender\BairroArterial.blend --python referencias\scripts\mapa\export_distrito.py
.venv\Scripts\python.exe referencias\scripts\mapa\build_navmesh.py
```

Para reconstruir a cena a partir dos scripts, use `referencias/scripts/mapa/rebuild_distrito.py`
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

## Macrófaga

`referencias/blender/macrophage.blend` contém a malha texturizada, o esqueleto
do corpo (com dois ossos por dedo nas duas mãos), a cadeia de quatro ossos da
trança e a escopeta. No Editor de Ações, selecione `macrophage.rig` para ver
`Idle`, `Walk`, `Run`, `Jump`, `Land`, `Fire`, `Reload` e `Melee`. A trança
acompanha a cabeça com atraso progressivo da raiz até a ponta, gravado nessas ações.

As ações são geradas por `animate_macrophage.py`: a mão direita fecha no cabo
com o indicador no gatilho, a esquerda segura a bomba por baixo e, na recarga,
a arma desce para a cintura enquanto a mão esquerda busca dois cartuchos na
cintura, empurra cada um na janela de carga e bombeia. Os ossos dos dedos e os
pesos da mão vêm de `macrophage_fingers.py` (criados só uma vez).

A coleção `macrophage.weapon_preview` exibe a escopeta no osso
`socket_weapon`. Para conferir o disparo ou a recarga, selecione também as
ações correspondentes do objeto `pump` no Editor de Ações.
Depois de animar, gere os GLBs da personagem e da arma e seus metadados:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background referencias\blender\macrophage.blend --python referencias\scripts\personagens\animate_macrophage.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python referencias\scripts\personagens\export_macrophage.py
```

## Hemácia, plaqueta e Célula B (Tripo + Mesh2Motion)

Os modelos de `referencias/Tripo 3D assets/` (`globulo vermelho.glb`, `plaqueta.glb`,
`linfocito b.glb`) chegam com esqueleto Mixamo em T. `tripo_characters.py` renomeia os ossos
para a convenção do projeto, escala até a altura do jogo e aplica os clipes CC0 de
`referencias/animacoes/mesh2motion/` (esqueleto Unreal): cada osso copia a rotação que o osso
correspondente fez a partir do repouso, e o quadril desloca na proporção das pernas. Depois:

- Walk e Run começam com o pé esquerdo à frente e guardam a passada (`strides` no JSON), para
  o jogo avançar o ciclo pela distância percorrida;
- os Idles ganham respiração e um olhar ao redor (os clipes baixados deixam cabeça e tronco parados);
- a Célula B tem o osso `socket_weapon` na mão direita, na pose do Rifle Idle, e a mão
  esquerda volta ao guarda-mão por IK em todo clipe (menos no meio da recarga);
- a hemácia tem a caixa de oxigênio (malha `box`, osso `box`) no clipe Carry: uma pose leve, com a
  caixa na cintura e rente à barriga (`BOX_CENTER`/`BOX_TILT` no script), montada sobre o Idle com a
  pegada das mãos do `walk-carry` (que, inteiro, parece carga pesada).

O JSON também diz qual parte do corpo cada clipe controla (`layers`: `upper` = tronco,
braços e cabeça; `lower` = quadril e pernas; `arms` = ombros, braços e caixa presos ao peito da
caminhada), usado por `UserComponents/cells/animation.py`.
Para trocar um clipe, edite `CHARACTERS` no script e rode:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python referencias\scripts\personagens\tripo_characters.py -- --only red_blood_cell,platelet,b_cell
```

As cenas ficam em `referencias/blender/<chave>.blend`, com as ações no Editor de Ações.

## Braços de primeira pessoa

Todos os heróis usam braços com esqueleto em primeira pessoa
(`Assets/Weapons/<herói>_arms.glb`): palma, quatro dedos de três falanges e
polegar. `build_fp_arms.py` gera a malha e os ossos; a pose é feita no jogo por
`UserComponents/cells/fp_arms.py`, que leva cada mão até uma empunhadura da
arma (cabo, bomba, guarda-mão, carregador), fecha os dedos falange por falange
até tocá-la e resolve ombro e cotovelo fora da tela. As armas desses heróis
não trazem mais braços rígidos.

As empunhaduras, as chaves de cada mão na recarga, a inclinação da arma e as
curvas das peças (bomba/ferrolho, carregador, solavanco) ficam em
`Assets/Weapons/<herói>_fp_anim.json`. Para editar visualmente, abra
`Editor Animacao 1a Pessoa.bat` (formato e uso em
[EDITOR_ANIMACAO_1A_PESSOA.md](EDITOR_ANIMACAO_1A_PESSOA.md)). O jogo relê o
arquivo quando ele muda.

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python referencias\scripts\personagens\build_fp_arms.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python referencias\scripts\personagens\build_weapons.py -- --only neutrophil,killer_t,pneumococcus,staphylococcus,pseudomonas,streptococcus --no-preview
.venv\Scripts\python.exe scripts\check_weapons.py
```
