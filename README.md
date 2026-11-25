# Cells at Work — Hero Shooter

Protótipo FPS 3v3 em **Python 3.14**, usando a EasyCells3D deste repositório.
Inclui multiplayer em rede local, oito heróis com kits próprios, bots de treino e
**quatro mapas** modelados no Blender a partir do anime: Bairro Arterial, Timo, Medula Óssea e
Coração. Há escolta das plaquetas, hemácias que entregam oxigênio e fogem de bactérias,
colônias bacterianas construídas pelos jogadores, reconhecimento de antígenos e reconhecimento
do mapa após o fechamento da entrada bacteriana. A Medula e o Coração trocam a escolta por
objetivos próprios (treino de entrega dos eritroblastos; comboio de hemácias que só atravessa as
valvas abertas).

As regras seguem `docs/PLANO_OBJETIVOS_E_HEROIS.md` e o mapa segue `docs/PLANO_MAPA.md`.
Os valores de balanceamento (atributos de cada herói e regras da partida) estão em `Assets/balance.json`
e ainda não foram validados em partidas com pessoas.

## Jogar

Em um computador novo, instale o **Python 3.14 64-bit** (python.org) e abra `Instalar.bat`:
ele cria a `.venv` e instala as dependências. O pybullet vem pré-compilado em `wheels/`,
então não é preciso compilador C++. Depois disso, execute:

```powershell
.venv\Scripts\python.exe main.py
```

Também pode abrir `Jogar.bat`. No menu, informe seu nome e escolha **Criar sala**.
Os outros jogadores informam o IPv6 do anfitrião (ou o IPv4, na mesma rede) em **IP do servidor** e clicam em
**Entrar na rede**. Use `127.0.0.1` para vários processos no mesmo computador.
Os nomes e IPs usados ficam como etiquetas abaixo de cada campo (clique para
preencher, **×** para apagar); eles são salvos só neste computador, em
`saves/recentes.json`. Tab troca de campo e Enter entra na rede.

**Configurações** (no menu, ou em Esc › *configurações* durante a partida) abre o painel com quatro abas:
**Vídeo** (janela ou tela cheia sem bordas, resolução, limite de FPS, VSync, campo de visão e qualidade
das sombras, que vale a partir da próxima partida), **Áudio** (volume geral, efeitos, vozes e dublagem
japonesa/inglesa), **Controles** (sensibilidade do mouse e da luneta, inverter eixo Y e a lista de teclas)
e **Jogo** (contador de FPS, gravar replays e mapa ao hospedar). Tudo muda na hora e fica salvo em
`saves/config.json`; *Restaurar padrões* desfaz só a aba aberta.

No lobby, o anfitrião escolhe o **mapa** com as setas ao lado do nome, no alto da tela (a escolha
fica salva em `saves/config.json`; os outros jogadores veem o mapa escolhido).
Seu herói aparece animado e explica as habilidades em balões.
**Trocar herói** abre a tira de retratos: passar o mouse mostra a prévia do kit,
clicar marca e **Escolher!** confirma (Esc cancela). Dá para escolher também a
facção, respeitando três vagas por time. **Iniciar 3v3** exige seis jogadores humanos. **Treino + bots**
completa as vagas restantes com combatentes de treino identificados como BOT.

```powershell
# Anfitrião
.venv\Scripts\python.exe main.py --host --name "Neutrophil"

# Cada um dos outros cinco jogadores, usando o IPv6 (ou IPv4 na mesma rede) do anfitrião
.venv\Scripts\python.exe main.py --join 192.168.1.100 --name "Macrophage"

# Partida imediata com cinco bots
.venv\Scripts\python.exe main.py --training
```

A sala usa **TCP e UDP na porta 25765**; o anfitrião escuta em `::` (IPv6 e IPv4 juntos). Permita o Python nas redes privada e pública se o Windows solicitar, e libere a porta 25765 no roteador se o acesso for pela internet.
O argumento `--port` permite outra porta, que deve ser a mesma em todos os processos.

### Log de rede (RPC)

Adicione `--rpc-log` para gravar todas as chamadas de rede (RPCs e variáveis de rede, enviadas e
recebidas, com protocolo, tamanho, destino, argumentos e status) em `logs/rpc/rpc_<data>_<pid>.jsonl`,
ou `--rpc-log arquivo.jsonl` para escolher o arquivo. A variável de ambiente `EASYCELLS_RPC_LOG=1`
(ou `=arquivo.jsonl`) liga o mesmo log em qualquer ponto de entrada, inclusive nos testes. Sem a
flag nada é gravado. Abra os arquivos em **`Visualizador RPC.html`** (vários peers podem ser
combinados; no Chrome/Edge a opção *Ao vivo* acompanha o jogo rodando).

### Replays

No lobby, o anfitrião marca **Gravar replay** (a escolha fica salva em `saves/config.json`;
os clientes veem o aviso *Partida será gravada*). A partida vira um arquivo
`replays/<data>_<hora>.replay` com um resumo `.json` ao lado. Uma partida 3v3 ocupa cerca de 3 KB por
segundo de jogo. No menu, **Assistir replays** abre a estante com as partidas
gravadas; os resultados também oferecem **Assistir replay** logo após a partida. Na linha de comando,
`--record` grava a partida de `--host`/`--training` e `--replay [arquivo]` abre a estante (ou o replay
indicado).

A reprodução é em 3ª pessoa, sem HUD de combate. Os controles são:

| Tecla | Ação |
|---|---|
| Espaço | pausa / continua (no fim, recomeça) |
| ← / → (Shift: 15 s) | volta / avança 5 s; dá para arrastar na linha do tempo (as marcas são abates) |
| ↑ / ↓ | velocidade de 0,25x a 4x |
| 1–6, Tab | segue um jogador (ou clique no quadro dele) |
| C | câmera livre: botão direito gira, WASD move, Q/E desce e sobe, Shift acelera |
| H | esconde / mostra os controles |
| Esc | volta à estante |

O arquivo guarda o que um espectador receberia do anfitrião (posições, tiros, projéteis, zonas,
habilidades, vida, abates e o snapshot dos objetivos). Também guarda a mira vertical de cada herói,
que a rede normal não replica: os clientes a enviam só ao anfitrião, a 10 Hz, enquanto a partida é
gravada. Voltar no tempo remonta a cena e avança rapidamente até o ponto pedido. Os arquivos podem ser
enviados a outra pessoa. A leitura não executa código do arquivo (unpickler restrito). Um replay
gravado com outro `balance.json` abre normalmente, mas avisa que granadas e zonas podem divergir.

## Controles

| Entrada | Ação |
| --- | --- |
| WASD / mouse | Movimento / mira |
| Shift / Espaço | Correr / pular |
| Botão esquerdo | Arma principal (B Cell dispara a cada clique) |
| Botão direito | Ação secundária do kit (B Cell: segurar para mira com zoom) |
| Q | Habilidade |
| F | Especial (carrega com combate e objetivos, nunca só com o tempo) |
| G (segurar) | Bactérias: construir colônia no chão à frente (mostra custo e motivo de impedimento) |
| E | Bactérias: entregar recursos carregados a uma colônia próxima |
| R | Recarregar |
| Tab | Espectador: alternar entre aliados vivos |
| Esc | Menu; a partida em rede continua |

Recursos e antígenos são recolhidos fisicamente, passando por cima deles. Células
que passam sobre recursos bacterianos os destroem.

## Objetivos

O lado das bactérias é igual em todos os mapas (colônias, infecção, recursos das hemácias,
antígenos). O objetivo das células muda com o mapa:

| Mapa | Objetivo das células | O que sela a entrada bacteriana |
| --- | --- | --- |
| Bairro Arterial, Timo | Escolta das plaquetas até a ferida | A ferida fechada |
| Medula Óssea | Treino de entrega dos eritroblastos (formatura) | A meta de formaturas |
| Coração | Comboio de hemácias pelo coração, com valvas no ritmo do batimento | O comboio chegando ao pulmão |

**Escolta contínua (Bairro Arterial e Timo).** As plaquetas saem da estação das células e seguem
até a ferida: no Bairro, pela avenida arterial, em volta do chafariz e pela ponte central do canal;
no Timo, pelo campo de treino e pelo corredor principal do labirinto até a cápsula rompida. Avançam sozinhas; param apenas quando há bactéria viva logo à
frente, na mesma passagem e com linha de visão (quem está em passarelas, sob a ponte
ou atrás de paredes não bloqueia). O progresso nunca regride. Ao chegar, a ferida é
fechada (irreversível) e as bactérias deixam de renascer pela entrada.

**Treino de entrega (Medula Óssea).** Não há plaquetas nem hemácias adultas: os eritroblastos
(hemácias crianças) saem um de cada vez do berçário com uma caixinha de O₂ de treino e vão até os
postos de formatura A, B ou C pela cidade de papelão. Cada criança que chega conta uma formatura;
ao bater a meta (`training_goal`), a medula entra em alerta e a entrada bacteriana é selada.
Atingida por bactérias, a criança não morre: larga a caixa (vira recurso) e volta chorando ao
berçário, sem poder ser atingida de novo até sair com outra caixa. Ela é, ao mesmo tempo, a
economia das bactérias e o objetivo das células. Células perto de uma criança no treino carregam o
especial.

**Comboio e batimento (Coração).** Uma carreta de CO₂ puxada por hemácias segue da veia cava até o
pulmão, com as mesmas regras de bloqueio da escolta (bactéria viva à frente, na mesma passagem).
Duas valvas, portões no caminho, abrem e fecham no ritmo do batimento e se alternam como no
coração de verdade: a **tricúspide** fecha na sístole e a **pulmonar** na diástole. A HUD mostra
o traçado do ECG e o estado de cada valva. Fechada, a valva bloqueia passagem e tiros, e quem
estiver no vão é empurrado para o lado mais próximo. O comboio espera no batente e segura aberta
a valva que está atravessando. **Endocardite:** uma colônia construída a até `valve_jam_radius` m de
uma valva a emperra fechada; o comboio só passa depois que as células destruírem essa colônia.
Corredores laterais contornam as valvas, então só o comboio depende delas.

**Hemácias e economia.** Hemácias levam oxigênio aos edifícios A, B e C, cada um com
duas portas e rotas alternativas. Ao avistar uma bactéria, fogem e tentam outro
caminho; sem rota segura, recuam e esperam. Mortas, deixam recursos que cada
bactéria recolhe para si e perde ao morrer.

**Colônias.** Cada bactéria mantém até três colônias. Construir custa recursos só ao
concluir; levar dano interrompe. Colônias servem de ponto de renascimento, dão
redução de dano às demais (com teto) e somam infecção. Entregar recursos as
desenvolve. Destruir uma remove toda a sua contribuição.

**Vitória.**
- Bactérias: infecção coletiva atinge a meta (várias colônias desenvolvidas), mesmo com a ferida aberta.
- Células: entrada bacteriana selada (ferida fechada, formatura ou comboio no pulmão), nenhuma colônia e nenhuma bactéria viva.

**Antígenos e desbloqueios.** Bactérias derrotadas deixam amostras. Coletá-las
aumenta o reconhecimento compartilhado (Macrófago rende mais). B Cell é liberado
na primeira meta e Killer T na segunda.

**Reconhecimento do mapa.** Depois do fechamento, células que ocupam o posto de reconhecimento,
sem bactérias presentes, revelam temporariamente as colônias. O posto é a torre treliçada da praça
(Bairro Arterial), a torre de observação do campo (Timo), o pé da torre do relógio (Medula) e o
pátio oeste do átrio (Coração).

**Respawn.** Durante a contagem, a câmera acompanha quem eliminou você. Bactérias
escolhem entrada ou colônia; sem nenhuma das duas, acompanham um aliado vivo (Tab
alterna) até que alguém construa uma colônia.

Não há mais Systemic Stress, fases cronometradas, núcleos fixos nem resposta imune compartilhada.

## Heróis

| Herói | Botão direito | Q | Especial (F) |
| --- | --- | --- | --- |
| Neutrophil | Golpe de faca | Avanço cortante | Marca inimigos próximos e acelera aliados |
| Macrophage | Machado em arco | Golpe no chão que empurra | Proteção para si e aliados próximos |
| B Cell | Zoom com mira | Disparo que marca e enfraquece a proteção (também de colônias) | Feixe de anticorpos que atravessa inimigos |
| Killer T | Golpe forte (execução em alvos feridos) | Salto com impacto | Sequência de golpes fortalecidos |
| Pneumococcus | Investida com empurrão | Cápsula que absorve dano | Nuvem que prejudica a visão e causa dano |
| Staphylococcus | Projétil aderente que desacelera | Repara colônia próxima | Fortifica colônias próximas |
| Pseudomonas | Ácido com explosão | Biofilme (acelera aliados, desacelera inimigos) | Biofilme maduro e corrosivo |
| Streptococcus | Hemólise, forte contra hemácias | Arrancada, também no ar | Mais mobilidade e cadência |

## Mapas

| Mapa | Episódio | Modo | Destaques |
| --- | --- | --- | --- |
| Bairro Arterial | S01E02 | escolta | Canais e pontes, avenida arterial, obra da ferida. |
| Timo | S01E09 | escolta | Dormitório, campo de treino com alambrado, labirinto do exame final, trilha da floresta. |
| Medula Óssea | S01E06 | treino de entrega | Berçário, torre do relógio, cidade de papelão, academia com arcadas, canal com ponte em arco. |
| Coração | S01E08 | comboio + valvas | Templo do átrio direito, túnel de torii, ventrículo listrado, artéria pulmonar, estação do pulmão. |

Os quadros do anime usados como referência ficam em `referencias/<Mapa>/`, com um README que diz
o que cada quadro inspirou. A construção, as regras de cada mapa e os comandos estão em
[docs/MAPAS_NOVOS.md](docs/MAPAS_NOVOS.md).

### Bairro Arterial

Mapa com cerca de **124 × 186 m** de área jogável e um horizonte de prédios
altos e vasos gigantes ao fundo. Foi construído do zero no Blender a partir das
imagens de `referencias/imagens/`:

- Estação de serviço das células (sul), com duas saídas protegidas por anteparos.
- Avenida arterial em madeira ocre, prédios com sacadas, passarelas a 4 m, arcos
  vermelhos e a lanterna "Artery" suspensa.
- Praça da ponte com ladrilhos pastéis, chafariz-coração, torre treliçada
  (posto de reconhecimento), pérgula azul e terraços nas esquinas.
- Canal raso atravessável, com rampas nas duas margens, passagem sob as três pontes
  (oeste com escadarias e guarda-corpo ornamentado, central da escolta, leste com
  arcos azuis) e túneis nas extremidades.
- Edifícios de oxigênio A (sudoeste), B (leste) e C (noroeste), pátios e recuos
  favoráveis a colônias, Rua Norte e Rua da Obra.
- Obra da ferida ao norte: cratera de tecido onde as bactérias entram, protegida
  por anteparos, andaimes, guindastes, barreiras, cones e túnel de manutenção em tijolo.
- Vida ambiente: multidão de hemácias e plaquetas nas sacadas, água animada,
  hemácias de entrega circulando e a equipe de plaquetas carregando materiais.

O jogo carrega `Assets/Maps/BairroArterial/BairroArterial.glb`, `runtime.json`
(colisão, marcadores, rotas) e `nav.json` (navegação dos bots); não precisa do
Blender. Os padrões (tijolo, pedras irregulares, ladrilhos, madeira, água) são
desenhados por um shader em `UserComponents/cells/scenery.py` a partir do id
gravado no UV de cada face. A iluminação em estilo anime (sombra do sol em faixas,
túneis e vãos cobertos mais escuros, postes acesos onde falta céu, contorno de
nanquim nas quinas e silhuetas) é calculada ao
carregar o mapa por `UserComponents/cells/lighting.py` e vale também para os
personagens. Para editar e reexportar, veja
[docs/MAPA_BAIRRO_ARTERIAL.md](docs/MAPA_BAIRRO_ARTERIAL.md).

## Personagens

Os personagens foram modelados no Blender a partir das imagens de `referencias/personagens_oficiais/`.
Macrófaga, Célula B, hemácia e plaqueta têm esqueleto e clipes no GLB; os demais heróis usam
animação procedural por partes (`referencias/scripts/personagens/build_characters.py`).
Célula B, hemácia e plaqueta vêm do Tripo, com animações CC0 do Mesh2Motion aplicadas por
`referencias/scripts/personagens/tripo_characters.py` (fontes em `referencias/animacoes/`).

No jogo, `UserComponents/cells/animation.py` dá a cada personagem com esqueleto um animador
próprio: parado, andando e correndo se misturam pela velocidade, sem trocas secas; disparo,
recarga e golpe mexem só no tronco, com as pernas seguindo a locomoção; a aterrissagem e um
disparo reiniciado entram por cima do anterior. NPCs fora da câmera não são animados.

## Armas e tiros

Cada herói tem a arma descrita no GDD, modelada no Blender por `referencias/scripts/personagens/build_weapons.py`
(`Assets/Weapons/<herói>.glb` + `.json`): SMG citotóxica (Neutrophil), escopeta-machado
(Macrophage), rifle de anticorpos (B Cell), fuzil de rajada (Killer T) e armas orgânicas
para as bactérias (canhão de cápsula, lançador de cachos, fuzil de ácido e SMG de contas).
As peças móveis (ferrolho, bomba, carregador, tambor, bolsa) e os braços de primeira pessoa
são malhas separadas, e o JSON guarda o cano, a janela de ejeção e a pose da câmera.

- **Primeira pessoa** (`weapons.py`): passe próprio com profundidade limpa e FOV fixo; recuo
  por molas, balanço do mouse, passos, corrida, recarga com troca de carregador, golpe com
  rastro, saque, clarão no cano e cápsulas ejetadas.
- **Terceira pessoa**: a mesma arma vai na mão do personagem (ponto `mount` do JSON do
  personagem), com recuo a cada disparo; Neutrophil e Killer T levam a faca na outra mão.
- **Tiros** (`shots.py`): o acerto continua instantâneo a partir do olho, mas o projétil visível
  sai do cano e viaja até o alvo com estilo por herói, deixa rastro, faíscas ou respingos no
  impacto e marcas nas superfícies.

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup `
    --python referencias\scripts\personagens\build_weapons.py                      # prévias em .scratch/weapons/
.venv\Scripts\python.exe scripts/check_weapons.py           # capturas no jogo (--third: vista de outro jogador)
```

## Câmera livre para referências

Execute `.venv\Scripts\python.exe main_freecam.py [--map timo]`. Essa entrada abre diretamente o
mapa (o Bairro Arterial, se `--map` não for informado), sem partida, bots ou colisões.

- **WASD / mouse:** voar e olhar. **E ou Espaço / Q ou Ctrl:** subir e descer.
- **Shift / Alt:** acelerar e mover com precisão.
- **Roda do mouse:** FOV; **R:** vista inicial; **Esc:** soltar/prender o mouse.
- **F1:** painel; **P:** salvar referência em `capturas/` (`print.png`, `camera.json`, `referencia.txt`).

## Estrutura e validação

As cenas `menu`, `lobby`, `selection` (abre o lobby já na seleção), `abrasion` e `results`
ficam em `Levels/`. Os menus usam o estilo Mangá de `manga_ui.py` (fontes Bangers e
M PLUS Rounded 1c, OFL, em `Assets/fonts/`); as telas ficam em `screens.py`.
Regras, física, combate, rede, interface e fábricas ficam em `UserComponents/cells/`:

- `maps.py` / `layout.py`: mapas disponíveis, modo de cada um e os marcadores do mapa ativo
  (`layout.select(chave)` antes de montar a arena).
- `rules.py`: estado da partida, escolta/comboio/formatura, colônias, infecção, antígenos, vitória.
- `heart.py`: batimento e valvas do Coração (determinístico pelo relógio replicado).
- `arena.py`: servidor autoritativo; valida pedidos e envia snapshot a 10 Hz.
- `npcs.py`: hemácias (rotas, percepção, fuga, retomada).
- `actors.py` / `combat.py`: heróis, kits, construção e respawn.
- `bots.py`, `navigation.py`, `hud.py`, `visuals.py`, `player.py`, `scenery.py`.
- `replay.py` / `replay_screens.py`: gravação no anfitrião, leitura e reprodução dos replays
  (cena `Levels/replay.py`: estante e controles no estilo Mangá).
- `audio.py` / `voice.py`: efeitos sonoros posicionados e falas dos personagens (dublagem
  japonesa ou inglesa, escolhida em `saves/config.json` via `settings.py`, ou por `CELLS_VOICE=en`).
- `settings.py` / `options.py`: preferências salvas em `saves/config.json` (validadas ao ler) e a tela de
  configurações, uma camada de UI persistente que desenha por cima de qualquer cena e aplica vídeo/áudio.

Cada jogador simula seu movimento, mira, arma e habilidades localmente
(`NetworkTransform` por UDP). Pedidos sobre objetos compartilhados (construir,
desenvolver, ferir hemácia ou colônia) vão ao anfitrião, que valida e replica o
resultado, evitando gastos ou coletas duplicadas.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts/check_multiplayer.py      # host + 5 clientes
.venv\Scripts\python.exe scripts/check_scenes.py           # todas as cenas, janela oculta (--map=coracao)
.venv\Scripts\python.exe scripts/check_match_views.py --map medula   # capturas de partida por mapa
.venv\Scripts\python.exe scripts/map_check.py --map timo     # confere um layout sem Blender
.venv\Scripts\python.exe scripts/check_hud.py              # capturas da HUD em .scratch/hud/
.venv\Scripts\python.exe scripts/check_match_views.py      # capturas da partida em .scratch/match/
.venv\Scripts\python.exe scripts/render_district.py        # vistas do mapa em .scratch/district/ (--map timo)
.venv\Scripts\python.exe scripts/check_art.py              # modelos dos personagens
```

O GDD original está em [docs/GDD_Cells_at_Work_Hero_Shooter_Prototype.html](docs/GDD_Cells_at_Work_Hero_Shooter_Prototype.html).
O mapa anterior, Bairro dos Canais, seus atlas e suas ferramentas exclusivas
foram removidos. Os mapas atuais são o Bairro Arterial, o Timo, a Medula Óssea e o Coração. Veja
[referencias/README.md](referencias/README.md) para a organização dos assets e os comandos
de geração.
