"""Local input and first-person camera; controls never travel over the network."""
import math
import pyray as rl
from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3, Quaternion
from .cursor import set_cursor_captured


class PlayerInput(Component):
    def __init__(self, arena, camera):
        self.arena, self.camera = arena, camera
        self.yaw = self.pitch = 0
        self.paused = False
        self.last_slot = None

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
        if captured:
            delta = rl.get_mouse_delta()
            self.yaw = (self.yaw + delta.x*.0024) % math.tau
            self.pitch = max(-1.45, min(1.45, self.pitch-delta.y*.0024))
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
                       reload=bool(down(k.KEY_R)), sprint=bool(down(k.KEY_LEFT_SHIFT)))

    def on_destroy(self):
        set_cursor_captured(False)
