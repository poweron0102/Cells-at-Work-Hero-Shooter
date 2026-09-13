"""Local input and first-person camera; motion is simulated by the host."""
import math
import pyray as rl
from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3, Quaternion
from .combat import direction


class PlayerInput(Component):
    def __init__(self, arena, camera):
        self.arena, self.camera = arena, camera
        self.yaw = self.pitch = 0
        self.paused = False
        self.send_timer = 0
        self.last_slot = None
        self.pending_jump = False

    def loop(self):
        net = self.game.session
        slot = net.local_slot
        if slot is None or slot not in self.arena.actors:
            return
        actor = self.arena.actors[slot]
        if slot != self.last_slot:
            self.yaw = actor.yaw
            self.last_slot = slot
        if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
            self.paused = not self.paused
        captured = not self.paused and actor.alive and not net.error
        if captured:
            if not rl.is_cursor_hidden():
                rl.disable_cursor()
            delta = rl.get_mouse_delta()
            self.yaw = (self.yaw + delta.x*.0024) % math.tau
            self.pitch = max(-1.45, min(1.45, self.pitch-delta.y*.0024))
        else:
            rl.enable_cursor()
        self.camera.transform.position = actor.transform.position+Vec3(0, .56, 0)
        self.camera.transform.rotation = (Quaternion.from_axis_angle(Vec3(0, 1, 0), -self.yaw)
                                          * Quaternion.from_axis_angle(Vec3(1, 0, 0), self.pitch))
        down = lambda key: captured and rl.is_key_down(key)
        k = rl.KeyboardKey
        self.pending_jump = self.pending_jump or (captured and rl.is_key_pressed(k.KEY_SPACE))
        command = dict(x=float(down(k.KEY_D))-float(down(k.KEY_A)), z=float(down(k.KEY_W))-float(down(k.KEY_S)),
                       yaw=self.yaw, pitch=self.pitch, jump=self.pending_jump,
                       fire=captured and rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT),
                       secondary=captured and rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_RIGHT),
                       ability=bool(down(k.KEY_Q)), ultimate=bool(down(k.KEY_F)), interact=bool(down(k.KEY_E)),
                       reload=bool(down(k.KEY_R)), sprint=bool(down(k.KEY_LEFT_SHIFT)))
        self.send_timer -= self.game.delta_time
        if net.is_server or self.send_timer <= 0:
            net.input(command)
            self.pending_jump = False
            self.send_timer = 1/30

    def on_destroy(self):
        rl.enable_cursor()
