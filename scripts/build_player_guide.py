"""Gera 'Como Jogar.html' com as regras atuais e capturas reais do jogo.

    (capturas da HUD/habilidades em .scratch/hudshots, geradas numa partida de treino)
    .venv\\Scripts\\python.exe scripts\\check_match_views.py
    .venv\\Scripts\\python.exe scripts\\check_art.py
    .venv\\Scripts\\python.exe scripts\\build_player_guide.py
"""
import base64
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from UserComponents.cells.catalog import HEROES, KIT  # noqa: E402

SHOTS = [
    ('.scratch/hudshots/h1_neutrofilo.png', 'HUD: placar e objetivo no topo, vida, especial (F) e habilidades.'),
    ('.scratch/hudshots/h2_kit_f1.png', 'Segure F1 para ver o kit do herói.'),
    ('.scratch/hudshots/h4_mac_banquete_3p.png', 'Macrófago: Banquete em 3ª pessoa, engolindo tiros.'),
    ('.scratch/hudshots/h7_bcell_torreta.png', 'B Cell: torreta Plasmócito marcando inimigos.'),
    ('.scratch/hudshots/h9_bcell_chuva.png', 'B Cell: Chuva de anticorpos, vista aérea.'),
    ('.scratch/hudshots/h11_staph_parede.png', 'Staphylococcus: parede de Coagulase.'),
    ('.scratch/match/avenida.png', 'Avenida arterial: a escolta parte da estação das células.'),
    ('.scratch/match/escolta.png', 'Praça da ponte: plaquetas contornam o chafariz-coração.'),
    ('.scratch/match/canal.png', 'Canal raso: rota inferior com passagem sob as pontes.'),
    ('.scratch/match/obra.png', 'Obra da ferida: destino das plaquetas.'),
    ('.scratch/match/respawn.png', 'Respawn: escolha herói e, como bactéria, entrada ou colônia.'),
    ('.scratch/match/timo_labirinto.png', 'Timo: as plaquetas atravessam o labirinto do exame final.'),
    ('.scratch/match/timo_campo.png', 'Timo: campo de treino com alambrado e a torre de observação.'),
    ('.scratch/match/medula_cidade.png', 'Medula Óssea: eritroblasto no treino de entrega pela cidade de papelão.'),
    ('.scratch/match/medula_choro.png', 'Medula Óssea: atingida, a criança larga a caixa e volta chorando ao berçário.'),
    ('.scratch/match/coracao_valva_fechada.png', 'Coração: o comboio espera a valva tricúspide abrir (ECG à esquerda).'),
    ('.scratch/match/coracao_valva_aberta.png', 'Coração: valva aberta, o comboio entra no túnel de torii.'),
    ('.scratch/match/coracao_endocardite.png', 'Coração: endocardite — a colônia junto à valva a emperra fechada.'),
    ('.scratch/match/coracao_ventriculo.png', 'Coração: salão do ventrículo direito e a valva pulmonar.'),
    ('.scratch/art-upgrade/immune-models.png', 'Células imunes.'),
    ('.scratch/art-upgrade/bacterial-models.png', 'Bactérias.'),
]

SECTIONS = [
    ('Mapas', [
        'O anfitrião escolhe o mapa no lobby, com as setas ao lado do nome.',
        'Bairro Arterial e Timo: escolta das plaquetas até a ferida.',
        'Medula Óssea: proteja o treino de entrega dos eritroblastos. Cada criança que chega a um posto conta '
        'uma formatura; atingida, ela larga a caixa (recurso das bactérias) e volta chorando ao berçário.',
        'Coração: leve o comboio de hemácias até o pulmão. As valvas abrem e fecham no ritmo do batimento '
        '(veja o ECG); o comboio espera a valva abrir. Uma colônia junto a uma valva a emperra fechada até '
        'ser destruída.',
        'Em todos: completar o objetivo sela a entrada das bactérias.',
    ]),
    ('Objetivo das células', [
        'Cumprir o objetivo do mapa: escoltar as plaquetas, formar os eritroblastos ou levar o comboio ao pulmão. A escolta e o comboio só param quando uma bactéria viva está logo à frente, na mesma passagem.',
        'Proteger as hemácias que levam oxigênio aos edifícios A, B e C.',
        'Coletar amostras de antígeno deixadas por bactérias: liberam B Cell e depois Killer T.',
        'Depois de selar a entrada, ocupar o posto de reconhecimento para revelar colônias e destruí-las.',
        'Vitória: entrada selada, nenhuma colônia e nenhuma bactéria viva.',
    ]),
    ('Objetivo das bactérias', [
        'Bloquear a escolta (ou o comboio) ficando à frente dela.',
        'Caçar hemácias (ou eritroblastos, na medula): deixam recursos que você recolhe passando por cima.',
        'No coração, construir uma colônia junto a uma valva a emperra fechada.',
        'Segurar G para construir colônias (até 3 por jogador). O custo só é cobrado no fim; levar dano interrompe.',
        'Tocar G perto de uma colônia para entregar recursos e desenvolvê-la.',
        'Colônias são pontos de renascimento e protegem umas às outras.',
        'Vitória: a infecção coletiva atinge a meta.',
    ]),
    ('Controles', [
        'WASD / mouse: mover e mirar · Shift: correr · Espaço: pular',
        'Botão esquerdo: arma · Botão direito: habilidade secundária (segurar em Engolir/Barreira/Soco/Granada ácida)',
        'Q e E: habilidades · F: especial (carrega lutando e cumprindo objetivos; alguns usam câmera em 3ª pessoa)',
        'V: golpe rápido · R: recarregar · F1 (segurar): cartão do kit',
        'G: segurar para construir colônia, tocar perto de uma colônia para entregar recursos (bactérias)',
        'Torreta e parede: Q mostra a prévia, botão esquerdo fixa, direito ou Q cancela',
        'Tab: alternar aliado no modo espectador · Esc: menu',
    ]),
    ('Mecânicas em comum', [
        'Marca (B Cell): o alvo marcado recebe +15% de dano. Killer T causa +20% em marcados.',
        'Cores fixas: sua equipe é sempre turquesa e a inimiga sempre vermelha; dourado é o especial.',
        'Ícones sobre as cabeças: marcado, preso, perforina, sem cura e especial ativo.',
        'Habilidades de tiro único (Rede NET, Perforina, Toxina, Projétil aderente, Pseudópode, Corrente): '
        'a mira tem uma ajuda: inimigo à vista bem perto do centro da tela é acerto garantido. '
        'Barreiras e membranas no caminho ainda bloqueiam.',
    ]),
]
for _key, _info in KIT.items():
    _hero = HEROES[_key]
    SECTIONS.append((f"{_hero.name.title()} — {_hero.role.lower()}", [
        f"{slot.upper()} · {name}: {desc}" for slot, (name, desc) in
        ((k, _info[k]) for k in ('passive', 'lmb', 'rmb', 'q', 'e', 'f'))
    ] + [f"Dica: {_info['tip']}"]))


def main():
    figures = []
    for path, caption in SHOTS:
        file = ROOT/path
        if not file.exists():
            continue
        data = base64.b64encode(file.read_bytes()).decode()
        figures.append(f'<figure><img src="data:image/png;base64,{data}" alt="{html.escape(caption)}">'
                       f'<figcaption>{html.escape(caption)}</figcaption></figure>')
    names = {'PASSIVE': 'PASSIVA'}
    for _title, items in SECTIONS:
        for i, item in enumerate(items):
            for a, b in names.items():
                if item.startswith(a):
                    items[i] = b+item[len(a):]
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
<header><h1>Cells at Work — Como jogar</h1>
<p>FPS 3v3 em rede local, em quatro mapas: Bairro Arterial, Timo, Medula Óssea e Coração.
Células cumprem o objetivo do mapa e protegem hemácias; bactérias bloqueiam, caçam e espalham colônias. Execute <code>Jogar.bat</code> e escolha
<b>Criar sala</b>, ou entre com o IP do anfitrião. <b>Treino + bots</b> completa as vagas.</p></header>
<main>{sections}</main><div class="gallery">{''.join(figures)}</div></body></html>'''
    (ROOT/'Como Jogar.html').write_text(page, encoding='utf-8')
    print(f'Como Jogar.html: {len(figures)} capturas')


if __name__ == '__main__':
    main()
