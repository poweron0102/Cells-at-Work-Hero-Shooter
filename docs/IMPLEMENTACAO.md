# Implementação do protótipo Abrasion

## Organização conforme o guia

| Módulo | Responsabilidade |
| --- | --- |
| `Levels/menu.py` | Entrada e montagem da interface inicial |
| `Levels/lobby.py` | Montagem da sala e transição ao início da partida |
| `Levels/selection.py` | Montagem da seleção de personagem |
| `Levels/abrasion.py` | Física, câmeras e fábricas da arena; não contém comportamento de entidades |
| `Levels/results.py` | Relatório e saída da sessão |
| `catalog.py` | Dados dos oito kits, facções, limites e desbloqueios |
| `rules.py` | Estado da partida e condições de progresso/vitória testáveis sem janela |
| `network.py` | Sessão, lobby, comandos validados e snapshots |
| `actors.py` / `combat.py` | Componentes de combatente, arma, dano, habilidades e respawn |
| `arena.py` | Objetivos vivos, amostras, núcleos e coordenação da simulação |
| `director.py` | Eventos fisiológicos e alteração da passagem central |
| `world.py` / `visuals.py` | Fábricas do blockout e componentes `Renderable3D` |
| `player.py` | Entrada local e câmera de primeira pessoa |
| `bots.py` | Navegação e decisões dos combatentes opcionais de treino |
| `ui_base.py` / `screens.py` / `hud.py` | Interface sobre `CameraUI` e `RenderableUI` |
| `audio.py` | Feedback local de tiro, acerto, dano e evento |

Todos os módulos de gameplay acima ficam em `UserComponents/cells/`.
Não foi criado um loop de jogo, engine de física ou transporte paralelo.

São reutilizados `Game`, `Item`, `Component`, `Transform`, `Vec3`, `Quaternion`,
`Camera3D`, `CameraUI`, `Renderable3D`, `RenderableUI`, `BulletPhysicsWorld`,
`PhysicsBody3D`, `CharacterController3D`, shapes, raycasts, `overlap_sphere`,
`NetworkManager`, `TcpTransport` e o scheduler da biblioteca. Temporizadores de
gameplay usam `game.delta_time` para permanecer pausáveis e replicáveis.

Embora o guia mencione apenas física 2D, a biblioteca fornecida também inclui
`PhysicsComponents3D`. Ela cuida das colisões, gravidade, pulo e movimento.
Os widgets antigos de `UiComponents/` importam módulos legados ausentes;
a interface utiliza a camada atual `CameraUI`, sem pygame.

## Rede

O anfitrião também joga e é a autoridade de todos os combatentes, objetivos,
cooldowns e eventos. Clientes enviam intenção de movimento, mira e botões a 30 Hz.
O host publica snapshots a 20 Hz; o cliente interpola posições para apresentação.
Não aceita posição, dano, vida ou resultado enviados por um cliente.

O `ArenaNetwork` especializa `NetworkManager` e usa seu transporte TCP existente.
O snapshot agrupa entidades e objetivos para aplicar um estado coerente; por isso
não usa `NetworkTransform`, cujo modelo transfere a escrita do transform ao dono.
UDP fica desativado nesta aplicação, pois os handshakes TCP/UDP da biblioteca
atribuem IDs separadamente e podem divergir com conexões simultâneas.

- Seis vagas, três por time; o host valida todas as escolhas.
- Células iniciam com dois neutrófilos e um macrófago em uma sala completa.
- Desconexão no lobby libera a vaga; durante a partida, um bot assume a vaga.
- Entradas tardias em uma partida iniciada são recusadas, com mensagem no lobby.
- Fechar o host encerra a sessão; clientes mostram perda de conexão e saída ao menu.
- Sem migração de host, matchmaking, relay, autenticação ou compensação de latência.
- O alvo desta entrega é LAN. O teste automatizado usa loopback; não foi feita uma
  partida entre seis computadores físicos nem validação de internet/WAN.

## Ajustes necessários na biblioteca

- `NetworkTCP.py`: leitura incremental de pacotes fragmentados/agregados; envio de
  cada frame TCP em uma chamada; desconexão sem renumerar IDs; encerramento de
  sockets; timeout; `TCP_NODELAY`; limite de tamanho de pacote. Desserialização
  aceita dados primitivos, mas rejeita instâncias executáveis via pickle.
  RPCs/NetworkVariables que enviem instâncias Python precisam convertê-las em
  dados primitivos; os snapshots deste jogo já fazem isso.
- `NetworkManager`: opção `enable_udp=False` sem alterar o padrão existente;
  flags de conexão inicializadas antes das threads de transporte.
- `Camera3D`: limpa a câmera principal ao destruir a cena e tolera destruição
  de renderizável que ainda não recebeu `init()`.
- `Game`: limpa callbacks pendentes de objetos da cena anterior; encerramento
  idempotente de itens persistentes, física, scheduler e janela; cor de fundo e
  sinal de parada usados também pelos testes de renderização.

## Recorte dos kits e arte

Os oito heróis são selecionáveis e possuem atributos, armas e habilidades
funcionais. São versões simplificadas para validar o loop, não a realização final
de cada efeito conceitual do GDD. Exemplos: Neutralization é uma ação de área;
Antigen Sample usa revelação temporária; as colônias iniciais aparecem em posições
fixas na Identification e Colony Seed reforça núcleos vivos/biofilme. Ainda não há
plantio livre, projéteis aderentes simulados, nódulos individuais destrutíveis de
Mature Biofilm nem animações finais de habilidades.

Killer T tem rajadas de três disparos; B Cell exige cliques individuais e recebe
bônus contra núcleos; macrófago usa sete pellets e coleta antígeno mais rápido.
As demais armas usam hitscan para o protótipo. Não há dano aliado. Headshots
multiplicam o dano sem transformar todo disparo em eliminação instantânea.

Há quatro eventos: coagulação bloqueia uma rota com collider real após aviso,
fluxo empurra ambos os times nas laterais, inflamação reduz movimento no centro,
febre suspende regeneração. Plaquetas são figuras passivas ligadas à reparação;
os bots de treino são combatentes das vagas do 3v3, não esses NPCs.

Arquitetura de tecido, cargas de oxigênio, rotas, silhuetas dos combatentes e
arma em primeira pessoa são blockout de geometria. O tecido infectado é atualmente
um estado de objetivo; não há célula do tecido individual infectável. Os PNGs
oficiais são usados como retratos; não são modelos 3D. A pasta de referências
locais mencionada não estava presente no workspace durante esta implementação.

## Evidências de validação

- Testes de regras: contestação, duas entradas, reconhecimento, limites por
  equipe, desbloqueio por tecido, cooldown imune compartilhado, vitória por
  maturidade ou destruição dos núcleos, independência entre stress e vitória.
- Física real PyBullet: tiro e cobertura, coleta bloqueada por parede, pulo e
  aterrissagem, recarga, morte e respawn.
- Transporte com sockets reais: cabeçalhos/corpos fragmentados, frames agregados
  e desconexão sem alteração de IDs.
- Um host e cinco processos clientes: seis vagas, comandos, movimento replicado,
  três fases, coleta de antígeno, morte/respawn e evento. O teste acelera tempo de
  simulação e prepara estados de objetivos; não é um playtest de balanceamento.
- GPU/Raylib: menu, lobby, seleção, arena, respawn, fases, resultado e retorno ao
  menu. Confere remoção de câmeras e do mundo físico ao sair da partida.

Reprodução pelos três comandos de teste do README. Capturas e relatórios locais
ficam em `.scratch/`, fora do controle de versão. Os números de balanceamento
continuam provisórios e exigem playtests humanos.
