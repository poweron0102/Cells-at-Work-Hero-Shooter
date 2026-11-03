"""Free flight and same-frame, HUD-free reference captures."""
from datetime import datetime
import json
import math
from pathlib import Path

import pyray as rl
from EasyCells3D.Components import Camera3D
from EasyCells3D.Geometry import Quaternion, Vec3
from .cursor import set_cursor_captured


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


class ReferenceCamera(Camera3D):
    def __init__(self):
        super().__init__(vfov=60)
        self.output = Path("capturas").resolve()
        self.yaw = self.pitch = 0.0
        self.captured = True
        self.show_help = True
        self.pending_capture = False
        self.status = ""
        self.status_until = 0.0
        self.frames = self.frame_limit = 0
        self.capture_on_exit = False

    def init(self):
        super().init()
        self.reset_pose()
        set_cursor_captured(True)

    def reset_pose(self):
        self.transform.position = Vec3(19, 5.3, 12)
        self.yaw, self.pitch = math.radians(-55), math.radians(-4.5)
        self.vfov = 60
        self.update_rotation()

    def update_rotation(self):
        self.transform.rotation = (
            Quaternion.from_axis_angle(Vec3(0, 1, 0), -self.yaw)
            * Quaternion.from_axis_angle(Vec3(1, 0, 0), self.pitch)
        )

    def loop(self):
        k = rl.KeyboardKey
        self.frames += 1
        if rl.is_key_pressed(k.KEY_ESCAPE):
            self.captured = not self.captured
            set_cursor_captured(self.captured)
        elif not self.captured and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.captured = True
            set_cursor_captured(True)
        if not rl.is_window_focused():
            self.captured = False
            set_cursor_captured(False)
        if rl.is_key_pressed(k.KEY_F1):
            self.show_help = not self.show_help
        if rl.is_key_pressed(k.KEY_R):
            self.reset_pose()
        if self.captured:
            delta = rl.get_mouse_delta()
            self.yaw = (self.yaw + delta.x * .0024) % math.tau
            self.pitch = max(math.radians(-89), min(math.radians(89),
                                                   self.pitch - delta.y * .0024))
            self.update_rotation()
            down = lambda key: float(rl.is_key_down(key))
            movement = (self.transform.forward * (down(k.KEY_W) - down(k.KEY_S))
                        + self.transform.right * (down(k.KEY_D) - down(k.KEY_A))
                        + Vec3(0, down(k.KEY_E) + down(k.KEY_SPACE)
                               - down(k.KEY_Q) - down(k.KEY_LEFT_CONTROL), 0))
            speed = 24 if rl.is_key_down(k.KEY_LEFT_SHIFT) else 8
            if rl.is_key_down(k.KEY_LEFT_ALT):
                speed *= .2
            if movement.magnitude() > 0:
                self.transform.position += movement.normalize() * speed * min(self.game.delta_time, .1)
            self.vfov = max(20, min(100, self.vfov - rl.get_mouse_wheel_move() * 2))
        if rl.is_key_pressed(k.KEY_P):
            self.pending_capture = True
        if self.frame_limit and self.frames >= self.frame_limit:
            self.pending_capture |= self.capture_on_exit
            self.game.running = False

    def update_rl_camera(self):
        # Use the pose updated this frame rather than Item's earlier transform cache.
        self.rl_camera.position = self.transform.position.to_raylib()
        self.rl_camera.target = (self.transform.position + self.transform.forward).to_raylib()
        self.rl_camera.up = self.transform.up.to_raylib()
        self.rl_camera.fovy = self.vfov
        self.rl_camera.projection = self.projection

    def render(self):
        width, height = rl.get_screen_width(), rl.get_screen_height()
        if width <= 0 or height <= 0:
            return
        if (self.render_target is None or self.render_target.texture.width != width
                or self.render_target.texture.height != height):
            if self.render_target is not None:
                rl.unload_render_texture(self.render_target)
            self.render_target = rl.load_render_texture(width, height)
        self.update_rl_camera()
        rl.begin_texture_mode(self.render_target)
        rl.clear_background(self.game.background_color)
        rl.begin_mode_3d(self.rl_camera)
        for renderable in self.renderables:
            renderable.render()
        rl.end_mode_3d()
        rl.end_texture_mode()
        if self.pending_capture:
            self.pending_capture = False
            try:
                self.save_reference()
            except (OSError, RuntimeError) as exc:
                self.status = f"Falha ao salvar: {exc}"
                print(self.status, flush=True)
            self.status_until = rl.get_time() + 6
        rl.draw_texture_pro(self.render_target.texture, rl.Rectangle(0, 0, width, -height),
                            rl.Rectangle(0, 0, width, height), rl.Vector2(0, 0), 0, rl.WHITE)
        if self.show_help:
            self.draw_help(width)

    def save_reference(self):
        stamp = datetime.now().astimezone()
        folder = self.output / stamp.strftime("%Y-%m-%d_%H-%M-%S_%f")
        folder.mkdir(parents=True, exist_ok=False)
        image = rl.load_image_from_texture(self.render_target.texture)
        try:
            rl.image_flip_vertical(image)
            if not rl.export_image(image, str(folder / "print.png")):
                raise RuntimeError("nao foi possivel exportar print.png")
        finally:
            rl.unload_image(image)
        camera = self.rl_camera
        rotation = self.transform.rotation
        data = {
            "schema_version": 1,
            "created_at": stamp.isoformat(),
            "map": "BairroArterial",
            "model": "Assets/Maps/BairroArterial/BairroArterial.glb",
            "image": "print.png",
            "coordinate_system": "World metres; +Y up; forward at zero yaw is -Z. Blender: (x, -z, y).",
            "position": xyz(camera.position),
            "target": xyz(camera.target),
            "up": xyz(camera.up),
            "forward": xyz(self.transform.forward),
            "angles_degrees": {"yaw": math.degrees(self.yaw), "pitch": math.degrees(self.pitch), "roll": 0},
            "angle_convention": "Yaw positive turns right from -Z; pitch positive looks up; roll is zero.",
            "rotation_quaternion_xyzw": [rotation.x, rotation.y, rotation.z, rotation.w],
            "projection": "PERSP",
            "vertical_fov_degrees": self.vfov,
            "resolution": [self.render_target.texture.width, self.render_target.texture.height],
        }
        (folder / "camera.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        x, y, z = data["position"]
        (folder / "referencia.txt").write_text(
            f"Bairro Arterial | {data['created_at']}\nImagem: print.png\n"
            f"Posicao (metros): X={x:.6f}, Y={y:.6f}, Z={z:.6f}\n"
            f"Angulos (graus): yaw={math.degrees(self.yaw):.6f}, "
            f"pitch={math.degrees(self.pitch):.6f}, roll=0\n"
            f"Yaw 0 olha para -Z; positivo vira a direita. Pitch positivo olha para cima.\n"
            f"FOV vertical: {self.vfov:.2f} graus\n"
            f"Resolucao: {data['resolution'][0]} x {data['resolution'][1]}\n"
            f"Coordenadas Blender (X, Y, Z): ({x:.6f}, {-z:.6f}, {y:.6f})\n"
            "Dados completos para reconstruir a camera: camera.json\n", encoding="utf-8")
        self.status = f"Salvo: {folder.name} (print + camera.json + referencia.txt)"
        print(f"Referencia salva em {folder}", flush=True)

    def draw_help(self, width):
        rl.draw_rectangle(12, 12, min(width - 24, 930), 112, rl.Color(15, 21, 29, 220))
        position = self.transform.position
        lines = [
            "CAMERA LIVRE | P: salvar print e camera | F1: ocultar painel",
            "WASD: voar | E/Espaco: subir | Q/Ctrl: descer | Shift: rapido | Alt: preciso",
            "Mouse: olhar | Roda: FOV | Esc: soltar/prender mouse | Clique: prender | R: inicio",
            f"XYZ: {position.x:.2f}, {position.y:.2f}, {position.z:.2f} | "
            f"Yaw: {math.degrees(self.yaw):.1f} | Pitch: {math.degrees(self.pitch):.1f} | FOV: {self.vfov:.0f}",
        ]
        for index, line in enumerate(lines):
            rl.draw_text(line, 22, 22 + index * 24, 18, rl.RAYWHITE)
        if rl.get_time() < self.status_until:
            rl.draw_rectangle(12, 136, max(1, width - 24), 34, rl.Color(15, 21, 29, 220))
            rl.draw_text(self.status, 22, 144, 16, rl.RAYWHITE)

    def on_destroy(self):
        if self.render_target is not None:
            rl.unload_render_texture(self.render_target)
            self.render_target = None
        set_cursor_captured(False)
        super().on_destroy()
