"""Entrada local, camera em primeira pessoa, zoom do B Cell e modo espectador.

Os controles nunca viajam pela rede: cada jogador simula o proprio heroi.
"""
import math
import random
import pyray as rl
from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3, Quaternion
from .cursor import set_cursor_captured

BASE_FOV = 75
ZOOM_FOV = 32


class PlayerInput(Component):
    def __init__(self, arena, camera):
        self.arena, self.camera = arena, camera
        self.yaw = self.pitch = 0
        self.paused = False
        self.last_slot = None
        self.spectating = None
        self.spectate_reason = ""
        self.camera_target = None
        self.was_alive = True

    def spectate_target(self, actor):
        """Killer during the countdown; a living ally while waiting for a colony."""
        actors = self.arena.actors
        if not actor.waiting and actor.killer is not None:
            killer = actors.get(actor.killer)
            if killer is not None and killer.alive and killer.slot != actor.slot:
                self.spectate_reason = "Acompanhando quem eliminou voce"
                return killer.slot
        allies = [a.slot for a in actors.values() if a.team == actor.team and a.alive and a.slot != actor.slot]
        if not allies:
            self.spectate_reason = "Nenhum aliado vivo para acompanhar"
            return None
        if self.spectating not in allies or (actor.killer is not None and self.spectating == actor.killer):
            self.spectating = random.choice(allies)
        if rl.is_key_pressed(rl.KeyboardKey.KEY_TAB):
            self.spectating = allies[(allies.index(self.spectating)+1) % len(allies)]
        self.spectate_reason = "Aliado (Tab alterna)"
        return self.spectating

    def follow(self, slot):
        target = self.arena.actors[slot]
        yaw = target.yaw
        back = Vec3(-math.sin(yaw), 0, math.cos(yaw))
        eye = target.transform.position+Vec3(0, 1.6, 0)+back*3.6
        hit = self.game.physics_world.raycast(target.transform.position+Vec3(0, 1.2, 0), eye-target.transform.position-Vec3(0, 1.2, 0), 4.0, 1)
        if hit:
            eye = hit.point+(target.transform.position-hit.point).normalize()*.3
        self.camera.transform.position = eye
        self.camera.transform.rotation = (Quaternion.from_axis_angle(Vec3(0, 1, 0), -yaw)
                                          * Quaternion.from_axis_angle(Vec3(1, 0, 0), -.22))

    def loop(self):
        net = self.game.session
        slot = net.local_slot
        if slot is None or slot not in self.arena.actors:
            set_cursor_captured(False)
            return
        actor = self.arena.actors[slot]
        if slot != self.last_slot:
            self.yaw = actor.yaw
            self.last_slot = slot
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            self.paused = not self.paused
        captured = not self.paused and actor.alive and not net.error
        set_cursor_captured(captured)
        if actor.alive and not self.was_alive:
            self.yaw, self.pitch = actor.yaw, 0
            self.spectating = None
        self.was_alive = actor.alive
        if not actor.alive:
            self.camera.vfov = BASE_FOV
            target = self.spectate_target(actor)
            self.camera_target = target
            if target is not None:
                self.follow(target)
            actor.controls = {}
            return
        if captured:
            delta = rl.get_mouse_delta()
            sens = .0024*(.45 if actor.zoom else 1)
            self.yaw = (self.yaw + delta.x*sens) % math.tau
            self.pitch = max(-1.45, min(1.45, self.pitch-delta.y*sens))
        self.camera.vfov = ZOOM_FOV if actor.zoom else BASE_FOV
        self.camera.transform.position = actor.transform.position+Vec3(0, .56, 0)
        self.camera.transform.rotation = (Quaternion.from_axis_angle(Vec3(0, 1, 0), -self.yaw)
                                          * Quaternion.from_axis_angle(Vec3(1, 0, 0), self.pitch))
        down = lambda key: captured and rl.is_key_down(key)
        k = rl.KeyboardKey
        actor.controls = dict(x=float(down(k.KEY_D))-float(down(k.KEY_A)), z=float(down(k.KEY_W))-float(down(k.KEY_S)),
                              yaw=self.yaw, pitch=self.pitch, jump=captured and rl.is_key_pressed(k.KEY_SPACE),
                              fire=captured and rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT),
                              secondary=captured and rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_RIGHT),
                              ability=bool(down(k.KEY_Q)), ultimate=bool(down(k.KEY_F)), interact=bool(down(k.KEY_E)),
                              build=bool(down(k.KEY_G)), reload=bool(down(k.KEY_R)), sprint=bool(down(k.KEY_LEFT_SHIFT)))

    def on_destroy(self):
        set_cursor_captured(False)
        self.camera.vfov = BASE_FOV
