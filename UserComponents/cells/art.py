"""Procedural art adapted from Cellular-Odyssey-2; no dependency on that checkout."""
from array import array
import math
import pyray as rl
from EasyCells3D.Geometry import Vec3

def color(r, g, b, a=255):
    return rl.Color(r, g, b, a)


CREAM = color(244, 228, 191)
INK = color(34, 56, 58)
TEAL = color(54, 124, 122)
RED = color(200, 64, 59)
GOLD = color(229, 177, 80)
WHITE = color(245, 243, 229)
SKY = color(199, 220, 214)
def tint(c, factor):
    return color(int(c.r * factor), int(c.g * factor), int(c.b * factor), c.a)


def box(position: Vec3, size: Vec3, c):
    rl.draw_cube_v(position.to_raylib(), size.to_raylib(), c)


def sphere(position: Vec3, radius: float, c):
    rl.draw_sphere_ex(position.to_raylib(), radius, 8, 12, c)


def cylinder(a: Vec3, b: Vec3, radius: float, c, end_radius=None):
    rl.draw_cylinder_ex(a.to_raylib(), b.to_raylib(), radius,
                        radius if end_radius is None else end_radius, 10, c)


class MeshBuilder:
    """Batch boxes into one mesh with baked face lighting."""
    def __init__(self):
        self.vertices = array("f")
        self.colors = bytearray()

    def box(self, center: Vec3, size: Vec3, c):
        h = size / 2
        faces = (
            (Vec3(0, 1, 0), Vec3(1, 0, 0), Vec3(0, 0, -1), 1.),
            (Vec3(0, -1, 0), Vec3(1, 0, 0), Vec3(0, 0, 1), .5),
            (Vec3(1, 0, 0), Vec3(0, 0, -1), Vec3(0, 1, 0), .78),
            (Vec3(-1, 0, 0), Vec3(0, 0, 1), Vec3(0, 1, 0), .63),
            (Vec3(0, 0, 1), Vec3(1, 0, 0), Vec3(0, 1, 0), .86),
            (Vec3(0, 0, -1), Vec3(-1, 0, 0), Vec3(0, 1, 0), .7),
        )
        for normal, u, v, light in faces:
            face_center = center + Vec3(normal.x * h.x, normal.y * h.y, normal.z * h.z)
            u = Vec3(u.x * h.x, u.y * h.y, u.z * h.z)
            v = Vec3(v.x * h.x, v.y * h.y, v.z * h.z)
            corners = (face_center - u - v, face_center + u - v,
                       face_center + u + v, face_center - u + v)
            shade = tint(c, light)
            for index in (0, 1, 2, 0, 2, 3):
                self.vertices.extend(corners[index].to_tuple)
                self.colors.extend((shade.r, shade.g, shade.b, shade.a))

    def upload(self):
        mesh = rl.Mesh()
        mesh.vertexCount = len(self.vertices) // 3
        mesh.triangleCount = mesh.vertexCount // 3
        vertex_bytes = self.vertices.tobytes()
        mesh.vertices = rl.ffi.cast("float *", rl.mem_alloc(len(vertex_bytes)))
        rl.ffi.memmove(mesh.vertices, vertex_bytes, len(vertex_bytes))
        mesh.colors = rl.ffi.cast("unsigned char *", rl.mem_alloc(len(self.colors)))
        rl.ffi.memmove(mesh.colors, bytes(self.colors), len(self.colors))
        rl.upload_mesh(mesh, False)
        return rl.load_model_from_mesh(mesh)


