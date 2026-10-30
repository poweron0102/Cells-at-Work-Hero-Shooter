# Bairro dos Canais

Mapa original criado no Blender com base em `docs/PLANO_MAPA.md`, na planta conceitual e nas oito imagens de `referencias/`. Nenhum mapa existente do jogo foi consultado ou reutilizado.

Abra **BairroDosCanais.blend**. A cena contém materiais procedurais, iluminação, quatro câmeras e coleções separadas para ruas, pontes, fachadas, avenida arterial, praça, obra e detalhes. As peças são editáveis. As colisões auxiliares ficam ocultas na coleção `08_Colisao`.

## Espaços

- Avenida ocre com três arcos vermelhos e placa suspensa.
- Canal de água jade com três pontes de alvenaria, passagem inferior e quatro rampas de saída.
- Galerias térreas atravessáveis, circuitos laterais e varanda baixa acessível por escadas nas duas extremidades.
- Praça com posto de reconhecimento, bancos, jardineiras e iluminação urbana.
- Estação celular ao sul, com anteparo central e saídas laterais.
- Área de reparo ao norte, com ruptura, andaimes, caixas e barreiras.
- Destinos A, B e C com identificação própria, toldos e acessos pelas duas extremidades das galerias.

## Arquivos

- `BairroDosCanais.blend`: arquivo principal, com o acabamento completo.
- `BairroDosCanais.glb`: exportação auxiliar de geometria e cores-base; os materiais procedurais do Blender não são reproduzidos integralmente no glTF.
- `BairroDosCanais_collision.glb`: superfícies de colisão separadas da decoração.
- `01_Bairro.png`, `02_Canal.png`, `03_Arteria.png`, `04_Planta.png`: vistas renderizadas.
- `marcadores.json`: posições de referência, sem lógica de jogo.

Escala em metros. No Blender, Z aponta para cima, o norte é +Y, a rua fica em Z=0 e o leito do canal em Z=-3. A água tem profundidade visual de aproximadamente 12 cm. O glTF converte os eixos para Y para cima.

Esta entrega é o mapa e seus arquivos de arte. Não altera código, regras, bots ou balanceamento do jogo. A colisão exportada é geometria auxiliar; não foi conectada ao motor do jogo.

Para reconstruir, execute na raiz do projeto:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python scripts\build_bairro_canais.py
```

A reconstrução substitui os arquivos gerados nesta pasta. Preserve uma cópia se editar o `.blend` manualmente.
