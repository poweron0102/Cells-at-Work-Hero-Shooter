"""Kits e parametros de balanceamento.

Os NUMEROS (vida, dano, municao, recargas, regras da partida) ficam em ``Assets/balance.json``;
aqui ficam so a identidade de cada heroi (nome, time, papel, cor, nomes das habilidades) e os textos.
Nenhum valor foi validado em partidas: sao pontos de partida do plano.
Cada heroi tem passiva, LMB (arma), RMB, Q, E e o especial F (ver ``KIT``).
"""
import json
from dataclasses import dataclass, fields
from pathlib import Path

CELLS = "cells"
BACTERIA = "bacteria"

BALANCE_FILE = Path(__file__).resolve().parents[2]/"Assets"/"balance.json"


@dataclass(frozen=True, kw_only=True)
class Hero:
    # Identidade (definida abaixo, em IDENTITY)
    name: str
    team: str
    role: str
    color: tuple
    secondary: str
    ability: str
    ultimate: str
    ability2: str = ""
    passive: str = ""
    # Numeros (Assets/balance.json -> "heroes"); significado em "_leia_me" no proprio JSON
    health: int
    speed: float
    jump_height: float
    damage: float
    interval: float
    magazine: int
    reload: float
    pellets: int
    spread: float
    range: float
    burst: int
    burst_gap: float
    secondary_cd: float
    ability_cd: float
    ability2_cd: float
    ult_time: float
    limit: int


IDENTITY = {
    "neutrophil": dict(name="NEUTROPHIL 1146", team=CELLS, role="COMBATENTE", color=(221, 235, 230),
                       secondary="Faca", ability="Avanco cortante", ultimate="Quimiotaxia",
                       ability2="Rede NET", passive="Receptor"),
    "macrophage": dict(name="MACROPHAGE", team=CELLS, role="TANQUE / ANTIGENOS", color=(234, 190, 196),
                       secondary="Engolir", ability="Pseudopode", ultimate="Banquete",
                       ability2="Machadada", passive="Fagocitose"),
    "b_cell": dict(name="B CELL", team=CELLS, role="PRECISAO / SUPORTE", color=(111, 197, 244),
                   secondary="Mira", ability="Plasmocito", ultimate="Chuva de anticorpos",
                   ability2="Granada de anticorpos", passive="Opsonizacao"),
    "killer_t": dict(name="KILLER T", team=CELLS, role="INVESTIDA", color=(62, 79, 91),
                     secondary="Soco carregado", ability="Salto de impacto", ultimate="Ativacao total",
                     ability2="Perforina", passive="Licenca para matar"),
    "pneumococcus": dict(name="PNEUMOCOCCUS", team=BACTERIA, role="TANQUE FRONTAL", color=(173, 119, 213),
                         secondary="Barreira", ability="Investida", ultimate="Pneumonia",
                         ability2="Capsula compartilhada", passive="Capsula"),
    "staphylococcus": dict(name="STAPHYLOCOCCUS", team=BACTERIA, role="COLONIZACAO", color=(237, 184, 77),
                           secondary="Projetil aderente", ability="Coagulase", ultimate="Abscesso",
                           ability2="Toxina", passive="Cacho"),
    "pseudomonas": dict(name="PSEUDOMONAS", team=BACTERIA, role="CONTROLE DE AREA", color=(99, 195, 150),
                        secondary="Granada acida", ability="Biofilme", ultimate="Quorum sensing",
                        ability2="Flagelo", passive="Corrosao"),
    "streptococcus": dict(name="STREPTOCOCCUS", team=BACTERIA, role="FLANQUEADOR", color=(229, 115, 158),
                          secondary="Golpe", ability="Arrancada", ultimate="Divisao binaria",
                          ability2="Corrente", passive="Hemolise"),
}

_IDENTITY_FIELDS = {"name", "team", "role", "color", "secondary", "ability", "ultimate", "ability2", "passive"}
_STATS = [f.name for f in fields(Hero) if f.name not in _IDENTITY_FIELDS]


def _numbers(section, where):
    """Tira as chaves de comentario (comecam com ``_``) e confere que o resto e numero."""
    out = {}
    for key, value in section.items():
        if key.startswith("_"):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{BALANCE_FILE.name}: {where}.{key} precisa ser um numero (veio {value!r})")
        out[key] = value
    return out


def _load():
    try:
        data = json.loads(BALANCE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{BALANCE_FILE.name} esta com erro de sintaxe na linha {e.lineno}, coluna {e.colno}: {e.msg}") from None
    heroes = {}
    for key, identity in IDENTITY.items():
        if key not in data.get("heroes", {}):
            raise ValueError(f"{BALANCE_FILE.name}: falta o heroi \"{key}\" em \"heroes\"")
        stats = _numbers(data["heroes"][key], f"heroes.{key}")
        missing = [s for s in _STATS if s not in stats]
        unknown = [s for s in stats if s not in _STATS]
        if missing or unknown:
            raise ValueError(f"{BALANCE_FILE.name}: heroes.{key} " +
                             (f"sem {missing} " if missing else "") + (f"com chaves desconhecidas {unknown}" if unknown else ""))
        for whole in ("magazine", "pellets", "burst", "limit"):
            if stats[whole] < 1 or stats[whole] != int(stats[whole]):
                raise ValueError(f"{BALANCE_FILE.name}: heroes.{key}.{whole} precisa ser inteiro >= 1")
            stats[whole] = int(stats[whole])
        heroes[key] = Hero(**identity, **stats)
    unknown = set(data.get("heroes", {})) - set(IDENTITY)
    if unknown:
        raise ValueError(f"{BALANCE_FILE.name}: herois desconhecidos em \"heroes\": {sorted(unknown)}")
    return heroes, _numbers(data.get("balance", {}), "balance")


HEROES, BALANCE = _load()

# Textos do cartao do kit (F1) e das dicas da HUD: (nome, descricao curta).
KIT = {
    "neutrophil": dict(
        passive=("Receptor", "Inimigos abaixo de 50% de vida aparecem atraves das paredes."),
        lmb=("Fuzil", "Rajada automatica precisa."),
        rmb=("Faca", "Golpe corpo a corpo. Dano dobrado pelas costas."),
        q=("Avanco cortante", "Corta quem atravessar. Recarrega na hora ao eliminar."),
        e=("Rede NET", "Prende o alvo no lugar por 1,5 s."),
        f=("Quimiotaxia", "Revela todos os inimigos, acelera a equipe e da 3 avancos seguidos."),
        tip="Persiga alvos marcados pelo B-Cell: recebem +15% de dano."),
    "macrophage": dict(
        passive=("Fagocitose", "Eliminar alguem de perto cura 25% da sua vida."),
        lmb=("Escopeta", "Chumbo de curto alcance."),
        rmb=("Engolir", "Segure: a membrana devora os tiros inimigos a frente (barra de 3 s). Sem atirar."),
        q=("Pseudopode", "Gancho que puxa o inimigo ate voce."),
        e=("Machadada", "Golpe pesado em arco que empurra."),
        f=("Banquete", "6 s: Engolir infinito e duas vezes maior; o que voce engole vira escudo dos aliados. "
                       "F de novo: Cuspir uma onda de dano."),
        tip="Fique na frente: cada tiro engolido carrega o Banquete."),
    "b_cell": dict(
        passive=("Opsonizacao", "Seus acertos marcam o alvo: +15% de dano recebido."),
        lmb=("Rifle", "Tiro preciso de alto dano."),
        rmb=("Mira", "Zoom com dano extra."),
        q=("Plasmocito", "Posicione uma torreta (160 HP, 15 m) que atira e marca. Clique para fixar."),
        e=("Granada de anticorpos", "Explode em area, causa dano e marca todos."),
        f=("Chuva de anticorpos", "Vista aerea: chuva com dano e marca; WASD a move. Voce senta (corpo menor)."),
        tip="Sua marca alimenta a equipe: Killer T ganha +20% contra marcados."),
    "killer_t": dict(
        passive=("Licenca para matar", "+20% de dano contra alvos marcados."),
        lmb=("Rajada", "Tres tiros por gatilho."),
        rmb=("Soco carregado", "Segure para carregar, solte para golpear e arremessar."),
        q=("Salto de impacto", "Salto rapido ate onde a mira tocar (16 m); esmaga ao pousar no circulo."),
        e=("Perforina", "Injeta perforina: o alvo sofre dano extra apos 3 s."),
        f=("Ativacao total", "8 s em 3a pessoa: mais rapido, mais dano e roubo de vida."),
        tip="Combine Perforina com a marca do B-Cell para eliminar tanques."),
    "pneumococcus": dict(
        passive=("Capsula", "Escudo proprio que se regenera fora de combate."),
        lmb=("Disparo", "Globulos de media distancia."),
        rmb=("Barreira", "Segure: barreira frontal de 600 HP que bloqueia tiros. Sem atirar."),
        q=("Investida", "Avanca e prende o primeiro inimigo atingido."),
        e=("Capsula compartilhada", "+100 de escudo para voce e o aliado mais proximo."),
        f=("Pneumonia", "Nuvem que segue voce: dano, cega inimigos e para as plaquetas."),
        tip="Fique a frente das plaquetas com a barreira levantada."),
    "staphylococcus": dict(
        passive=("Cacho", "Regenera vida perto de colonias."),
        lmb=("Disparo", "Globulos de media distancia."),
        rmb=("Projetil aderente", "Gruda e deixa o alvo lento."),
        q=("Coagulase", "Posicione uma parede de coagulo (6 m, 5 s). Clique para fixar."),
        e=("Toxina", "Corta toda cura e regeneracao do alvo por 5 s."),
        f=("Abscesso", "Domo que bloqueia tiros de fora e protege quem esta dentro."),
        tip="Use a parede para fechar o caminho das plaquetas."),
    "pseudomonas": dict(
        passive=("Corrosao", "+30% de dano contra alvos abaixo de 50%."),
        lmb=("Disparo", "Acido que deixa pocas."),
        rmb=("Granada acida", "Segure para ver o arco, solte para lancar."),
        q=("Biofilme", "Desliza deixando um rastro que acelera aliados e prende inimigos."),
        e=("Flagelo", "Gancho: puxa voce ate a superficie mirada."),
        f=("Quorum sensing", "Equipe toda: +20% de dano e velocidade; biofilme maduro ao redor."),
        tip="Corrosao finaliza: mire em quem ja esta ferido."),
    "streptococcus": dict(
        passive=("Hemolise", "Dano dobrado contra hemacias."),
        lmb=("Metralhadora", "Rajada rapida de curto alcance."),
        rmb=("Golpe", "Corte rapido, devastador em hemacias."),
        q=("Arrancada", "Avanco na direcao da mira (2 cargas)."),
        e=("Corrente", "Lance a corrente: puxa voce ate o alvo e o deixa lento."),
        f=("Divisao binaria", "Cria 2 clones que correm e atiram."),
        tip="Flanqueie: cace hemacias longe da equipe inimiga."),
}

# Icone por habilidade (desenhado pela HUD em hud_icons.py).
ICONS = {
    "Receptor": "eye", "Fuzil": "rifle", "Faca": "knife", "Avanco cortante": "dash", "Rede NET": "net",
    "Quimiotaxia": "radar", "Fagocitose": "mouth", "Escopeta": "rifle", "Engolir": "mouth", "Pseudopode": "hook",
    "Machadada": "axe", "Banquete": "mouth", "Opsonizacao": "mark", "Rifle": "rifle", "Mira": "scope",
    "Plasmocito": "turret", "Granada de anticorpos": "grenade", "Chuva de anticorpos": "rain",
    "Licenca para matar": "mark", "Rajada": "rifle", "Soco carregado": "fist", "Salto de impacto": "leap",
    "Perforina": "drop", "Ativacao total": "burst", "Capsula": "shield", "Disparo": "rifle", "Barreira": "barrier",
    "Investida": "dash", "Capsula compartilhada": "shield", "Pneumonia": "cloud", "Cacho": "cluster",
    "Projetil aderente": "drop", "Coagulase": "wall", "Toxina": "toxin", "Abscesso": "dome", "Corrosao": "acid",
    "Granada acida": "grenade", "Biofilme": "slide", "Flagelo": "hook", "Quorum sensing": "radar",
    "Hemolise": "drop", "Metralhadora": "rifle", "Golpe": "knife", "Arrancada": "dash", "Corrente": "chain",
    "Divisao binaria": "clone",
}

UNLOCKS = {"b_cell": "unlock_b_cell", "killer_t": "unlock_killer_t"}


def unlocked(hero, recognition):
    key = UNLOCKS.get(hero)
    return key is None or recognition >= BALANCE[key]


def can_select(hero, team, roster, recognition=0, exclude=None):
    return (hero in HEROES and HEROES[hero].team == team
            and unlocked(hero, recognition)
            and sum(p["hero"] == hero for pid, p in roster.items() if pid != exclude)
            < HEROES[hero].limit)
