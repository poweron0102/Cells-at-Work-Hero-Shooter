"""Provisional kit balance, separate from scene assembly and simulation."""
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
    ability: str
    secondary: str
    ultimate: str
    limit: int = 1


HEROES = {
    "neutrophil": Hero("NEUTROPHIL 1146", CELLS, "COMBATENTE", 200, 6.2, 17, .105, 32,
                       (221, 235, 230), "Phagocytic Rush", "Faca", "Chemotactic Signal", 2),
    "macrophage": Hero("MACROPHAGE", CELLS, "CONTENCAO / ANTIGENO", 280, 5.0, 12, .8, 8,
                       (234, 190, 196), "Antigen Sample", "Machado", "Hyperactivation"),
    "b_cell": Hero("B CELL", CELLS, "PRECISAO / ANTI-COLONIA", 180, 5.8, 42, .38, 14,
                  (111, 197, 244), "Neutralization", "Coronhada", "Massive Antibodies"),
    "killer_t": Hero("KILLER T", CELLS, "BREACHER", 250, 6.0, 24, .16, 27,
                    (62, 79, 91), "Cytotoxic Charge", "Execute", "Full Activation"),
    "pneumococcus": Hero("PNEUMOCOCCUS", BACTERIA, "PRESSAO FRONTAL", 270, 5.1, 24, .22, 24,
                        (173, 119, 213), "Capsule Harden", "Invasive Charge", "Pneumonia Cloud"),
    "staphylococcus": Hero("STAPHYLOCOCCUS", BACTERIA, "COLONIZACAO", 230, 5.3, 25, .28, 24,
                          (237, 184, 77), "Colony Seed", "Aggregate", "Bacterial Cluster"),
    "pseudomonas": Hero("PSEUDOMONAS", BACTERIA, "CONTROLE DE TERRITORIO", 210, 5.8, 21, .19, 28,
                       (99, 195, 150), "Biofilm", "Acid Burst", "Mature Biofilm"),
    "streptococcus": Hero("STREPTOCOCCUS", BACTERIA, "FLANQUEADOR", 180, 7.2, 13, .08, 36,
                         (229, 115, 158), "Spread", "Hemolysis", "Rapid Spread"),
}

POINTS = [(-13, 0), (0, -3), (13, 0)]
CORE_POSITIONS = [(-11, -15), (11, -15)]
PHASE_NAMES = ["BREACH", "IDENTIFICATION", "COLONIZATION"]
PHASE_SECONDS = [180, 150, 210]


def unlocked(hero, recognition, infected):
    return (hero != "b_cell" or recognition >= 50) and (hero != "killer_t" or infected)


def can_select(hero, team, roster, recognition=0, infected=False, exclude=None):
    return (hero in HEROES and HEROES[hero].team == team
            and unlocked(hero, recognition, infected)
            and sum(p["hero"] == hero for pid, p in roster.items() if pid != exclude)
            < HEROES[hero].limit)
