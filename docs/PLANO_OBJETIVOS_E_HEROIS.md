# Plano de implementação — objetivos, colônias e heróis

## Status e escopo

Plano registrado em 15/09/2026 a partir das decisões da entrevista de design.
Este documento não representa funcionalidades já implementadas. A solicitação
desta etapa é registrar o plano, sem modificar o código do jogo.

Complemento de design aprovado em 16/09/2026: [plano do mapa e planta
esquemática](PLANO_MAPA.md), com bairro de canais e pontes para 3v3, entregas
de oxigênio em edifícios diferentes, rotas alternativas e fuga das hemácias.
Esse complemento também é planejamento, sem implementação nesta etapa.

O redesenho substitui as fases e vitórias baseadas em cronômetro por escolta,
economia, construção e combate. Não existe um conceito de região contaminável:
a infecção é representada exclusivamente pelas colônias construídas pelos jogadores.

## 1. Fluxo e condições de vitória

### Abertura e escolta

- Plaquetas avançam automaticamente até a ferida, sem exigir escolta próxima
  para se movimentar.
- Bactérias vivas em uma faixa curta à frente delas, na mesma passagem, bloqueiam
  o avanço. Bactérias em telhados ou atrás de paredes não bloqueiam por proximidade.
- Ao morrer ou sair do caminho, a bactéria deixa de bloquear as plaquetas.
- Não existe incapacitação ou reanimação das plaquetas.
- Colônias e áreas de habilidades não bloqueiam a escolta por si mesmas.
- A interface mostra a área e a causa do bloqueio.
- O caminho conquistado permanece; fechar a ferida é irreversível.

### Atividades simultâneas

Desde o início, bactérias podem bloquear a escolta, atacar hemácias, coletar
recursos, construir colônias e desenvolvê-las. Células podem proteger hemácias,
liberar o caminho das plaquetas e atacar colônias.

O fechamento da ferida corta o renascimento bacteriano pela entrada. A partida
continua no mesmo mapa, sem transição obrigatória entre três fases rígidas.

### Vitória das células

As células vencem quando a ferida está fechada e não existem colônias nem
bactérias vivas.

**Interpretação registrada no plano:** a retirada da eliminação total refere-se
à eliminação definitiva de jogadores durante uma partida ainda recuperável.
A derrota coletiva acima permanece: sem bactérias vivas e sem colônias, não há
quem possa construir um ponto de retorno.

### Vitória das bactérias

- Cada colônia contribui para um total coletivo de infecção.
- Construir concede uma contribuição inicial; entregar recursos na colônia
  aumenta sua contribuição até um limite.
- Destruir uma colônia remove toda a contribuição dela.
- Alcançar a meta coletiva de infecção encerra a partida com vitória bacteriana,
  inclusive antes de fechar a ferida.
- Não há crescimento passivo da infecção nem vitória por esperar um cronômetro.

A meta deve exigir várias colônias desenvolvidas. O valor exato será ajustado
em partidas de teste; não está fixado que sejam necessárias nove colônias nem
que três colônias desenvolvidas necessariamente bastem.

## 2. Hemácias, recursos e construção

### Economia

- Hemácias percorrem rotas visíveis e podem receber dano bacteriano.
- Ao morrer, deixam recursos que bactérias recolhem fisicamente.
- Células podem destruir recursos deixados no chão.
- Recursos carregados caem quando o jogador morre.
- A economia é individual: quem coleta decide onde gastar.
- Os recursos financiam construção e desenvolvimento de colônias.

### Construção

- Todas as bactérias podem construir por uma ação comum, separada de seus kits.
- Cada jogador bacteriano pode manter até três colônias simultâneas.
- As colônias servem como pontos de renascimento compartilhados pelo time.
- Trocar de herói preserva recursos e colônias, sem reiniciar o limite.
- Mostrar prévia da posição, custo, validade e motivo de impedimento.
- Exigir chão acessível, espaço livre e posição fora da base das células.
- Construir exige permanecer próximo durante uma ação curta.
- Receber dano interrompe a construção; cobrar recursos somente na conclusão.
- A colônia concluída nasce com vida completa.
- Construções incompletas não permitem renascer nem fortalecem outras colônias.

## 3. Colônias, resistência e reconhecimento do mapa

- Substituir os dois núcleos fixos por colônias posicionadas pelos jogadores.
- Cada colônia concluída concede redução de dano às demais, até um teto.
- Destruir uma colônia reduz imediatamente a proteção das sobreviventes.
- Alterar a proteção não cura nem modifica a vida já perdida.
- Não conceder invulnerabilidade por quantidade de colônias.
- Mostrar vida, desenvolvimento e proteção coletiva com sinais visuais claros.
- Colônias próximas devem ser perceptíveis por sinais visuais e sonoros.
- Depois do fechamento da ferida, células podem realizar uma ação de
  reconhecimento disputável em um ponto do mapa para revelar temporariamente
  as colônias restantes.

O reconhecimento do mapa é distinto da coleta de antígenos: antígenos não precisam
ser entregues nesse ponto nem em qualquer outro local.

### Investigar o dano aos núcleos atuais

A inspeção inicial encontrou um caminho de dano implementado, incluindo tiros
das células e modificadores do B-Cell. Os núcleos ficam desativados na fase inicial.
A causa do relato de núcleos que não recebem dano ainda não foi reproduzida.

Antes de substituir essas estruturas, reproduzir o problema e verificar colisão,
identificação do alvo, ativação e comunicação em rede. Usar a conclusão para
evitar transportar o defeito para as colônias novas.

## 4. Respawn e modo espectador

Não há eliminação individual definitiva enquanto a partida continuar.

| Situação | Comportamento |
| --- | --- |
| Durante a contagem de respawn | Acompanhar quem matou o jogador. |
| Contagem encerrada e ferida aberta | Bactéria pode retornar pela entrada. |
| Contagem encerrada e colônia disponível | Bactéria pode renascer em uma colônia válida. |
| Contagem encerrada, sem entrada nem colônia | Acompanhar um aliado vivo aleatório e aguardar construção. |
| Nova colônia concluída | Jogadores aguardando voltam a poder renascer. |
| Tab enquanto acompanha aliados | Alternar entre os aliados vivos. |

- Permitir escolher uma colônia disponível para renascer.
- Revalidar a estrutura no instante do retorno. Se a escolhida foi destruída,
  procurar outra concluída; sem alternativa, continuar aguardando.
- Uma bactéria sobrevivente pode construir uma colônia e resgatar os aliados.
- Preservar o renascimento das células em sua base.
- Tratar câmera quando o assassino morre ou desconecta, morte sem assassino
  válido, ausência de aliados observáveis e encerramento da partida.
- Acompanhar a posição atual do assassino; não implementar uma reprodução
  gravada da morte neste escopo.

## 5. Reconhecimento da infecção e desbloqueios

- Neutrófilo e Macrófago começam disponíveis.
- Bactérias derrotadas deixam amostras de antígeno, separadas dos recursos
  produzidos pelas hemácias.
- Coletar uma amostra aumenta imediatamente o reconhecimento compartilhado.
- Não existe ponto de entrega nem transporte obrigatório de antígenos.
- Macrófago recebe mais reconhecimento por amostra; qualquer célula consegue
  fazer o time progredir.
- A primeira meta libera B-Cell; uma meta adicional libera Killer T.
- Os desbloqueios permanecem até o fim da partida.
- A HUD mostra requisitos, progresso e anúncio de liberação.

Como licença de lore, a primeira etapa representa identificar o invasor e
mobilizar a resposta específica; a segunda representa mobilizar reforços contra
a infecção estabelecida. Não depende de regiões ou de contaminação territorial.

## 6. Kits dos heróis

Preservar uma identidade reconhecível por herói e implementar a resposta visual
e sonora junto do comportamento de cada habilidade.

| Herói | Botão direito | Q | Especial |
| --- | --- | --- | --- |
| Neutrófilo | Golpe de faca | Avanço com corte | Marca inimigos próximos e acelera aliados na perseguição |
| Macrófago | Machado em arco | Golpe no chão que empurra inimigos | Proteção temporária para si e aliados próximos |
| B-Cell | Segurar para zoom com mira | Disparo que marca e enfraquece a proteção do alvo | Tiro carregado de anticorpos que atravessa inimigos |
| Killer T | Golpe forte contra alvo próximo | Salto com impacto na aterrissagem | Sequência de ataques corpo a corpo fortalecidos |
| Pneumococcus | Investida com empurrão | Cápsula que absorve dano | Nuvem que prejudica a visão inimiga e causa dano |
| Staphylococcus | Projétil aderente que desacelera | Repara uma colônia próxima, sem ultrapassar sua vida máxima | Fortifica temporariamente colônias próximas |
| Pseudomonas | Projétil de ácido com explosão | Biofilme que acelera aliados e desacelera inimigos | Expande o biofilme e torna a área corrosiva |
| Streptococcus | Ataque curto eficaz contra hemácias | Arrancada, utilizável também no ar | Aumenta temporariamente mobilidade e velocidade de ataque |

### Especiais e remoção de Systemic Stress

- Especiais têm carga individual por participação em combate e objetivos,
  incluindo proteção, coleta e escolta.
- Não gerar carga apenas pela passagem do tempo ou por atacar estruturas aliadas.
- Remover a recarga compartilhada das respostas imunes.
- Remover Systemic Stress, seu medidor, regras e eventos automáticos de
  coagulação, fluxo sanguíneo, inflamação e febre.
- O fechamento da ferida pelas plaquetas passa a representar a coagulação.

## 7. Feedback audiovisual e interface

### Combate

- Indicar direção do dano recebido.
- Mostrar confirmação de acerto, impacto no alvo, absorção por proteção e destruição.
- Exibir ícones e duração de efeitos ativos, incluindo lentidão e proteção.
- Apresentar preparação dos golpes fortes e trajetórias ou áreas quando aplicável.
- Diferenciar efeitos aliados e inimigos.
- Combinar sinais visuais e sonoros para que dano e habilidades sejam perceptíveis.
- Garantir que o zoom do B-Cell tenha mira própria e retorne corretamente ao
  sair da mira, morrer ou mudar de estado de controle.

### Objetivos

- Progresso da escolta e causa de bloqueio das plaquetas.
- Recursos pessoais e custo de construção/desenvolvimento.
- Quantidade de colônias do jogador e pontos de renascimento disponíveis.
- Infecção coletiva e meta de vitória.
- Reconhecimento e desbloqueios.
- Estado do respawn, motivo da espera e instrução de Tab no modo espectador.

## 8. Integração técnica

Usar os módulos existentes como pontos de partida, ajustando a separação de
responsabilidades conforme a complexidade real da implementação:

- `UserComponents/cells/rules.py` e `catalog.py`: condições de vitória,
  configuração de economia, progressão e balanceamento.
- `arena.py`, `world.py` e `actors.py`: entidades, construção, dano e ciclo de vida.
- `combat.py` e `player.py`: habilidades, mira, ações de construção e controle.
- `hud.py`, `visuals.py` e `audio.py`: interface e feedback audiovisual.
- `bots.py`: decisões de escolta, economia, construção e ataque.
- `director.py`: retirar as dependências dos eventos de Systemic Stress.
- Componentes de sessão e rede: sincronização, entrada/saída de jogadores e
  resultados, respeitando a arquitetura efetivamente usada pelo projeto.

Sincronizar recursos, colônias, reconhecimento, proteção coletiva, respawn,
espectadores e vitória. Validar ações compartilhadas para impedir gastos,
construções, coletas ou recompensas duplicadas.

## 9. Ordem de implementação e validação

### Etapa 1 — regras e dano às estruturas

Reproduzir o problema dos núcleos; substituir as regras temporizadas; estabelecer
os estados da escolta, infecção e vitória e os parâmetros configuráveis.

Validar dano com armas e habilidades, remoção da contribuição de uma colônia e
condições de vitória, inclusive eventos próximos de morte e destruição.

### Etapa 2 — economia, escolta e colônias

Implementar hemácias, coleta, recursos, movimento das plaquetas, bloqueio,
construção, desenvolvimento e resistência coletiva.

Validar o limite por jogador, interrupção sem cobrança, posições válidas,
fortalecimento sem cura involuntária e ausência de bloqueios através de paredes.

### Etapa 3 — respawn, espectadores e reconhecimento

Implementar seleção e revalidação de colônia, espera por resgate, câmera do
assassino, troca por Tab, coleta imediata de antígenos e desbloqueios.

Validar o resgate após expirar a contagem, destruição da colônia escolhida,
ausência de alvo de câmera e preservação de colônias ao trocar de personagem.

### Etapa 4 — kits e feedback

Implementar os kits aprovados, zoom do B-Cell, carga individual e feedback;
remover Systemic Stress e os eventos associados.

Validar as interações relevantes de habilidades e inspecionar visualmente mira,
impactos, indicadores, legibilidade de áreas e estados de controle da câmera.

### Etapa 5 — bots, multiplayer e documentação

Atualizar bots para completar o ciclo inteiro. Validar partidas com bots e com
host/clientes, incluindo coletas concorrentes, construção, destruição e retorno
de jogadores aguardando colônia.

Atualizar README, instruções de jogo e documentação de implementação para
refletir o comportamento entregue. Remover orientações obsoletas de fases,
cronômetros, entrega de antígenos e Systemic Stress onde existirem.

## 10. Balanceamento e critérios de conclusão

Centralizar custos, vida, teto de resistência, contribuição por desenvolvimento,
meta de infecção, metas de reconhecimento, velocidades e durações para ajuste.
Os valores numéricos ainda não foram fechados nesta conversa.

O trabalho estará concluído quando:

- Ambos os times puderem vencer pelas novas condições em partidas completas.
- Objetivos progredirem por ações, sem crescimento passivo da infecção.
- Colônias receberem dano e puderem ser destruídas em multiplayer.
- Bactérias sem ponto de retorno puderem voltar após a construção de uma colônia.
- Escolta, reconhecimento e espectadores seguirem as regras deste documento.
- Os oito kits tiverem seus comportamentos e sinais audiovisuais implementados.
- Não restarem mecânicas ou interface de Systemic Stress no fluxo da partida.
- Bots e jogadores em rede conseguirem participar do ciclo completo.

Observar em testes de partida a duração, frequência de reconstruções, resistência
de redes grandes de colônias, possibilidade de recuperação e períodos sem ação.
Ajustar os valores para reduzir impasses sem tornar a proteção coletiva invulnerável.
