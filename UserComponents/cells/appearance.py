"""Typed character identities and reusable visual presets."""
from dataclasses import dataclass, replace
from enum import Enum, auto

import pyray as rl


class CharacterKind(Enum):
    RED_BLOOD_CELL = auto()
    WHITE_BLOOD_CELL = auto()
    PLATELET = auto()
    PNEUMOCOCCUS = auto()
    ORDINARY_CELL = auto()


class CharacterVariant(Enum):
    DEFAULT = auto()
    ALTERNATE = auto()
    SECONDARY = auto()


class Accessory(Enum):
    OPEN_JACKET = auto()
    LONG_HAIR = auto()
    UNIFORM_POCKET = auto()
    BLADE = auto()
    RECEPTOR = auto()
    SATCHEL = auto()


@dataclass(frozen=True)
class HumanPalette:
    skin: rl.Color
    hair: rl.Color
    jacket: rl.Color
    legs: rl.Color
    shoes: rl.Color
    shorts: rl.Color
    belt: rl.Color
    forearms: rl.Color
    hands: rl.Color
    shirt: rl.Color
    trim: rl.Color
    metal: rl.Color
    accessory: rl.Color
    eyes: rl.Color
    pupils: rl.Color
    mouth: rl.Color
    receptor_idle: rl.Color
    receptor_alert: rl.Color


@dataclass(frozen=True)
class CapAppearance:
    crown: rl.Color
    brim: rl.Color
    badge: rl.Color


@dataclass(frozen=True)
class HumanAppearance:
    palette: HumanPalette
    scale: float = 1.
    cap: CapAppearance | None = None
    accessories: tuple[Accessory, ...] = ()


@dataclass(frozen=True)
class BacteriumAppearance:
    body: rl.Color
    skin: rl.Color
    shoes: rl.Color
    claws: rl.Color
    eyes: rl.Color
    pupils: rl.Color
    teeth: rl.Color
    capsule: rl.Color


SKIN = rl.Color(250, 213, 177, 255)
WHITE = rl.Color(245, 243, 229, 255)
RED = rl.Color(200, 64, 59, 255)
GOLD = rl.Color(229, 177, 80, 255)
TEAL = rl.Color(54, 124, 122, 255)

CELL_PALETTE = HumanPalette(
    skin=SKIN, hair=rl.Color(92, 61, 42, 255),
    jacket=rl.Color(226, 224, 201, 255), legs=SKIN,
    shoes=rl.Color(57, 52, 49, 255), shorts=rl.Color(226, 224, 201, 255),
    belt=rl.Color(180, 179, 160, 255), forearms=SKIN, hands=SKIN,
    shirt=rl.Color(45, 48, 47, 255), trim=rl.Color(120, 38, 35, 255),
    metal=rl.Color(190, 211, 213, 255), accessory=GOLD,
    eyes=WHITE, pupils=rl.Color(71, 64, 46, 255), mouth=rl.Color(159, 86, 71, 255),
    receptor_idle=GOLD, receptor_alert=RED,
)
RED_PALETTE = replace(
    CELL_PALETTE, hair=rl.Color(175, 66, 39, 255), jacket=RED,
    shorts=rl.Color(59, 102, 124, 255), belt=rl.Color(91, 49, 40, 255), hands=WHITE,
)
WHITE_PALETTE = replace(
    CELL_PALETTE, skin=rl.Color(225, 233, 231, 255), hair=rl.Color(186, 201, 200, 255),
    jacket=WHITE, legs=WHITE, shoes=rl.Color(207, 218, 213, 255), shorts=WHITE,
    belt=rl.Color(196, 194, 183, 255), forearms=WHITE, hands=WHITE,
    trim=rl.Color(207, 219, 212, 255),
)
PLATELET_PALETTE = replace(
    CELL_PALETTE, jacket=rl.Color(137, 205, 215, 255),
    shorts=rl.Color(137, 205, 215, 255), belt=rl.Color(109, 164, 172, 255),
)

HUMAN_APPEARANCES = {
    CharacterKind.RED_BLOOD_CELL: HumanAppearance(
        RED_PALETTE,
        cap=CapAppearance(RED, rl.Color(44, 47, 44, 255), GOLD),
        accessories=(Accessory.OPEN_JACKET, Accessory.LONG_HAIR),
    ),
    CharacterKind.WHITE_BLOOD_CELL: HumanAppearance(
        WHITE_PALETTE, scale=1.05,
        cap=CapAppearance(WHITE, rl.Color(205, 204, 192, 255), TEAL),
        accessories=(Accessory.UNIFORM_POCKET, Accessory.BLADE, Accessory.RECEPTOR),
    ),
    CharacterKind.PLATELET: HumanAppearance(
        PLATELET_PALETTE, scale=.66,
        cap=CapAppearance(WHITE, rl.Color(205, 204, 192, 255), TEAL),
        accessories=(Accessory.SATCHEL,),
    ),
    CharacterKind.ORDINARY_CELL: HumanAppearance(CELL_PALETTE),
}
ALTERNATE_RED = replace(
    HUMAN_APPEARANCES[CharacterKind.RED_BLOOD_CELL],
    palette=replace(RED_PALETTE, hair=CELL_PALETTE.hair, legs=rl.Color(59, 99, 120, 255)),
)
BACTERIUM_APPEARANCE = BacteriumAppearance(
    body=rl.Color(146, 82, 164, 255), skin=rl.Color(183, 133, 186, 255),
    shoes=rl.Color(102, 57, 114, 255), claws=WHITE,
    eyes=rl.Color(245, 220, 92, 255), pupils=rl.Color(34, 56, 58, 255),
    teeth=WHITE, capsule=rl.Color(202, 152, 218, 110),
)


def character_appearance(kind: CharacterKind, variant: CharacterVariant) -> HumanAppearance | BacteriumAppearance:
    """Resolve the preset once when creating an actor, before rendering."""
    if not isinstance(kind, CharacterKind) or not isinstance(variant, CharacterVariant):
        raise TypeError("Character kind and variant must use their respective enums")
    if kind is CharacterKind.PNEUMOCOCCUS:
        return BACTERIUM_APPEARANCE
    if kind is CharacterKind.RED_BLOOD_CELL and variant is not CharacterVariant.DEFAULT:
        return ALTERNATE_RED
    return HUMAN_APPEARANCES[kind]


# Shooter presets extend the Odyssey models using the archived official stands.
MACROPHAGE = HumanAppearance(replace(
    CELL_PALETTE, hair=rl.Color(177, 153, 126, 255), jacket=WHITE, shorts=WHITE,
    legs=WHITE, shoes=rl.Color(165, 156, 143, 255), forearms=WHITE,
    belt=rl.Color(217, 205, 191, 255), trim=rl.Color(235, 215, 206, 255)),
    accessories=(Accessory.LONG_HAIR,))
B_CELL = HumanAppearance(replace(
    WHITE_PALETTE, skin=SKIN, hair=rl.Color(160, 108, 61, 255),
    jacket=rl.Color(113, 154, 179, 255), shorts=rl.Color(113, 154, 179, 255),
    legs=rl.Color(113, 154, 179, 255), forearms=SKIN, belt=rl.Color(76, 104, 125, 255)),
    cap=CapAppearance(rl.Color(113, 154, 179, 255), rl.Color(83, 124, 150, 255), WHITE),
    accessories=(Accessory.UNIFORM_POCKET,))
KILLER_T = HumanAppearance(replace(
    CELL_PALETTE, jacket=rl.Color(43, 47, 50, 255), shorts=rl.Color(43, 47, 50, 255),
    legs=rl.Color(43, 47, 50, 255), hair=rl.Color(211, 187, 127, 255),
    forearms=SKIN, belt=rl.Color(115, 99, 70, 255)),
    cap=CapAppearance(rl.Color(38, 41, 44, 255), rl.Color(28, 32, 35, 255), GOLD),
    accessories=(Accessory.UNIFORM_POCKET,))

MODEL_APPEARANCES = {
    'neutrophil': replace(HUMAN_APPEARANCES[CharacterKind.WHITE_BLOOD_CELL], scale=1),
    'red_blood_cell': HUMAN_APPEARANCES[CharacterKind.RED_BLOOD_CELL],
    'platelet': HUMAN_APPEARANCES[CharacterKind.PLATELET],
    'ordinary_cell': HUMAN_APPEARANCES[CharacterKind.ORDINARY_CELL],
    'macrophage': MACROPHAGE, 'b_cell': B_CELL, 'killer_t': KILLER_T,
    'pneumococcus': BACTERIUM_APPEARANCE,
    'staphylococcus': replace(BACTERIUM_APPEARANCE, body=rl.Color(219, 211, 48, 255), skin=rl.Color(207, 225, 229, 255)),
    'pseudomonas': replace(BACTERIUM_APPEARANCE, body=rl.Color(181, 201, 87, 255), skin=rl.Color(213, 229, 132, 255)),
    'streptococcus': replace(BACTERIUM_APPEARANCE, body=rl.Color(187, 47, 108, 255), skin=rl.Color(194, 218, 225, 255)),
}


def model_appearance(hero):
    return MODEL_APPEARANCES[hero]
