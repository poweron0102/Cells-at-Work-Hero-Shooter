"""Screen-space UI using CameraUI/RenderableUI (legacy pygame widgets are unused)."""
from pathlib import Path
import math
import pyray as rl
from EasyCells3D.Components.CameraUI import CameraUI, RenderableUI
from .visuals import color

INK = (26, 50, 48)
MUTED = (102, 118, 110)
PAPER = (246, 244, 233)
TEAL = (39, 123, 110)
RED = (203, 71, 65)
LINE = (214, 220, 206)
WHITE = (255, 255, 246)


def load_ui(game, screen):
    camera = game.CreateItem().AddComponent(CameraUI())
    item = game.CreateItem()
    item.name = screen.__class__.__name__
    screen.camera = camera
    return item.AddComponent(screen)


class Canvas(RenderableUI):
    def __init__(self):
        self.controls = []
        self.textures = {}
        self.focus = ""

    def init(self):
        super().init()
        self.font = rl.get_font_default()
        self.custom_font = False
        # Windows' UI font provides readable small text without bundling a system font.
        font_path = Path("Assets/fonts/Inter.ttf")
        if font_path.exists():
            self.font = rl.load_font_ex(str(font_path), 64, rl.ffi.NULL, 0)
            self.custom_font = True
            rl.set_texture_filter(self.font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)

    def layout(self):
        self.scale = min(rl.get_screen_width()/1280, rl.get_screen_height()/720)
        self.ox = (rl.get_screen_width()-1280*self.scale)/2
        self.oy = (rl.get_screen_height()-720*self.scale)/2
        self.controls = []

    def rect(self, x, y, w, h):
        return rl.Rectangle(self.ox+x*self.scale, self.oy+y*self.scale, w*self.scale, h*self.scale)

    def panel(self, x, y, w, h, tint=PAPER, alpha=255):
        rl.draw_rectangle_rec(self.rect(x, y, w, h), color(tint, alpha))

    def line(self, x, y, w, tint=LINE):
        self.panel(x, y, w, 1, tint)

    def text(self, value, x, y, size=20, tint=INK):
        rl.draw_text_ex(self.font, str(value), rl.Vector2(self.ox+x*self.scale, self.oy+y*self.scale), size*self.scale, .4*self.scale, color(tint))

    def circle(self, x, y, r, tint, alpha=255):
        rl.draw_circle(int(self.ox+x*self.scale), int(self.oy+y*self.scale), r*self.scale, color(tint, alpha))

    def button(self, title, x, y, w, action, primary=False, enabled=True, h=48):
        rect = self.rect(x, y, w, h)
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), rect)
        bg = TEAL if primary else WHITE
        if hover and enabled:
            bg = (32, 98, 90) if primary else (228, 234, 219)
        if not enabled:
            bg = LINE
        self.panel(x, y, w, h, bg)
        self.text(title, x+17, y+(h-22)/2-1, 21, WHITE if primary else INK if enabled else MUTED)
        if enabled:
            self.controls.append((rect, action))

    def portrait(self, hero, x, y, w, h, tint=WHITE):
        if hero not in self.textures:
            path = Path("Assets/characters") / f"{hero}.png"
            self.textures[hero] = rl.load_texture(str(path)) if path.exists() else None
            if self.textures[hero]:
                rl.gen_texture_mipmaps(rl.ffi.addressof(self.textures[hero]))
                rl.set_texture_filter(self.textures[hero], rl.TextureFilter.TEXTURE_FILTER_TRILINEAR)
        texture = self.textures[hero]
        if texture:
            factor = min(w/texture.width, h/texture.height)
            dw, dh = texture.width*factor, texture.height*factor
            rl.draw_texture_pro(texture, rl.Rectangle(0, 0, texture.width, texture.height),
                                self.rect(x+(w-dw)/2, y+h-dh, dw, dh), rl.Vector2(0, 0), 0, color(tint))
        else:
            from .catalog import HEROES, CELLS
            kit = HEROES.get(hero)
            if not kit:
                return
            cx, cy, r = x+w*.5, y+h*.5, min(w, h)*.28
            if kit.team != CELLS:
                for i in range(8):
                    angle = i*math.tau/8
                    self.circle(cx+math.cos(angle)*r*1.2, cy+math.sin(angle)*r*1.2, r*.2, kit.color)
                self.circle(cx, cy, r, kit.color)
                for dx in (-.34, .34):
                    self.circle(cx+dx*r, cy-r*.12, r*.24, WHITE)
                    self.circle(cx+dx*r, cy-r*.12, r*.10, INK)
            else:
                self.panel(cx-r, cy, r*2, r*1.7, kit.color)
                self.circle(cx, cy-r*.55, r*.7, (236, 203, 168))
                self.panel(cx-r*.85, cy-r*1.3, r*1.7, r*.35, kit.color)
                self.text("B", cx-r*.24, cy+r*.35, r*.85, WHITE)

    def bar(self, x, y, w, amount, tint=TEAL, h=5):
        self.panel(x, y, w, h, LINE)
        self.panel(x, y, w*max(0, min(1, amount)), h, tint)

    def chrome(self, section):
        self.layout()
        rl.clear_background(color(PAPER))
        self.circle(49, 42, 14, RED)
        self.circle(49, 42, 6, PAPER)
        self.text("CELLS AT WORK", 73, 24, 22)
        self.text("IMMUNE OPERATIONS", 74, 48, 10, MUTED)
        self.text(section, 455, 35, 14, MUTED)
        self.panel(1040, 27, 196, 30, (224, 232, 215))
        self.circle(1056, 42, 3, TEAL)
        self.text("ABRASION / PROTOTYPE", 1067, 33, 12, TEAL)
        self.line(40, 79, 1196)
        self.line(40, 671, 1196)
        self.text("EASYCELLS 3D     /     FAN PROTOTYPE", 42, 685, 12, MUTED)
        self.text("OBJETIVOS DEFINEM A VITORIA. O CORPO DEFINE O COMBATE.", 785, 685, 11, MUTED)

    def loop(self):
        if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
            for rect, action in reversed(self.controls):
                if rl.check_collision_point_rec(rl.get_mouse_position(), rect):
                    action()
                    break

    def on_destroy(self):
        super().on_destroy()
        for texture in self.textures.values():
            if texture:
                rl.unload_texture(texture)
        if getattr(self, "custom_font", False):
            rl.unload_font(self.font)
