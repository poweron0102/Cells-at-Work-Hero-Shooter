# Cells at Work — Bairro Arterial

Protótipo FPS 3v3 em **Python 3.14**, usando a EasyCells3D deste repositório.
Inclui multiplayer em rede local, oito heróis com kits próprios, bots de treino e
um bairro grande modelado no Blender: escolta das plaquetas, hemácias que entregam
oxigênio e fogem de bactérias, colônias bacterianas construídas pelos jogadores,
reconhecimento de antígenos e reconhecimento do mapa após o fechamento da ferida.

As regras seguem `docs/PLANO_OBJETIVOS_E_HEROIS.md` e o mapa segue `docs/PLANO_MAPA.md`.
Os valores de balanceamento estão centralizados em `UserComponents/cells/catalog.py`
(`BALANCE`) e ainda não foram validados em partidas com pessoas.

## Jogar

O ambiente `.venv` deste workspace já está preparado. Execute:

```powershell
.venv\Scripts\python.exe main.py
```

Também pode abrir `Jogar.bat`. No menu, informe seu nome e escolha **Criar sala**.
Os outros jogadores informam o IPv4 do anfitrião em **IP do servidor** e clicam em
**Entrar na rede**. Use `127.0.0.1` para vários processos no mesmo computador.

No lobby, **Escolher herói** permite escolher também a facção, respeitando três
vagas por time. **Iniciar 3v3** exige seis jogadores humanos. **Treino + bots**
completa as vagas restantes com combatentes de treino identificados como BOT.

```powershell
# Anfitrião
.venv\Scripts\python.exe main.py --host --name "Neutrophil"

# Cada um dos outros cinco jogadores, usando o IPv4 do anfitrião
.venv\Scripts\python.exe main.py --join 192.168.1.100 --name "Macrophage"

# Partida imediata com cinco bots
.venv\Scripts\python.exe main.py --training
```

A sala usa **TCP e UDP na porta 25765**; permita o Python na rede privada se o Windows solicitar.
O argumento `--port` permite outra porta, que deve ser a mesma em todos os processos.

### Log de rede (RPC)

Adicione `--rpc-log` para gravar todas as chamadas de rede (RPCs e variáveis de rede, enviadas e
recebidas, com protocolo, tamanho, destino, argumentos e status) em `logs/rpc/rpc_<data>_<pid>.jsonl`,
ou `--rpc-log arquivo.jsonl` para escolher o arquivo. A variável de ambiente `EASYCELLS_RPC_LOG=1`
(ou `=arquivo.jsonl`) liga o mesmo log em qualquer ponto de entrada, inclusive nos testes. Sem a
flag nada é gravado. Abra os arquivos em **`Visualizador RPC.html`** (vários peers podem ser
combinados; no Chrome/Edge a opção *Ao vivo* acompanha o jogo rodando).

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

**Escolta contínua.** As plaquetas saem da estação das células, percorrem a avenida
arterial, contornam o chafariz da praça, cruzam a ponte central do canal e seguem
até a obra da ferida. Avançam sozinhas; param apenas quando há bactéria viva logo à
frente, na mesma passagem e com linha de visão (quem está em passarelas, sob a ponte
ou atrás de paredes não bloqueia). O progresso nunca regride. Ao chegar, a ferida é
fechada (irreversível) e as bactérias deixam de renascer pela entrada.

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
- Células: ferida fechada, nenhuma colônia e nenhuma bactéria viva.

**Antígenos e desbloqueios.** Bactérias derrotadas deixam amostras. Coletá-las
aumenta o reconhecimento compartilhado (Macrófago rende mais). B Cell é liberado
na primeira meta e Killer T na segunda.

**Reconhecimento do mapa.** Depois do fechamento, células que ocupam o posto da
torre treliçada da praça, sem bactérias presentes, revelam temporariamente as colônias.

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

## Mapa: Bairro Arterial

Mapa novo, com cerca de **124 × 186 m** de área jogável e um horizonte de prédios
altos e vasos gigantes ao fundo. Foi construído do zero no Blender a partir das
imagens de `referencias/`:

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
gravado no UV de cada face. Para editar e reexportar, veja
[docs/MAPA_BAIRRO_ARTERIAL.md](docs/MAPA_BAIRRO_ARTERIAL.md).

## Personagens

Os oito heróis, as hemácias e as plaquetas são modelos novos feitos no Blender a
partir das imagens de `Assets/characters/` (`scripts/build_characters.py`),
exportados em partes animadas proceduralmente pelo jogo. Veja
`Assets/characters/SOURCES.md` para regenerar.

## Armas e tiros

Cada herói tem a arma descrita no GDD, modelada no Blender por `scripts/build_weapons.py`
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
    --python scripts\build_weapons.py                      # prévias em .scratch/weapons/
.venv\Scripts\python.exe scripts/check_weapons.py           # capturas no jogo (--third: vista de outro jogador)
```

## Câmera livre para referências

Execute `.venv\Scripts\python.exe main_freecam.py`. Essa entrada abre diretamente o
Bairro Arterial, sem partida, bots ou colisões.

- **WASD / mouse:** voar e olhar. **E ou Espaço / Q ou Ctrl:** subir e descer.
- **Shift / Alt:** acelerar e mover com precisão.
- **Roda do mouse:** FOV; **R:** vista inicial; **Esc:** soltar/prender o mouse.
- **F1:** painel; **P:** salvar referência em `capturas/` (`print.png`, `camera.json`, `referencia.txt`).

## Estrutura e validação

As cenas `menu`, `lobby`, `selection`, `abrasion` e `results` ficam em `Levels/`.
Regras, física, combate, rede, interface e fábricas ficam em `UserComponents/cells/`:

- `rules.py`: estado da partida, escolta, colônias, infecção, antígenos, vitória.
- `arena.py`: servidor autoritativo; valida pedidos e envia snapshot a 10 Hz.
- `npcs.py`: hemácias (rotas, percepção, fuga, retomada).
- `actors.py` / `combat.py`: heróis, kits, construção e respawn.
- `bots.py`, `navigation.py`, `hud.py`, `visuals.py`, `player.py`, `scenery.py`.

Cada jogador simula seu movimento, mira, arma e habilidades localmente
(`NetworkTransform` por UDP). Pedidos sobre objetos compartilhados (construir,
desenvolver, ferir hemácia ou colônia) vão ao anfitrião, que valida e replica o
resultado, evitando gastos ou coletas duplicadas.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts/check_multiplayer.py      # host + 5 clientes
.venv\Scripts\python.exe scripts/check_scenes.py           # todas as cenas, janela oculta
.venv\Scripts\python.exe scripts/check_hud.py              # capturas da HUD em .scratch/hud/
.venv\Scripts\python.exe scripts/check_match_views.py      # capturas da partida em .scratch/match/
.venv\Scripts\python.exe scripts/render_district.py        # vistas do mapa em .scratch/district/
.venv\Scripts\python.exe scripts/check_art.py              # modelos dos personagens
```

O GDD original está em [docs/GDD_Cells_at_Work_Hero_Shooter_Prototype.html](docs/GDD_Cells_at_Work_Hero_Shooter_Prototype.html).
O mapa anterior, Bairro dos Canais, seus atlas e suas ferramentas exclusivas
foram removidos. O único mapa mantido é o Bairro Arterial. Veja
[Assets/README.md](Assets/README.md) para a organização dos assets e os comandos
de geração.
