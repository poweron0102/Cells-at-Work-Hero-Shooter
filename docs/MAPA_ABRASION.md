# Distrito epitelial de Abrasion

O mapa substitui o bloco de 52 × 62 por um distrito de **96 × 120 unidades**
(3,57 vezes a área). As células nascem em Z=52, as bactérias em Z=-52, com
barreiras que interrompem linhas de tiro e saídas para as três frentes.

As avenidas central e laterais se conectam pela praça dos objetivos e pelas
ruas atrás dos depósitos. É possível contornar os depósitos por fora, passar
sob as galerias ou atravessar seus telhados. A ponte pública liga os dois
depósitos em Z=22. Coagulação fecha só o arco central; outras rotas continuam abertas.

| Camada | Acesso e função |
| --- | --- |
| Rua, 0 m | Objetivos A/B/C, núcleos, cargas de oxigênio e rotas de flanco |
| Depósitos e galerias, 4 m | Quatro rampas para todos os heróis; cobertura nos telhados |
| Torres receptoras, 7 m | Salto de Killer T/Pseudomonas a partir da ponta da galeria; posição elevada com cobertura |
| Passarela interrompida, Z=-22 | Vão de 9 m entre X=-4,5 e X=4,5; corrida + salto de Streptococcus ou combinação com avanço |

Quem erra o salto cai na avenida inferior. Os núcleos permanecem acessíveis por
rotas terrestres: nenhuma composição depende de escolher um herói específico
para cumprir os objetivos. As quatro torres têm o mesmo acesso em ambos os lados.

| Herói | Velocidade base | Altura de salto |
| --- | --- | --- |
| Neutrophil | 6,2 | 2,0 m |
| Macrophage | 5,0 | 1,2 m |
| B Cell | 5,8 | 1,2 m |
| Killer T | 6,0 | 3,6 m |
| Pneumococcus | 5,1 | 1,2 m |
| Staphylococcus | 5,3 | 1,2 m |
| Pseudomonas | 5,8 | 3,6 m |
| Streptococcus | 7,2 | 2,0 m |

Shift multiplica a velocidade por 1,35. Saltos usam a gravidade real de Bullet;
altura e deslocamento são decididos pelo servidor. O avanço preserva a
velocidade vertical. Os valores são balanceamento inicial e precisam de partidas
humanas para avaliar tempos de retorno, domínio das torres e linhas de tiro.

`layout.py` é a fonte das construções e rampas. O cenário agrupa detalhes em
malhas com sombreamento por face; colisões ficam em corpos estáticos simples.
Rampas têm casco convexo contínuo sob os degraus visuais. A navegação mantém
camadas separadas para rua e galeria no mesmo X/Z; bots podem planejar pelas
rampas, mas não planejam combinações de avanço e salto através do vão.

Validação: `tests/test_traversal.py` simula o herói mais lento subindo a rampa,
pulo e pouso no telhado, sucesso/falha no vão e na torre por herói, navegação
até o telhado e rotas de todos os seis spawns até cada objetivo com o portão
aberto e fechado. `scripts/check_art.py` captura todos os oito modelos e três
vistas do distrito; `scripts/check_scenes.py` valida o ciclo das cenas.
