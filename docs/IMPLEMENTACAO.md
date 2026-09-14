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
| `session.py` | Sala, seleção de heróis e transições com RPCs e `NetworkVariable` |
| `actors.py` / `combat.py` | Componentes de combatente, arma, dano, habilidades e respawn |
| `arena.py` | Objetivos vivos, amostras, núcleos e coordenação da simulação |
| `director.py` | Eventos fisiológicos e alteração da passagem central |
| `world.py` / `layout.py` / `navigation.py` | Distrito, colisões e navegação por superfícies em diferentes alturas |
| `scenery.py` / `art.py` | Fachadas e pavimentação em malhas estáticas agrupadas |
| `models.py` / `appearance.py` / `model_lighting.py` | Personagens articulados, aparências e iluminação |
| `visuals.py` | Integração dos modelos com combatentes e efeitos da arena |
| `player.py` | Entrada local e câmera de primeira pessoa |
| `bots.py` | Navegação e decisões dos combatentes opcionais de treino |
| `ui_base.py` / `screens.py` / `hud.py` | Interface sobre `CameraUI` e `RenderableUI` |
| `audio.py` | Feedback local de tiro, acerto, dano e evento |

Todos os módulos de gameplay acima ficam em `UserComponents/cells/`.
Não foi criado um loop de jogo, engine de física ou transporte paralelo.

São reutilizados `Game`, `Item`, `Component`, `Transform`, `Vec3`, `Quaternion`,
`Camera3D`, `CameraUI`, `Renderable3D`, `RenderableUI`, `BulletPhysicsWorld`,
`PhysicsBody3D`, `CharacterController3D`, shapes, raycasts, `overlap_sphere`,
`NetworkManager`, `NetworkComponent`, `Rpc`, `NetworkTransform` e o scheduler da biblioteca. Temporizadores de
gameplay usam `game.delta_time` para permanecer pausáveis e replicáveis.

Embora o guia mencione apenas física 2D, a biblioteca fornecida também inclui
`PhysicsComponents3D`. Ela cuida das colisões, gravidade, pulo e movimento.
Os widgets antigos de `UiComponents/` importam módulos legados ausentes;
a interface utiliza a camada atual `CameraUI`, sem pygame.

## Rede

Cada jogador simula entrada, física, mira, hitscan, munição, recarga, habilidades
e respawn localmente. O jogo usa os RPCs, `NetworkVariable` e `NetworkTransform`
diretamente. Não há canais de comandos, sanitização de inputs remotos,
snapshots periódicos, reconciliação ou código de transporte no gameplay.

- **Movimento:** `NetworkTransform`, UDP a 30 Hz, `owner` do jogador. Sequência,
  descarte de posições antigas, interpolação e reenvio ficam na biblioteca.
  Um datagrama perdido não bloqueia o seguinte.
- **Tiros:** o atirador resolve o raycast e informa o acerto por RPC TCP ao dono
  do alvo. O alvo aplica dano, escudo, neutralização e morte; variáveis nativas
  publicam vida, escudo e placar. Traçantes são RPCs UDP.
- **Habilidades:** ativação e cooldowns locais; RPCs TCP comunicam zonas,
  revelação de inimigos e resposta imune compartilhada.
- **Objetivos:** o anfitrião envia incrementos do relógio e presença nos pontos
  aproximadamente a 10 Hz. Todos executam as mesmas regras de objetivos e eventos.
  Esses RPCs usam TCP porque cada incremento contribui para o progresso; não são
  estados substituíveis por versões mais novas. Movimento e disparos locais
  continuam mesmo quando esses eventos atrasam.
- **Sala:** uma variável nativa guarda as vagas; RPCs cuidam de entrada, seleção
  e transições. A partida começa quando todos montaram a arena. Apenas o relatório
  final contém os dados consolidados de objetivos e placar.
- **Desconexão:** o callback da biblioteca libera a vaga no lobby ou passa o
  combatente para um bot do anfitrião. O jogo não inspeciona sockets ou transportes.

TCP e UDP usam a porta 25765 e o mesmo ID de jogador. O UDP registra o ID recebido
no handshake TCP, independentemente da ordem das conexões. A biblioteca responde
a handshakes repetidos e limpa a associação UDP quando o TCP encerra.

Os testes usam um host e cinco clientes em processos separados. Suspendem a
leitura de respostas do host para verificar movimento, tiro, habilidade e recarga
locais; verificam dano entre clientes, respawn, objetivos e transferência para bot.
Testes de transporte invertem a ordem dos handshakes e perdem a primeira confirmação.
A validação usa loopback, sem teste entre computadores físicos ou WAN. Entradas
tardias são recusadas; não há migração de host ou matchmaking.

## Ajustes necessários na biblioteca

- `NetworkTCP.py`: leitura incremental de pacotes fragmentados/agregados; envio de
  cada frame TCP em uma chamada; desconexão sem renumerar IDs; encerramento de
  sockets; timeout; `TCP_NODELAY`; limite de tamanho de pacote. Desserialização
  aceita dados primitivos, mas rejeita instâncias executáveis via pickle.
  RPCs/NetworkVariables que enviem instâncias Python precisam convertê-las em
  dados primitivos; os RPCs e variáveis deste jogo usam esses tipos.
- `NetworkManager`: flags de conexão inicializadas antes das threads; quando a
  porta solicitada é zero, TCP e UDP compartilham a mesma porta atribuída. A opção
  `enable_udp` continua disponível, mas o jogo utiliza ambos os protocolos.
  Expõe erros e callbacks de desconexão, e associa UDP à identidade TCP.
- `Rpc`: `SendTo.SERVER` executa também quando quem chama é o próprio host.
  `Protocol` é exportado por `NetworkComponents`, como no exemplo do guia.
- `NetworkTransform`: interpolação opcional (desativada por padrão), correção
  imediata de teleporte, reenvio periódico de estado estacionário para recuperar
  datagramas perdidos, rejeição de pacotes antigos/tamanho inválido e cancelamento
  da coroutine ao destruir o componente. A coroutine acompanha trocas de dono
  para permitir que o host assuma um combatente desconectado.
- `NetworkUDP`: a thread de handshake é a única leitora até obter o ID; tentativas
  limitadas com timeout; encerramento tolerante a desconexão. Usa a mesma leitura
  restrita a dados primitivos do transporte TCP.
- `Camera3D`: limpa a câmera principal ao destruir a cena e tolera destruição
  de renderizável que ainda não recebeu `init()`.
- `Game`: limpa callbacks pendentes de objetos destruídos, preservando o `init()`
  dos itens persistentes e seus filhos; encerramento
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

Arquitetura e personagens foram refeitos a partir dos renderizadores procedurais
de Cellular-Odyssey-2. O distrito tem 96 × 120 unidades, rampas, galerias, telhados,
torres e atalhos por mobilidade; veja `MAPA_ABRASION.md`. Os oito modelos têm
silhuetas e equipamentos próprios, baseados nas imagens oficiais arquivadas.
Os PNGs são retratos e referências; os modelos 3D são geometria articulada em código.
A arma em primeira pessoa continua sendo uma silhueta 2D. O tecido infectado é
um estado de objetivo; não há célula do tecido individual infectável.

## Evidências de validação

- Testes de regras: contestação, duas entradas, reconhecimento, limites por
  equipe, desbloqueio por tecido, cooldown imune compartilhado, vitória por
  maturidade ou destruição dos núcleos, independência entre stress e vitória.
- Física real PyBullet: tiro e cobertura, coleta bloqueada por parede, pulo e
  aterrissagem, recarga, morte e respawn.
- Transporte com sockets reais: cabeçalhos/corpos fragmentados, frames agregados
  e desconexão sem alteração de IDs.
- Um host e cinco processos clientes: seis vagas, comandos via RPC, movimento por
  `NetworkTransform` UDP, três fases, coleta de antígeno, morte/respawn e evento.
  O teste verifica que o estado enviado via TCP não transporta posições e que cada
  cliente recebe o `NetworkTransform` do servidor. O teste acelera tempo de
  simulação e prepara estados de objetivos; não é um playtest de balanceamento.
- Regressões das APIs de rede: propriedade de RPC, execução pelo host, inicialização
  persistente, interpolação/teleporte, ordem de datagramas, reenvio de posição
  estacionária após perda de pacote e recusa de transform enviado por cliente.
- GPU/Raylib: menu, lobby, seleção, arena, respawn, fases, resultado e retorno ao
  menu. Confere remoção de câmeras e do mundo físico ao sair da partida.

Reprodução pelos três comandos de teste do README. Capturas e relatórios locais
ficam em `.scratch/`, fora do controle de versão. Os números de balanceamento
continuam provisórios e exigem playtests humanos.
