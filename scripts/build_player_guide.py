"""Gera 'Como Jogar.html' com as regras atuais e capturas reais do jogo.

    .venv\\Scripts\\python.exe scripts\\check_match_views.py
    .venv\\Scripts\\python.exe scripts\\check_art.py
    .venv\\Scripts\\python.exe scripts\\build_player_guide.py
"""
import base64
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOTS = [
    ('.scratch/match/avenida.png', 'Avenida arterial: a escolta parte da estação das células.'),
    ('.scratch/match/escolta.png', 'Praça da ponte: plaquetas contornam o chafariz-coração.'),
    ('.scratch/match/canal.png', 'Canal raso: rota inferior com passagem sob as pontes.'),
    ('.scratch/match/obra.png', 'Obra da ferida: destino das plaquetas.'),
    ('.scratch/match/respawn.png', 'Respawn: escolha herói e, como bactéria, entrada ou colônia.'),
    ('.scratch/art-upgrade/immune-models.png', 'Células imunes.'),
    ('.scratch/art-upgrade/bacterial-models.png', 'Bactérias.'),
]

SECTIONS = [
    ('Objetivo das células', [
        'Escoltar as plaquetas até a ferida. Elas avançam sozinhas e só param quando uma bactéria viva está logo à frente, na mesma passagem.',
        'Proteger as hemácias que levam oxigênio aos edifícios A, B e C.',
        'Coletar amostras de antígeno deixadas por bactérias: liberam B Cell e depois Killer T.',
        'Depois de fechar a ferida, ocupar o posto da torre treliçada para revelar colônias e destruí-las.',
        'Vitória: ferida fechada, nenhuma colônia e nenhuma bactéria viva.',
    ]),
    ('Objetivo das bactérias', [
        'Bloquear a escolta ficando à frente das plaquetas.',
        'Caçar hemácias: ao morrer, deixam recursos que você recolhe passando por cima.',
        'Segurar G para construir colônias (até 3 por jogador). O custo só é cobrado no fim; levar dano interrompe.',
        'Apertar E perto de uma colônia para entregar recursos e desenvolvê-la.',
        'Colônias são pontos de renascimento e protegem umas às outras.',
        'Vitória: a infecção coletiva atinge a meta.',
    ]),
    ('Controles', [
        'WASD / mouse: mover e mirar · Shift: correr · Espaço: pular',
        'Botão esquerdo: arma · Botão direito: ação secundária (B Cell: zoom)',
        'Q: habilidade · F: especial (carrega lutando e cumprindo objetivos)',
        'G: construir (bactérias) · E: entregar recursos · R: recarregar',
        'Tab: alternar aliado no modo espectador · Esc: menu',
    ]),
]


def main():
    figures = []
    for path, caption in SHOTS:
        file = ROOT/path
        if not file.exists():
            continue
        data = base64.b64encode(file.read_bytes()).decode()
        figures.append(f'<figure><img src="data:image/png;base64,{data}" alt="{html.escape(caption)}">'
                       f'<figcaption>{html.escape(caption)}</figcaption></figure>')
    sections = ''.join(f'<section><h2>{html.escape(t)}</h2><ul>' + ''.join(f'<li>{html.escape(i)}</li>' for i in items)
                       + '</ul></section>' for t, items in SECTIONS)
    page = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Cells at Work — Como jogar</title>
<style>
body{{font-family:Inter,Segoe UI,sans-serif;background:#f6f1e6;color:#1b2b33;margin:0}}
header{{background:#1b2b33;color:#fff;padding:32px 48px}} header p{{color:#cfe0e6;max-width:760px}}
main{{padding:24px 48px;display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}}
section{{background:#fff;border-radius:6px;padding:8px 24px;border-top:5px solid #d85a58}}
li{{margin:8px 0;line-height:1.45}}
.gallery{{padding:0 48px 48px;display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:18px}}
figure{{margin:0;background:#fff;border-radius:6px;overflow:hidden}} img{{width:100%;display:block}}
figcaption{{padding:10px 14px;font-size:14px;color:#4b5d66}}
</style></head><body>
<header><h1>Cells at Work — Bairro Arterial</h1>
<p>FPS 3v3 em rede local. Células escoltam plaquetas até a ferida e protegem hemácias;
bactérias bloqueiam, caçam e espalham colônias. Execute <code>Jogar.bat</code> e escolha
<b>Criar sala</b>, ou entre com o IP do anfitrião. <b>Treino + bots</b> completa as vagas.</p></header>
<main>{sections}</main><div class="gallery">{''.join(figures)}</div></body></html>'''
    (ROOT/'Como Jogar.html').write_text(page, encoding='utf-8')
    print(f'Como Jogar.html: {len(figures)} capturas')


if __name__ == '__main__':
    main()
