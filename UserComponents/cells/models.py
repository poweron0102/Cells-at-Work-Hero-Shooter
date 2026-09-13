"""Articulated models adapted from Cellular-Odyssey-2 and official reference art."""
import math
import pyray as rl
from EasyCells3D.Geometry import Vec3
from .appearance import Accessory, BacteriumAppearance, CapAppearance, HumanAppearance, HumanPalette, model_appearance
from .art import box, sphere, cylinder, color, INK, WHITE, RED, TEAL, GOLD
from . import model_lighting

class CharacterModel:
    def __init__(self, hero):
        self.hero = hero
        self.appearance = model_appearance(hero)
        self.phase = 0
        self.moving = False
        self.reveal = self.shield = 0
        self._accessory_renderers = {
            Accessory.OPEN_JACKET: self._open_jacket,
            Accessory.LONG_HAIR: self._long_hair,
            Accessory.UNIFORM_POCKET: self._uniform_pocket,
            Accessory.BLADE: self._blade,
            Accessory.RECEPTOR: self._receptor,
            Accessory.SATCHEL: self._satchel,
        }

    def draw(self, position, yaw=0, phase=0, moving=False, reveal=0, shield=0):
        self.phase, self.moving, self.reveal, self.shield = phase, moving, reveal, shield
        model_lighting.begin()
        rl.rl_push_matrix()
        rl.rl_translatef(position.x, position.y, position.z)
        rl.rl_rotatef(180-math.degrees(yaw), 0, 1, 0)
        # Feet at the capsule base; model height matches the shared combat hitbox.
        scale = .69 if isinstance(self.appearance, BacteriumAppearance) else .76
        rl.rl_scalef(scale, scale, scale)
        if self.hero == 'staphylococcus':
            self._staphylococcus()
        elif self.hero in ('pseudomonas', 'streptococcus'):
            self._pseudomonas() if self.hero == 'pseudomonas' else self._streptococcus()
        elif isinstance(self.appearance, BacteriumAppearance):
            self._bacteria()
        else:
            self._human()
            self._equipment()
        rl.rl_pop_matrix()
        model_lighting.end()

    def _equipment(self):
        p = self.appearance.palette
        if self.hero == 'macrophage':
            # Bell skirt, apron, bonnet, braided hair and the heavy cleaver.
            cylinder(Vec3(0, .32, 0), Vec3(0, 1.16, 0), .7, p.jacket, .34)
            for i in range(16):
                a = i*math.tau/16
                sphere(Vec3(math.cos(a)*.67, .34, math.sin(a)*.67), .09, p.trim)
            box(Vec3(0, .79, .45), Vec3(.42, .66, .11), WHITE)
            sphere(Vec3(0, 2.4, -.03), .36, WHITE)
            for i in range(9):
                a = i*math.pi/8
                sphere(Vec3(math.cos(a)*.33, 2.37+math.sin(a)*.12, .2), .09, p.trim)
            for i in range(7):
                sphere(Vec3(.32+i*.065, 2.12-i*.08, -.09), .105, p.hair)
            cylinder(Vec3(.51, .55, .2), Vec3(.51, 1.48, .2), .045, GOLD)
            box(Vec3(.66, .6, .2), Vec3(.38, .7, .07), p.metal)
            box(Vec3(.85, .6, .2), Vec3(.045, .72, .085), WHITE)
        elif self.hero in ('b_cell', 'killer_t', 'neutrophil'):
            # Distinct weapons plus a readable shoulder emblem.
            length = 1.05 if self.hero == 'b_cell' else .7
            box(Vec3(.48, 1.27, .42), Vec3(.18, .24, length), INK)
            cylinder(Vec3(.48, 1.28, .8), Vec3(.48, 1.28, .8+length*.5), .055, p.metal)
            box(Vec3(.48, 1.44, .46), Vec3(.09, .11, .23), TEAL)
            box(Vec3(-.405, 1.65, .02), Vec3(.06, .24, .25), WHITE)
            if self.hero == 'b_cell':
                for y in (1.58, 1.7):
                    box(Vec3(-.444, y, .025), Vec3(.02, .055, .12), INK)
                for x in (-.19, .19):
                    box(Vec3(x, 1.5, .25), Vec3(.21, .22, .045), p.trim)
                # Antibody cartridge pack with twin canisters.
                box(Vec3(0, 1.46, -.36), Vec3(.57, .56, .3), INK)
                for x in (-.16, .16):
                    cylinder(Vec3(x, 1.2, -.49), Vec3(x, 1.77, -.49), .1, TEAL)
            elif self.hero == 'killer_t':
                box(Vec3(-.443, 1.68, .02), Vec3(.025, .055, .17), INK)
                box(Vec3(-.443, 1.61, .02), Vec3(.025, .15, .05), INK)

    def _staphylococcus(self):
        p = self.appearance
        bob = math.sin(self.phase)*.05
        for side in (-1, 1):
            cylinder(Vec3(side*.2, .16, 0), Vec3(side*.22, 1.05, 0), .13, p.body)
            cylinder(Vec3(side*.42, 1.65, 0), Vec3(side*.75, 1.0, .2), .12, p.skin)
        cylinder(Vec3(0, .55, 0), Vec3(0, 1.6, 0), .58, p.body, .32)
        for level, radius in ((.6, .46), (.95, .57), (1.25, .42)):
            for i in range(8):
                a = i*math.tau/8
                sphere(Vec3(math.cos(a)*radius, level, math.sin(a)*radius), .24, p.body)
        for y in (1.38, 1.59, 1.8):
            sphere(Vec3(0, y, .3), .12, p.skin)
        sphere(Vec3(0, 2.12+bob, .04), .42, p.skin)
        # Grape-like golden clusters form the distinctive aureus silhouette.
        for i in range(13):
            a = i*math.tau/13
            sphere(Vec3(math.cos(a)*.55, 2.15+bob+math.sin(a)*.53, -.12), .23, p.body)
        for side in (-1, 1):
            box(Vec3(side*.15, 2.16+bob, .44), Vec3(.15, .065, .025), p.pupils)
        box(Vec3(0, 1.96+bob, .435), Vec3(.17, .035, .03), p.pupils)
        last = Vec3(.4, .8, -.2)
        for i in range(1, 9):
            nxt = Vec3(.4+math.sin(i*.3)*.75, .8-i*.07, -.2-i*.08)
            cylinder(last, nxt, .065, p.body, .045)
            last = nxt
        cylinder(last, last+Vec3(-.2, -.12, .1), .12, INK, .005)

    def _pseudomonas(self):
        p = self.appearance
        # Official reference: green quadruped, hooked neck and one large eye.
        sphere(Vec3(0, 1.02, -.16), .57, p.body)
        cylinder(Vec3(0, 1.12, .08), Vec3(0, 2.16, .05), .34, p.body, .29)
        sphere(Vec3(0, 2.22, .2), .44, p.body)
        sphere(Vec3(0, 2.21, .52), .31, p.skin)
        sphere(Vec3(0, 2.21, .65), .24, WHITE)
        sphere(Vec3(0, 2.21, .84), .13, GOLD)
        sphere(Vec3(0, 2.21, .94), .062, INK)
        box(Vec3(0, 1.8, .37), Vec3(.39, .16, .08), INK)
        for i in range(6):
            cylinder(Vec3(-.16+i*.065, 1.85, .42), Vec3(-.16+i*.065, 1.76, .44), .029, WHITE, .003)
        for side in (-1, 1):
            for z in (-.48, .28):
                wave = math.sin(self.phase+side+z*4)*.1 if self.moving else 0
                knee = Vec3(side*.68, .47, z+wave)
                cylinder(Vec3(side*.3, 1.02, z), knee, .2, p.body, .14)
                cylinder(knee, Vec3(side*.75, .08, z+.17+wave), .14, p.body, .025)
            last = Vec3(side*.33, 1.35, .28)
            for i in range(1, 8):
                nxt = Vec3(side*(.33+math.sin(i*.35)*.42), 1.35-i*.075, .28+i*.12)
                cylinder(last, nxt, .04, p.body, .02)
                last = nxt
        last = Vec3(0, 1, -.5)
        for i in range(1, 9):
            nxt = Vec3(math.sin(i*.35+self.phase*.15)*.22, 1-i*.06, -.5-i*.14)
            cylinder(last, nxt, max(.025, .3-i*.033), p.body, max(.01, .27-i*.033))
            last = nxt

    def _streptococcus(self):
        p = self.appearance
        stride = math.sin(self.phase)*.22 if self.moving else 0
        cylinder(Vec3(0, 1.1, 0), Vec3(0, 1.8, 0), .23, p.skin, .34)
        for side in (-1, 1):
            knee = Vec3(side*.22, .55, side*stride)
            foot = Vec3(side*.25, .09, side*stride*1.5)
            cylinder(Vec3(side*.2, 1.15, 0), knee, .17, p.body, .12)
            cylinder(knee, foot, .12, p.body, .07)
            cylinder(foot, foot+Vec3(0, -.03, .3), .11, INK, .005)
            shoulder, elbow, hand = Vec3(side*.39, 1.76, 0), Vec3(side*.5, 1.4, .06), Vec3(side*.57, 1.03, .2)
            sphere(shoulder, .2, p.body)
            cylinder(shoulder, elbow, .1, p.body)
            cylinder(elbow, hand, .08, p.body, .05)
            cylinder(hand, hand+Vec3(side*.07, -.32, .16), .11, INK, .003)
        sphere(Vec3(0, 2.16, .02), .32, p.skin)
        cylinder(Vec3(0, 2.36, 0), Vec3(0, 2.98, -.04), .3, p.body, .003)
        for side in (-1, 1):
            cylinder(Vec3(side*.18, 2.34, 0), Vec3(side*.58, 2.52, .04), .2, p.body, .003)
            box(Vec3(side*.12, 2.19, .31), Vec3(.2, .11, .045), INK)
            sphere(Vec3(side*.12, 2.2, .345), .042, GOLD)
        for y in (1.25, 1.72):
            cylinder(Vec3(-.3, y, .24), Vec3(.3, y+.14, .24), .07, p.body)
        # Long beaded head-tail, visible from the side and rear.
        for i in range(13):
            a = i*.17
            pos = Vec3(.28+math.sin(a)*.56, 2.4-i*.12, -.2-i*.045)
            sphere(pos, .145-i*.003, p.body)
            cylinder(pos, pos+Vec3(.13, .14, -.12), .067, INK, .003)

    def _human(self):
        appearance: HumanAppearance = self.appearance
        palette = appearance.palette
        rl.rl_scalef(appearance.scale, appearance.scale, appearance.scale)
        stride = 0.
        if self.moving:
            stride = math.sin(self.phase) * .34
        cylinder(Vec3(0, .01, 0), Vec3(0, .018, 0), .57, color(84, 91, 77, 70))
        self._legs(palette, stride)
        self._torso(palette)
        self._arms(palette, stride)
        self._head(palette)
        if appearance.cap is not None:
            self._cap(appearance.cap)
        for accessory in appearance.accessories:
            self._accessory_renderers[accessory](palette)

    def _legs(self, palette: HumanPalette, stride: float):
        for side in (-1, 1):
            hip = Vec3(side * .19, 1.0, 0)
            knee = Vec3(side * .19, .55, side * stride)
            ankle = Vec3(side * .19, .15, side * stride * 1.3)
            cylinder(hip, knee, .145, palette.legs)
            cylinder(knee, ankle, .12, palette.legs)
            box(ankle + Vec3(0, -.04, .09), Vec3(.29, .23, .46), palette.shoes)

    def _torso(self, palette: HumanPalette):
        box(Vec3(0, 1., 0), Vec3(.7, .35, .45), palette.shorts)
        box(Vec3(0, 1.1, 0), Vec3(.72, .09, .48), palette.belt)
        box(Vec3(0, 1.47, 0), Vec3(.77, .69, .45), palette.jacket)

    def _arms(self, palette: HumanPalette, stride: float):
        for side in (-1, 1):
            elbow_z = -side * stride
            hand_z = -side * stride * 1.5
            shoulder = Vec3(side * .47, 1.73, 0)
            elbow = Vec3(side * .56, 1.35, elbow_z)
            hand = Vec3(side * .47, 1.04, hand_z)
            if side > 0 and self.hero in ('b_cell', 'killer_t', 'neutrophil'):
                elbow = Vec3(.56, 1.34, .12)
                hand = Vec3(.48, 1.2, .4)
            cylinder(shoulder, elbow, .14, palette.jacket)
            cylinder(elbow, hand, .1, palette.forearms)
            sphere(hand, .13, palette.hands)

    def _head(self, palette: HumanPalette):
        cylinder(Vec3(0, 1.78, 0), Vec3(0, 1.94, 0), .13, palette.skin)
        sphere(Vec3(0, 2.15, 0), .36, palette.hair)
        sphere(Vec3(0, 2.1, .115), .3, palette.skin)
        for side in (-1, 1):
            box(Vec3(side * .115, 2.14, .392), Vec3(.105, .14, .025), palette.eyes)
            box(Vec3(side * .105, 2.14, .411), Vec3(.052, .10, .022), palette.pupils)
            box(Vec3(side * .08, 2.17, .426), Vec3(.02, .032, .01), palette.eyes)
        box(Vec3(0, 1.994, .39), Vec3(.09, .023, .014), palette.mouth)

    def _cap(self, cap: CapAppearance):
        cylinder(Vec3(0, 2.36, 0), Vec3(0, 2.48, 0), .4, cap.crown, .32)
        box(Vec3(0, 2.35, .24), Vec3(.68, .06, .43), cap.brim)
        sphere(Vec3(.28, 2.43, .18), .075, cap.badge)

    def _open_jacket(self, palette: HumanPalette):
        box(Vec3(0, 1.48, .232), Vec3(.26, .66, .035), palette.shirt)
        box(Vec3(.22, 1.51, .25), Vec3(.17, .05, .04), palette.trim)

    def _uniform_pocket(self, palette: HumanPalette):
        box(Vec3(-.22, 1.47, .25), Vec3(.19, .19, .045), palette.trim)

    def _blade(self, palette: HumanPalette):
        cylinder(Vec3(.5, .95, .3), Vec3(.52, 1.42, .32), .06, palette.metal, .015)

    def _long_hair(self, palette: HumanPalette):
        for side in (-1, 1):
            cylinder(Vec3(side * .28, 2.24, .02), Vec3(side * .29, 1.95, .08), .1, palette.hair, .025)

    def _receptor(self, palette: HumanPalette):
        light = palette.receptor_idle
        if self.reveal > 0:
            light = palette.receptor_alert
        cylinder(Vec3(.27, 2.5, 0), Vec3(.31, 2.9, 0), .02, INK)
        sphere(Vec3(.31, 2.92, 0), .06, light)

    def _satchel(self, palette: HumanPalette):
        cylinder(Vec3(-.28, 1.75, .28), Vec3(.31, 1.03, .29), .035, palette.accessory)
        box(Vec3(.33, .95, .1), Vec3(.37, .4, .29), palette.accessory)

    def _bacteria(self):
        a = self
        bob = math.sin(a.phase) * .12
        palette: BacteriumAppearance = self.appearance
        for side in (-1, 1):
            foot = Vec3(side * .38, .1, math.sin(a.phase + side) * .3)
            cylinder(foot, Vec3(side * .3, 1.1, 0), .18, palette.body)
            box(foot, Vec3(.37, .2, .6), palette.shoes)
            cylinder(Vec3(side * .5, 1.7 + bob, 0), Vec3(side * 1.0, 1.2 + bob, .3), .16, palette.skin)
            for finger in range(3):
                cylinder(Vec3(side * 1., 1.2 + bob, .3), Vec3(side * (1.1 + finger * .08), 1.02 + bob, .52), .04, palette.claws, .008)
        sphere(Vec3(0, 1.55 + bob, 0), .67, palette.body)
        sphere(Vec3(0, 2.23 + bob, 0), .53, palette.skin)
        for i in range(8):
            angle = i * math.tau / 8
            root = Vec3(math.sin(angle) * .42, 2.3 + bob + math.cos(angle) * .35, 0)
            tip = Vec3(math.sin(angle) * .83, 2.3 + bob + math.cos(angle) * .73, -.05)
            cylinder(root, tip, .13, palette.body, .015)
        for side in (-1, 1):
            box(Vec3(side * .18, 2.28 + bob, .48), Vec3(.18, .09, .025), palette.eyes)
            box(Vec3(side * .18, 2.28 + bob, .5), Vec3(.035, .09, .02), palette.pupils)
        box(Vec3(0, 2.04 + bob, .47), Vec3(.38, .1, .025), palette.pupils)
        for i in range(5):
            box(Vec3(-.15 + i * .075, 2.04 + bob, .49), Vec3(.042, .075, .025), palette.teeth)
        if self.shield > 0:
            rl.draw_sphere_wires(Vec3(0, 1.55, 0).to_raylib(), 1.35, 6, 10, palette.capsule)


