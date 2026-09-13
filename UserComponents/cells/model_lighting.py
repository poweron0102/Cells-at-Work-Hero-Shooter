"""Shared directional cel lighting for articulated Raylib primitive models."""
import pyray as rl

VERTEX = '''#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
in vec4 vertexColor;
uniform mat4 mvp;
out vec4 shadedColor;
void main() {
    float n = dot(normalize(vertexNormal), normalize(vec3(-0.45, 0.8, 0.55)));
    float light = n > 0.55 ? 1.0 : (n > -0.1 ? 0.85 : 0.65);
    shadedColor = vec4(vertexColor.rgb * light, vertexColor.a);
    gl_Position = mvp * vec4(vertexPosition, 1.0);
}
'''
FRAGMENT = '''#version 330
in vec4 shadedColor;
out vec4 finalColor;
void main() { finalColor = shadedColor; }
'''

_shader = None


def begin():
    global _shader
    if _shader is None:
        _shader = rl.load_shader_from_memory(VERTEX, FRAGMENT)
    rl.begin_shader_mode(_shader)


def end():
    rl.end_shader_mode()


def release():
    global _shader
    if _shader is not None:
        rl.unload_shader(_shader)
        _shader = None
