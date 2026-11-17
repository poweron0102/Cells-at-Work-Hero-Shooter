"""Kits e parametros de balanceamento (centralizados para ajuste em testes).

Nenhum valor aqui foi validado em partidas: sao pontos de partida do plano.
Cada heroi tem passiva, LMB (arma), RMB, Q, E e o especial F (ver ``KIT``).
"""
from dataclasses import dataclass

CELLS = "cells"
BACTERIA = "bacteria"


@dataclass(frozen=True)
class Hero:
    name: str
    team: str
    role: str
    health: int
    speed: float
    damage: int
    interval: float
    magazine: int
    color: tuple
    secondary: str
    ability: str
    ultimate: str
    limit: int = 1
    jump_height: float = 1.2
    ability_cd: float = 8.0
    secondary_cd: float = .8
    ability2: str = ""
    ability2_cd: float = 10.0
    passive: str = ""
    ult_time: float = 0.0      # segundos de camera em 3a pessoa ao ativar o especial


HEROES = {
    "neutrophil": Hero("NEUTROPHIL 1146", CELLS, "COMBATENTE", 200, 6.2, 17, .105, 32, (221, 235, 230),
                       "Faca", "Avanco cortante", "Quimiotaxia", 2, 2.0, 7, .7,
                       ability2="Rede NET", ability2_cd=10, passive="Receptor"),
    "macrophage": Hero("MACROPHAGE", CELLS, "TANQUE / ANTIGENOS", 450, 5.0, 12, .8, 8, (234, 190, 196),
                       "Engolir", "Pseudopode", "Banquete", 1, 1.2, 8, 0,
                       ability2="Machadada", ability2_cd=5, passive="Fagocitose", ult_time=6.0),
    "b_cell": Hero("B CELL", CELLS, "PRECISAO / SUPORTE", 180, 5.8, 42, .38, 14, (111, 197, 244),
                   "Mira", "Plasmocito", "Chuva de anticorpos", 1, 1.2, 12, 0,
                   ability2="Granada de anticorpos", ability2_cd=9, passive="Opsonizacao", ult_time=4.0),
    "killer_t": Hero("KILLER T", CELLS, "INVESTIDA", 250, 6.0, 24, .16, 27, (62, 79, 91),
                     "Soco carregado", "Salto de impacto", "Ativacao total", 1, 3.6, 9, 1.2,
                     ability2="Perforina", ability2_cd=10, passive="Licenca para matar", ult_time=8.0),
    "pneumococcus": Hero("PNEUMOCOCCUS", BACTERIA, "TANQUE FRONTAL", 300, 5.1, 24, .22, 24, (173, 119, 213),
                         "Barreira", "Investida", "Pneumonia", 1, 1.2, 9, 0,
                         ability2="Capsula compartilhada", ability2_cd=12, passive="Capsula", ult_time=7.0),
    "staphylococcus": Hero("STAPHYLOCOCCUS", BACTERIA, "COLONIZACAO", 230, 5.3, 25, .28, 24, (237, 184, 77),
                           "Projetil aderente", "Coagulase", "Abscesso", 1, 1.2, 12, 1.6,
                           ability2="Toxina", ability2_cd=9, passive="Cacho", ult_time=3.0),
    "pseudomonas": Hero("PSEUDOMONAS", BACTERIA, "CONTROLE DE AREA", 210, 5.8, 21, .19, 28, (99, 195, 150),
                        "Granada acida", "Biofilme", "Quorum sensing", 1, 3.6, 8, 2.2,
                        ability2="Flagelo", ability2_cd=8, passive="Corrosao", ult_time=3.0),
    "streptococcus": Hero("STREPTOCOCCUS", BACTERIA, "FLANQUEADOR", 180, 6.6, 10, .08, 36, (229, 115, 158),
                          "Golpe", "Arrancada", "Divisao binaria", 1, 2.0, 5, .9,
                          ability2="Corrente", ability2_cd=9, passive="Hemolise", ult_time=3.0),
}

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
        f=("Chuva de anticorpos", "Vista aerea: chuva de anticorpos na mira, dano e marcacao em area."),
        tip="Sua marca alimenta a equipe: Killer T ganha +20% contra marcados."),
    "killer_t": dict(
        passive=("Licenca para matar", "+20% de dano contra alvos marcados."),
        lmb=("Rajada", "Tres tiros por gatilho."),
        rmb=("Soco carregado", "Segure para carregar, solte para golpear e arremessar."),
        q=("Salto de impacto", "Salta e esmaga onde cair (circulo de pouso)."),
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

BALANCE = dict(
    respawn_seconds=6.0,
    # Escolta
    escort_speed=.6,              # m/s das plaquetas
    escort_block_distance=5.0,     # faixa a frente da escolta
    escort_block_height=1.6,       # mesma passagem: diferenca vertical maxima
    # Economia
    rbc_count=9,
    rbc_speed=3.2,
    rbc_health=60,
    rbc_resource=2,                # recurso deixado ao morrer
    rbc_sight=16.0,
    rbc_memory=3.5,                # segundos lembrando da ameaca
    rbc_commit=1.2,                # intervalo minimo antes de trocar de rota
    rbc_respawn=7.0,
    drop_life=40.0,
    pickup_radius=2.0,
    # Colonias
    colony_cost=5,
    colony_build_time=3.0,
    colony_build_radius=2.2,
    colony_health=420,
    colony_limit=3,
    colony_base_infection=10,
    colony_dev_per_resource=3,
    colony_dev_cap=24,
    colony_protection_each=.08,
    colony_protection_cap=.4,
    infection_goal=150,
    # Reconhecimento (antigenos) e desbloqueios
    antigen_per_sample=12,
    antigen_macrophage=26,
    unlock_b_cell=40,
    unlock_killer_t=90,
    antigen_life=30.0,
    # Reconhecimento do mapa apos fechar a ferida
    recon_channel=4.0,
    recon_radius=3.0,
    recon_reveal=14.0,
    recon_cooldown=30.0,
    # Especiais
    charge_per_damage=.22,
    charge_escort=1.2,             # por segundo perto da escolta
    charge_collect=6,
    charge_build=10,
    charge_protect=.35,            # por dano causado perto de uma hemacia
    charge_absorb=.3,              # Engolir: carga por dano engolido
    # Kits
    mark_bonus=.15,                # dano extra recebido por alvos marcados
    engulf_time=3.0,               # barra do Engolir (s)
    engulf_radius=1.3,
    barrier_health=600,
    barrier_radius=1.7,
    turret_health=160,
    turret_range=15.0,
    turret_damage=11,
    wall_life=5.0,
    wall_width=6.0,
    clone_health=60,
    dome_radius=7.0,
)

UNLOCKS = {"b_cell": "unlock_b_cell", "killer_t": "unlock_killer_t"}


def unlocked(hero, recognition):
    key = UNLOCKS.get(hero)
    return key is None or recognition >= BALANCE[key]


def can_select(hero, team, roster, recognition=0, exclude=None):
    return (hero in HEROES and HEROES[hero].team == team
            and unlocked(hero, recognition)
            and sum(p["hero"] == hero for pid, p in roster.items() if pid != exclude)
            < HEROES[hero].limit)
