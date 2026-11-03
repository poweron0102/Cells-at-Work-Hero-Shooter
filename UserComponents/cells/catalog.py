"""Kits e parametros de balanceamento (centralizados para ajuste em testes).

Nenhum valor aqui foi validado em partidas: sao pontos de partida do plano.
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


HEROES = {
    "neutrophil": Hero("NEUTROPHIL 1146", CELLS, "COMBATENTE", 200, 6.2, 17, .105, 32, (221, 235, 230),
                       "Golpe de faca", "Avanco cortante", "Quimiotaxia", 2, 2.0, 7, .7),
    "macrophage": Hero("MACROPHAGE", CELLS, "PROTECAO / ANTIGENOS", 280, 5.0, 12, .8, 8, (234, 190, 196),
                       "Machado em arco", "Golpe no chao", "Hiperativacao", 1, 1.2, 9, 1.0),
    "b_cell": Hero("B CELL", CELLS, "PRECISAO / ANTI-COLONIA", 180, 5.8, 42, .38, 14, (111, 197, 244),
                  "Mira", "Disparo marcador", "Anticorpos em massa", 1, 1.2, 10, 0),
    "killer_t": Hero("KILLER T", CELLS, "INVESTIDA", 250, 6.0, 24, .16, 27, (62, 79, 91),
                    "Golpe forte", "Salto de impacto", "Ativacao total", 1, 3.6, 9, 1.1),
    "pneumococcus": Hero("PNEUMOCOCCUS", BACTERIA, "PRESSAO FRONTAL", 270, 5.1, 24, .22, 24, (173, 119, 213),
                        "Investida", "Capsula", "Nuvem pneumonica", 1, 1.2, 11, 7),
    "staphylococcus": Hero("STAPHYLOCOCCUS", BACTERIA, "COLONIZACAO", 230, 5.3, 25, .28, 24, (237, 184, 77),
                          "Projetil aderente", "Reparar colonia", "Fortificar colonias", 1, 1.2, 9, 1.6),
    "pseudomonas": Hero("PSEUDOMONAS", BACTERIA, "CONTROLE DE AREA", 210, 5.8, 21, .19, 28, (99, 195, 150),
                       "Acido explosivo", "Biofilme", "Biofilme maduro", 1, 3.6, 11, 2.2),
    "streptococcus": Hero("STREPTOCOCCUS", BACTERIA, "FLANQUEADOR", 180, 7.2, 13, .08, 36, (229, 115, 158),
                         "Hemolise", "Arrancada", "Proliferacao rapida", 1, 2.0, 5, .9),
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
