# Cells at Work — Abrasion

Protótipo FPS 3v3 em **Python 3.14**, usando a EasyCells3D deste repositório.
Inclui multiplayer em rede local, oito heróis com kits de protótipo, Abrasion em
três fases, respawn com troca de personagem e quatro eventos fisiológicos.

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

Para iniciar diretamente pela linha de comando:

```powershell
# Anfitrião
.venv\Scripts\python.exe main.py --host --name "Neutrophil"

# Cada um dos outros cinco jogadores, usando o IPv4 do anfitrião
.venv\Scripts\python.exe main.py --join 192.168.1.100 --name "Macrophage"

# Partida imediata com cinco bots
.venv\Scripts\python.exe main.py --training
```

O endereço acima é apenas um exemplo. Consulte `ipconfig` no computador anfitrião.
A sala usa **TCP 25765**; permita o Python na rede privada se o Windows solicitar.
O argumento `--port` permite outra porta, que deve ser a mesma em todos os processos.
A interface gráfica usa a porta padrão.

## Controles

| Entrada | Ação |
| --- | --- |
| WASD / mouse | Movimento / mira |
| Shift / Espaço | Correr / pular |
| Botão esquerdo | Arma principal; B Cell dispara a cada clique |
| Botão direito | Ataque secundário do kit |
| R | Recarregar |
| Q | Habilidade |
| E | Coletar amostras de antígeno |
| F | Resposta imune compartilhada ou especial bacteriano |
| Esc | Abrir menu; a partida em rede continua |

Após morrer, clique em um herói disponível durante os seis segundos de respawn.
O servidor valida o desbloqueio e as vagas simultâneas, inclusive entre clientes.

## Objetivos

1. **Breach:** bactérias precisam contaminar duas das três entradas. Células
   contestam e recuperam pontos incompletos; defender até o fim do tempo vence.
2. **Identification:** os dois focos internos aparecem. Células podem destruí-los
   ou coletar restos de invasores com E. Macrófago recebe 25 pontos por amostra;
   outras células recebem 8. Aos 50 pontos, B Cell fica disponível no respawn.
3. **Colonization:** tecido infectado libera Killer T. Núcleos vivos aumentam a
   maturidade da infecção. Destruir ambos ou impedir a consolidação até o fim do
   tempo vence para as células; maturidade de 100% vence para as bactérias.

**Systemic Stress nunca determina vitória.** Controla frequência de coagulação,
fluxo sanguíneo, inflamação e febre, com aviso de quatro segundos. Respostas imunes
consomem um cooldown compartilhado de 45 segundos e adicionam stress.

## Preparar outro computador com Python 3.14

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Neste ambiente foi instalado `pybullet 3.2.7` de um wheel CPython 3.14 disponível
no cache local. Em outro computador, o pip pode precisar compilar o PyBullet com
ferramentas C++; não troque a versão do Python para contornar isso sem avaliar o
ambiente. Raylib e NumPy foram instalados em versões compatíveis com Python 3.14.

## Estrutura e validação

As cenas `menu`, `lobby`, `selection`, `abrasion` e `results` ficam em `Levels/`.
Cada cena monta objetos e componentes; regras, física, combate, rede, interface e
fábricas ficam em `UserComponents/cells/`, seguindo `GUIA_DESENVOLVIMENTO.md`.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts/check_multiplayer.py
.venv\Scripts\python.exe scripts/check_scenes.py
```

O segundo comando abre um host e cinco clientes em processos independentes,
sem janela. O terceiro usa uma janela oculta e salva capturas em `.scratch/scenes/`.
Veja [detalhes da implementação](docs/IMPLEMENTACAO.md) e o
[GDD original](docs/GDD_Cells_at_Work_Hero_Shooter_Prototype.html).

O visual 3D é um blockout estilizado, com personagens de geometria simples.
Os retratos transparentes originais do [site oficial](https://cellsatwork-anime.com/character/)
estão em `Assets/characters/`, com créditos em `SOURCES.md`. Os sons curtos são
procedurais e podem ser regenerados com `python scripts/build_audio.py`.
