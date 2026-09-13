"""Face-only source rectangles in the official first-season expression sheets.

Coordinates are in source pixels; sheets remain untouched. States without an
appropriate official expression deliberately reuse the normal face.
"""
from pathlib import Path
import pyray as rl
from .visuals import color

ROOT = Path('Assets/characters/official/1st/assets/img/character')
# Rectangles: x, y, width, height. Keep each crop clear of adjacent faces.
FACES = {
    'neutrophil': ('leukocyte', [(265, 48, 188, 260), (72, 310, 190, 252), (412, 330, 216, 270)],
                   {'normal': 0, 'low': 1, 'hurt': 2, 'special': 2}),
    'macrophage': ('macrophage', [(239, 45, 220, 267), (90, 312, 195, 288), (394, 318, 225, 284)],
                   {'normal': 0, 'low': 2, 'hurt': 2, 'special': 1, 'success': 0}),
    'b_cell': ('b_cell', [(244, 56, 210, 248), (73, 334, 211, 250), (388, 335, 229, 250)],
               {'normal': 0, 'low': 2, 'hurt': 2, 'special': 1}),
    'killer_t': ('killer_t_cell', [(244, 47, 210, 258), (52, 314, 238, 242), (397, 313, 238, 270)],
                 {'normal': 2, 'low': 1, 'hurt': 0, 'special': 0, 'success': 2}),
    'pneumococcus': ('s_pneumoniae', [(135, 130, 207, 250), (347, 364, 223, 252)],
                     {'normal': 0, 'low': 1, 'hurt': 1, 'special': 1}),
    'staphylococcus': ('s_aureus', [(229, 84, 286, 267)], {'normal': 0}),
    'pseudomonas': ('s_aeruginosa', [(286, 140, 160, 224)], {'normal': 0}),
    'streptococcus': ('s_pyogenes', [(81, 101, 239, 276), (426, 260, 184, 181)],
                      {'normal': 0, 'special': 1, 'success': 1}),
}


def draw_face(canvas, hero, state, x, y, size):
    folder, regions, states = FACES[hero]
    key = 'hud-face:' + hero
    if key not in canvas.textures:
        path = ROOT / folder / 'up.png'
        canvas.textures[key] = rl.load_texture(str(path)) if path.exists() else None
        if canvas.textures[key]:
            rl.set_texture_filter(canvas.textures[key], rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
    texture = canvas.textures[key]
    if not texture:
        canvas.portrait(hero, x, y, size, size)
        return
    sx, sy, w, h = regions[states.get(state, states['normal'])]
    factor = size / max(w, h)
    dw, dh = w * factor, h * factor
    rl.draw_texture_pro(texture, rl.Rectangle(sx, sy, w, h),
                        canvas.rect(x + (size-dw)/2, y + (size-dh)/2, dw, dh),
                        rl.Vector2(0, 0), 0, color((255, 255, 255)))
