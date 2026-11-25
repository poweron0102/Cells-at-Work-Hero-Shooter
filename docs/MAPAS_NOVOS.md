# Mapas novos: Timo, Medula Óssea e Coração

Três mapas construídos do zero no Blender, por script, a partir de quadros do anime
(`D:\Series e Filmes\Cells at Work!`). Os objetivos novos (Medula e Coração) foram alinhados
com o usuário em 25/11/2026; o mapa do deserto da glândula sudorípara foi descartado.

| Mapa | Chave | Episódio | Modo | Layout | Referências |
| --- | --- | --- | --- | --- | --- |
| Timo | `timo` | S01E09 Timócito | `escort` | `referencias/scripts/mapa/timo_layout.py` | `referencias/Timo/` |
| Medula Óssea | `medula` | S01E06 Eritroblastos e Mielócitos | `training` | `referencias/scripts/mapa/medula_layout.py` | `referencias/MedulaOssea/` |
| Coração | `coracao` | S01E08 Circulação Sanguínea | `convoy` | `referencias/scripts/mapa/coracao_layout.py` | `referencias/Coracao/` |

Os três têm 100 × ~155 m (o Bairro Arterial tem 124 × 186 m), a base das células ao sul e a
entrada bacteriana ao norte, sem linha de visão entre as bases, três destinos de hemácias (A, B, C)
com duas portas cada e duas rotas por destino, e de 14 a 16 sugestões de colônia para os bots.

## Escolha do mapa

- `UserComponents/cells/maps.py` lista os mapas (`MAPS`, `ORDER`), o modo de cada um e os textos do
  objetivo por modo (`MODES`). Só aparecem no lobby os mapas exportados (`maps.available()`).
- O anfitrião troca o mapa no lobby (setas ao lado do nome). A chave vai na variável de rede
  `Session.map` (id 103); a escolha fica em `saves/config.json` (`"map"`).
- `layout.select(chave)` carrega o `runtime.json` do mapa antes de montar a arena (`Levels/abrasion.py`,
  `Levels/replay.py`). Quem usa marcadores lê `layout.NOME` na hora do uso.
- O replay grava a chave do mapa no cabeçalho; replays antigos abrem no Bairro Arterial.

## Timo (escolta)

Do sul para o norte: dormitório dos timócitos (base, prédio de sacadas), rua do portão com o portão
de pedra, campo de treino de terra batida (muros de escalada, pneus, rastejo sob arame farpado,
sacos de areia, torre de observação = reconhecimento), o **labirinto do exame final** (muros de
concreto sobre grama, corredor principal de 6 m para a escolta e setores laterais com laços), o
pátio da escola (biblioteca = edifício C, caixa-d'água) e a cápsula do timo rompida (cratera).
A oeste, a trilha da floresta com o refeitório (A) e uma plataforma de observação; a leste, o
ginásio (B) e a arquibancada de concreto voltada para o labirinto. Ao fundo, a montanha listrada.

**Alambrado vazado.** As cercas usam o padrão de shader 18 (`CHAINLINK`): a tela é vazada no
desenho, na sombra e no contorno. A colisão das cercas vai num grupo próprio (`world.SCREEN_GROUP`
= 16, chave `screen_vertices`/`screen_indices` do `runtime.json`): os heróis não atravessam, mas
tiros (máscara 1|8) e linha de visão (máscara 1) passam pela tela. A navegação dos bots e a
checagem das rotas das hemácias levam as cercas em conta.

## Medula Óssea (treino de entrega)

Do sul para o norte: alojamento dos mielócitos (base), gramado com a torre do relógio
(reconhecimento) e o parquinho (casa na árvore com escada e escorregador), o **berçário** a oeste
(de onde saem as crianças), a **cidade de papelão** do treino (piso rosa, quarteirões de divisórias
pintadas com árvores, casinhas e setas, ruas de 5 m, carrinhos de caixas de O₂), a praça norte com o
corredor do vaso sanguíneo (C) e a fratura do osso (entrada bacteriana). A leste, a academia de
tijolos com arcada coberta ao longo do mapa (B); a noroeste, o canal com a ponte de tijolo em arco
e o ateliê (A).

Regras (`npcs.Hemacias` com `kids=True`, `rules.MatchState.graduate`):

- `training_kids` eritroblastos (desenhados a 72% do tamanho) saem um de cada vez do berçário e vão
  aos postos A, B e C pelas ruas, com a mesma percepção e fuga das hemácias.
- Cada entrega é uma formatura (`MatchState.escort` conta formaturas, `escort_total` =
  `training_goal`). Ao bater a meta, `seal()` fecha a entrada bacteriana.
- Com `kid_health` de dano, a criança larga a caixa (recurso de `kid_resource`), passa ao estado
  `cry` (não é alvo) e volta correndo ao berçário pelas ruas; sai de novo após `kid_respawn` s.
- Células a até `kid_protect_radius` m de uma criança em treino carregam o especial.
- HUD: "FORMATURA 3/10", marcadores "socorro!" sobre crianças fugindo (células) e "caixa" (bactérias).

## Coração (comboio + batimento + endocardite)

O caminho do episódio, do sul para o norte: estação da veia cava (base), avenida com a placa do
mapa do coração e o depósito das hemácias, pátio do **átrio direito** com o grande torii e as
lanternas de pedra, o **templo** (o comboio atravessa o salão das lanternas), o paredão de rocha
com a **valva tricúspide** (portão com dois guardiões) e uma fenda estreita, o **túnel de torii**
com tapete vermelho (fora dele, jardim de musgo e pátio de serviço), o salão do **ventrículo
direito** (teto em tenda listrado, lanternas em tambor, mezaninos com escadas), a **valva pulmonar**,
o corredor branco da **artéria pulmonar** ("siga em frente") e a estação de troca do **pulmão**
(galpão de treliças, cilindros de O₂). A lesão do endocárdio (entrada bacteriana) fica a leste do
pulmão. Corredores laterais em x ≈ ±29 contornam as valvas.

Regras (`UserComponents/cells/heart.py`, `Arena.update_valves`):

- Batimento: ciclo de `heart_period` s, começando por `heart_systole` s de sístole. A tricúspide
  (`kind: av`) abre na diástole e fecha na sístole; a pulmonar (`semilunar`) faz o contrário.
  Tudo sai do relógio replicado (`MatchState.elapsed`): cada par calcula as valvas sozinho.
- Valva fechada: corpo estático (bloqueia passagem e tiros); os atores simulados no par que
  estiverem no vão são empurrados para o lado mais próximo. As folhas giram nas dobradiças
  (`visuals.draw_valves`) e soam um baque posicionado; cada sístole toca o `heartbeat.wav`.
- Comboio (`convoy_speed` m/s): espera a `STOP_BEFORE` m de uma valva fechada
  (`MatchState.blocked_valve`) e segura aberta a valva que está atravessando.
- Endocardite: colônia a até `valve_jam_radius` m do centro da valva a emperra fechada
  (`MatchState.jammed`), até ser destruída. Não se constrói no vão da valva. Os bots células
  priorizam essa colônia; há sugestões de colônia ao lado das duas valvas.
- HUD: faixa de ECG (sístole/diástole e segundos até a troca), estado de cada valva, títulos
  "VALVA FECHADA" / "VALVA EMPERRADA", marcadores "valva emperrada" e valvas no minimapa.
- Ao chegar à doca do pulmão: "CIRCULAÇÃO RESTABELECIDA", a lesão é selada.

## Balanceamento

Os números novos ficam em `Assets/balance.json` (`training_*`, `kid_*`, `heart_*`, `convoy_speed`,
`valve_*`). Com bots (2 células ativas contra 3 bactérias), a formatura completa em ~4 min e o
comboio chega ao pulmão em ~4,5 min, no ritmo da escolta do Bairro Arterial e do Timo. Nada disso
foi validado em partidas com pessoas.

## Construir, exportar e conferir

```powershell
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
# Confere o layout sem Blender: marcadores, rotas, navegação, linha de visão e z-fight
.venv\Scripts\python.exe scripts\map_check.py --map coracao
.venv\Scripts\python.exe scripts\plot_map.py --map coracao        # planta em .scratch/maps/
# Monta no Blender, salva referencias/blender/<Pasta>.blend e exporta Assets/Maps/<Pasta>/
& $blender --background --factory-startup --python referencias\scripts\mapa\rebuild_distrito.py -- --map coracao
.venv\Scripts\python.exe referencias\scripts\mapa\build_navmesh.py --map coracao
# Vistas pelo motor do jogo e capturas de uma partida de treino
.venv\Scripts\python.exe scripts\render_district.py --map coracao
.venv\Scripts\python.exe scripts\check_match_views.py --map coracao
.venv\Scripts\python.exe scripts\check_scenes.py --map=coracao
```

`tests/test_maps.py` cobre os três mapas (GLB, marcadores, rotas, navegação, visão entre bases,
z-fight, alambrado), o treino de entrega, o batimento, o comboio, a endocardite e a escolha do
mapa pela sessão.
