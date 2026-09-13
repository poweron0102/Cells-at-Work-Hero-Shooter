# Especificação da HUD — Cells at Work | Abrasion

## 1. Objetivo

A HUD deve ser **moderna, limpa, compacta e muito fácil de ler durante a ação**. A principal referência de organização visual é a HUD de **Overwatch**, especialmente pelo uso de módulos pequenos, sólidos, bem alinhados e com hierarquia clara.

O objetivo é reduzir ao máximo a quantidade de tela ocupada pela interface e manter o centro livre para o gameplay.

A HUD deve permitir identificar rapidamente:

- vida atual e máxima;
- personagem atual;
- habilidades e seus cooldowns;
- munição;
- objetivo atual;
- progresso dos objetivos;
- minimapa;
- Systemic Stress.

---

## 2. Direção visual

### 2.1 Estilo geral

A HUD deve ter uma aparência de **hero shooter moderno**, com inspiração em Overwatch, porém mantendo identidade própria relacionada ao tema biológico/imunológico do jogo.

Características desejadas:

- visual limpo e funcional;
- módulos compactos;
- formas geométricas simples;
- cantos levemente chanfrados;
- poucos efeitos decorativos;
- leitura imediata;
- ícones fortes e simples;
- uso de áreas sólidas em vez de painéis translúcidos;
- pouca ou nenhuma transparência;
- sem efeitos exagerados de glow, glassmorphism ou blur;
- todos os módulos devem parecer parte do mesmo sistema visual.

A interface não deve parecer holográfica ou excessivamente futurista. O resultado desejado é algo mais próximo de uma interface competitiva, limpa e legível.

### 2.2 Paleta

A paleta principal deve seguir a linguagem visual das referências atuais:

- **branco / cinza muito claro:** superfícies principais;
- **azul-marinho / grafite:** áreas secundárias e textos de alto contraste;
- **amarelo:** objetivos, progresso e informações de atenção;
- **ciano / turquesa:** vida, habilidade pronta e elementos ligados às células;
- **vermelho:** apenas estados negativos ou críticos.

As cores devem ter função informativa. Não usar muitas cores diferentes sem necessidade.

---

## 3. Organização geral

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ OBJETIVO / PARTIDA                                        MINIMAPA           │
│                                                        SYSTEMIC STRESS       │
│                                                                              │
│                                                                              │
│                               MIRA                                           │
│                                                                              │
│                                                                              │
│                                                                              │
│ PERSONAGEM / HP                                      MUNIÇÃO                 │
│                                                    HABILIDADES                │
└──────────────────────────────────────────────────────────────────────────────┘
```

O centro da tela deve permanecer livre, com exceção da mira e de informações contextuais temporárias.

---

# 4. Personagem e HP — canto inferior esquerdo

O módulo de vida deve ser compacto e funcionar como referência de tamanho para os demais painéis pequenos da HUD.

## Conteúdo

- retrato do personagem;
- nome;
- HP atual;
- HP máximo;
- barra de vida.

Exemplo conceitual:

```text
[ROSTO]  280 / 280 HP
         ████████████
         Macrophage
```

## Retrato

O retrato deve utilizar o **rosto do personagem**, não apenas um ícone abstrato.

Quando houver mais de uma expressão disponível, ela pode mudar durante a partida conforme o estado do personagem.

Exemplos:

- normal → expressão focada;
- vida baixa → cansado ou ferido;
- recebendo dano → reação de impacto;
- habilidade especial → expressão determinada;
- objetivo concluído → expressão confiante.

As mudanças devem ser sutis e não prejudicar a leitura.

## Tamanho

O módulo deve permanecer **pequeno e discreto**.

O painel de objetivo no canto superior esquerdo deve ter aproximadamente o **mesmo comprimento horizontal** deste módulo, para criar consistência visual entre os cantos da interface.

---

# 5. Objetivo da partida — canto superior esquerdo

O painel de objetivo deve ocupar o canto superior esquerdo e ser **compacto**, com dimensões semelhantes às do painel de HP.

Ele substitui completamente informações permanentes sem utilidade direta, como:

```text
ABRASION
IMMUNE DEFENSE
```

## Estrutura

O título e o progresso do objetivo devem formar **um único módulo acoplado**, sem separação visual entre painéis independentes.

Todos os blocos que formam esse módulo devem possuir o **mesmo comprimento horizontal**.

Exemplo:

```text
┌──────────────────────────────┐
│ 02 | IDENTIFICATION    01:57 │
│ Collect antigens / destroy   │
├──────────────────────────────┤
│ A ●      B ●      C ○        │
│ SECURED  SECURED   0%        │
├──────────────────────────────┤
│ Nuclei 2/2 | Colonization 0% │
└──────────────────────────────┘
```

## Conteúdo

- estágio atual;
- nome do objetivo;
- cronômetro;
- descrição curta;
- pontos A/B/C;
- núcleos;
- colonização.

## Tamanho

Este painel não deve se aproximar das dimensões dos protótipos iniciais.

A referência é: **largura próxima à do painel de HP**, preservando o máximo possível da visão do cenário.

---

# 6. Minimapa — canto superior direito

O minimapa permanece no canto superior direito.

## Visual

- mapa simplificado;
- fundo sólido escuro;
- jogador claramente destacado;
- aliados, inimigos e objetivos diferenciados de maneira simples;
- bordas discretas;
- pouca informação textual.

Informações como nome do distrito, orientação ou altitude só devem permanecer se forem relevantes ao gameplay.

---

# 7. Systemic Stress

O Systemic Stress deve ficar **diretamente acoplado abaixo do minimapa**.

Os dois devem possuir exatamente a mesma largura e parecer um único conjunto.

```text
┌──────────────────────┐
│       MINIMAPA       │
│                      │
├──────────────────────┤
│ Systemic Stress  46% │
│ ███████░░░░░░░░░░   │
└──────────────────────┘
```

## Comportamento

### Normal

- amarelo ou ciano discreto;
- sem animação agressiva.

### Elevado

- maior destaque na barra;
- leve mudança de cor.

### Crítico

- vermelho;
- pequeno pulso ou aviso visual;
- alerta sonoro opcional.

Evitar flashes ou efeitos excessivos.

---

# 8. Munição — canto inferior direito

A munição deve ser o módulo principal do canto inferior direito.

Logo abaixo dele ficam as habilidades, formando um único conjunto vertical.

## Estrutura

```text
┌──────────────────┐
│ ▮▮▮   08 / 08   R │
├──────────────────┤
│   Q       |   F   │
│ Skill 1   | Skill2│
└──────────────────┘
```

## Regras

- munição atual em destaque;
- munição máxima com menor peso visual;
- ícone de munição alinhado verticalmente com os números;
- botão `R` integrado ao mesmo bloco da munição;
- não criar uma linha grande separada apenas para `Reload`;
- o texto de recarga deve ocupar o mínimo possível.

### Alinhamento

O ícone de munição deve ficar **centralizado verticalmente** em relação ao conjunto numérico ao lado.

Ele não deve parecer mais alto do que `08 / 08`.

### Espaço

Se necessário para deixar o painel mais estreito, o contador pode ser reorganizado verticalmente.

Exemplo alternativo:

```text
▮▮▮   08
      08
      R
```

Essa solução deve ser usada apenas se melhorar o encaixe com o módulo das habilidades.

---

# 9. Habilidades — abaixo da munição

As habilidades devem ficar **abaixo do painel de munição**, e não ao lado dele.

O painel de munição e o painel de habilidades devem estar **acoplados**, compartilhando exatamente a mesma largura.

Isso cria um bloco único no canto inferior direito.

## Estrutura

```text
┌──────────────────────┐
│ ▮▮▮   08 / 08   [R] │
├──────────┬───────────┤
│    Q     │     F     │
│  [ICON]  │   [ICON]  │
│ Antigen  │ Hyperact. │
│  READY   │   READY   │
└──────────┴───────────┘
```

## Conteúdo de cada habilidade

- tecla;
- ícone;
- nome curto;
- estado atual;
- feedback de cooldown.

## Cooldown

O cooldown deve ser mostrado principalmente no próprio ícone.

Possibilidades:

- preenchimento radial;
- máscara circular;
- pequeno contador numérico;
- mudança de contraste;
- barra curta ou anel fino.

Evitar glow excessivo.

Quando pronta, a habilidade pode receber um pequeno destaque em ciano e o texto `READY`.

---

# 10. Mira

A mira deve ser simples, pequena e limpa.

Sugestão:

- quatro pequenos segmentos;
- ponto central;
- feedback discreto ao acertar um alvo;
- mudança sutil para interação ou alvo válido.

Ela não precisa repetir a estética dos grandes módulos da HUD.

---

# 11. Tags de aliados e inimigos

As informações sobre personagens no mundo devem ser discretas.

Exemplo:

```text
BOT 2   360 HP
```

Evitar grandes caixas ou marcadores muito chamativos.

Mostrar apenas o necessário:

- nome;
- HP quando relevante;
- status importante;
- indicador de time ou objetivo.

---

# 12. Informações contextuais

Controles não devem ficar permanentemente na tela.

Evitar:

```text
WASD mover
SHIFT correr
ESPAÇO salto
E coletar
RMB secundário
ESC menu
```

Mostrar apenas quando necessário.

Exemplos:

```text
[E] Collect Antigen
```

```text
[E] Interact
```

```text
SHIFT — Sprint
```

Depois que o jogador entende a ação, o aviso desaparece.

---

# 13. HUD dinâmica

A interface deve reagir ao estado da partida sem se tornar visualmente exagerada.

## Vida baixa

- retrato muda de expressão;
- barra de HP muda de cor;
- aviso discreto.

## Habilidade em cooldown

- ícone perde contraste;
- preenchimento radial ou contador indica o tempo restante.

## Habilidade pronta

- pequeno destaque em ciano;
- `READY` pode aparecer abaixo.

## Colonização aumentando

- indicador recebe destaque temporário.

## Systemic Stress crítico

- barra muda para vermelho;
- pequeno efeito pulsante.

A HUD deve parecer responsiva, mas nunca cheia de partículas ou efeitos luminosos desnecessários.

---

# 14. Hierarquia visual

## Prioridade máxima

1. mira;
2. HP;
3. munição;
4. habilidades e cooldowns;
5. ameaça imediata.

## Prioridade média

- objetivo;
- cronômetro;
- minimapa;
- Systemic Stress;
- progresso A/B/C.

## Prioridade baixa

- nome do mapa;
- nome do modo;
- controles já aprendidos;
- informações sem impacto imediato.

---

# 15. Uso do espaço

A HUD deve utilizar principalmente os quatro cantos da tela.

Regras:

- manter o centro livre;
- evitar grandes retângulos;
- não usar transparência como elemento visual principal;
- preferir fundos sólidos claros ou escuros;
- evitar blur e glassmorphism;
- agrupar informações relacionadas;
- usar módulos acoplados sempre que fizer sentido;
- manter padding pequeno;
- utilizar dimensões consistentes entre componentes.

---

# 16. Padronização dos módulos

Os módulos devem seguir a mesma linguagem visual.

## Formas

- cantos chanfrados discretos;
- bordas finas;
- base retangular;
- divisões internas claras;
- sem ornamentos excessivos.

## Espaçamento

Usar grid baseado em `8 px`.

Sugestão:

- gap pequeno: `4–8 px`;
- padding interno: `8–12 px`;
- gap entre elementos relacionados: `8 px`;
- margem externa dos cantos da tela consistente.

## Tipografia

Poucos níveis tipográficos.

```text
Número principal       28–36 px
Título                 16–20 px
Texto normal           13–16 px
Texto secundário       10–12 px
```

Números importantes podem usar peso forte.

Textos explicativos devem ser pequenos e curtos.

---

# 17. Layout final desejado

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ┌───────────────────────┐                               ┌─────────────────┐ │
│ │ 02 IDENTIFICATION     │                               │     MINIMAP     │ │
│ │               01:57   │                               │                 │ │
│ ├───────────────────────┤                               ├─────────────────┤ │
│ │ A●      B●      C○    │                               │ STRESS      46% │ │
│ ├───────────────────────┤                               │ ███████░░░░░░░ │ │
│ │ Nuclei 2/2  Colon. 0% │                               └─────────────────┘ │
│ └───────────────────────┘                                                     │
│                                                                              │
│                                                                              │
│                                  +                                           │
│                                                                              │
│                                                                              │
│                                                                              │
│ ┌───────────────────────┐                         ┌────────────────────────┐ │
│ │ [FACE] 280 / 280 HP   │                         │ ▮▮▮   08 / 08     [R] │ │
│ │        ███████████    │                         ├───────────┬────────────┤ │
│ │        Macrophage     │                         │ Q         │ F          │ │
│ └───────────────────────┘                         │ Skill 1   │ Skill 2    │ │
│                                                   └───────────┴────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

# 18. Decisões finais consolidadas

- Visual geral inspirado na organização e clareza de HUDs como Overwatch.
- Interface moderna e clean.
- Evitar transparência, blur, vidro e efeitos luminosos excessivos.
- Fundos sólidos claros e escuros com alto contraste.
- Paleta principal em branco, grafite, amarelo e ciano.
- Centro da tela livre.
- Painel de HP pequeno no canto inferior esquerdo.
- Retrato facial do personagem, podendo mudar de expressão.
- Painel de objetivo no canto superior esquerdo com tamanho semelhante ao de HP.
- Título, progresso A/B/C e estatísticas do objetivo devem ser acoplados e possuir a mesma largura.
- Minimapa no canto superior direito.
- Systemic Stress imediatamente abaixo do minimapa, com a mesma largura.
- Munição no canto inferior direito.
- Habilidades diretamente abaixo da munição.
- Munição e habilidades devem formar um único conjunto acoplado e com a mesma largura.
- O botão `R` deve ficar dentro da área da munição, sem ocupar uma linha grande separada.
- O ícone de munição deve estar centralizado verticalmente em relação ao contador.
- Se necessário, o contador de munição pode ser reorganizado verticalmente para economizar espaço.
- Habilidades devem usar feedback de cooldown no próprio ícone.
- Informações contextuais devem aparecer apenas quando necessárias.
- Todos os módulos devem seguir a mesma geometria, tipografia e sistema de espaçamento.

