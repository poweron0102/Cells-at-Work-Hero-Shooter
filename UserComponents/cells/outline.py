"""Contorno e silhueta dos personagens (no lugar das barrinhas sobre a cabeça).

* **Contorno**: casca invertida. A malha é desenhada de novo, inflada em espaço de tela ao longo
  da normal (largura constante em pixels), só com as faces de trás. Inimigos ganham um contorno
  vermelho fino; atrás da parede o teste de profundidade esconde o contorno junto com o modelo.
* **Silhueta**: desenhada ANTES dos personagens, só onde algo do cenário está na frente
  (``glDepthFunc(GL_GREATER)`` sem gravar profundidade). Depois o personagem é desenhado por
  cima normalmente, então a silhueta só sobra nas partes escondidas. Aliados sempre; inimigos
  quando revelados/marcados. Sem acesso ao glDepthFunc, cai para "atrás da parede inteira".

Os dois passes trocam o shader do toon via ``model_lighting.override`` (vale também para a
arma montada na mão).
"""
import ctypes
import math
import sys

import pyray as rl

from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3
from . import model_lighting
from .catalog import HEROES

OUTLINE_VS = '''#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
uniform mat4 mvp;
uniform vec2 screen;
uniform float width;
''' + model_lighting.SKIN_GLSL + '''
void main() {
    mat4 sk = skinMatrix();
    vec4 pos = mvp * (sk * vec4(vertexPosition, 1.0));
    vec4 nrm = mvp * vec4(mat3(sk) * vertexNormal, 0.0);
    vec2 dir = nrm.xy;
    float len = length(dir);
    dir = len > 1e-5 ? dir / len : vec2(0.0);
    pos.xy += dir * width * 2.0 / screen * pos.w;
    pos.z += 0.00002 * pos.w;
    gl_Position = pos;
}
'''

OUTLINE_FS = '''#version 330
uniform vec4 color;
out vec4 finalColor;
void main() { finalColor = color; }
'''

SILHOUETTE_VS = '''#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform mat4 matView;
out vec3 viewNormal;
out vec3 viewPos;
''' + model_lighting.SKIN_GLSL + '''
void main() {
    mat4 sk = skinMatrix();
    vec4 p = sk * vec4(vertexPosition, 1.0);
    viewNormal = mat3(matView) * normalize(mat3(matNormal) * (mat3(sk) * vertexNormal));
    viewPos = (matView * matModel * p).xyz;
    gl_Position = mvp * p;
}
'''

SILHOUETTE_FS = '''#version 330
in vec3 viewNormal;
in vec3 viewPos;
uniform vec4 color;
out vec4 finalColor;
void main() {
    vec3 n = normalize(viewNormal);
    if (!gl_FrontFacing) n = -n;
    float rim = 1.0 - abs(dot(n, normalize(-viewPos)));
    float edge = smoothstep(0.45, 0.85, rim);
    vec3 col = mix(color.rgb * 0.55, min(color.rgb * 1.25 + 0.12, vec3(1.0)), edge);
    finalColor = vec4(col, color.a * mix(0.55, 1.0, edge));
}
'''

ENEMY = (1.0, 0.30, 0.34)
ALLY = (0.16, 0.87, 0.82)
GL_LEQUAL, GL_GREATER = 0x0203, 0x0204

_state = {}


def _depth_func():
    """glDepthFunc do contexto atual (GL 1.1, exportado pelo opengl32 no Windows)."""
    if 'depth' not in _state:
        fn = None
        try:
            if sys.platform == 'win32':
                fn = ctypes.WinDLL('opengl32').glDepthFunc
            elif sys.platform == 'darwin':
                fn = ctypes.CDLL('/System/Library/Frameworks/OpenGL.framework/OpenGL').glDepthFunc
            else:
                fn = ctypes.CDLL('libGL.so.1').glDepthFunc
            fn.argtypes, fn.restype = [ctypes.c_uint], None
        except (OSError, AttributeError):
            fn = None
        _state['depth'] = fn
    return _state['depth']


def _shader(key):
    if key not in _state:
        vs, fs = (OUTLINE_VS, OUTLINE_FS) if key == 'outline' else (SILHOUETTE_VS, SILHOUETTE_FS)
        shader = rl.load_shader_from_memory(vs, fs)
        names = ('color', 'screen', 'width') if key == 'outline' else ('color',)
        _state[key] = (shader, {n: rl.get_shader_location(shader, n) for n in names})
    return _state[key]


def _set(shader, loc, value, kind):
    if loc < 0:
        return
    if kind == 'float':
        rl.set_shader_value(shader, loc, rl.ffi.new('float *', value), rl.ShaderUniformDataType.SHADER_UNIFORM_FLOAT)
        return
    size = len(value)
    rl.set_shader_value(shader, loc, rl.ffi.new(f'float[{size}]', value),
                        getattr(rl.ShaderUniformDataType, f'SHADER_UNIFORM_VEC{size}'))


def draw_outline(model, args, rgb, width=2.4):
    """Redesenha ``model.draw(*args)`` como casca invertida (só faces de trás) na cor ``rgb``."""
    shader, locs = _shader('outline')
    w, h = rl.get_render_width(), rl.get_render_height()
    _set(shader, locs['screen'], (float(w), float(h)), 'vec')
    _set(shader, locs['width'], width * h / 720, 'float')
    _set(shader, locs['color'], (*rgb, 1.0), 'vec')
    model_lighting.override = shader
    try:
        model.draw(*args, cull='front')
    finally:
        model_lighting.override = None


def draw_silhouette(model, args, rgb, alpha=.8, occluded_only=True):
    shader, locs = _shader('silhouette')
    _set(shader, locs['color'], (*rgb, alpha), 'vec')
    depth = _depth_func() if occluded_only else None
    rl.rl_draw_render_batch_active()
    rl.rl_disable_depth_mask()
    if depth:
        depth(GL_GREATER)
    elif occluded_only is None:
        rl.rl_disable_depth_test()
    model_lighting.override = shader
    try:
        model.draw(*args, cull='back')
    finally:
        model_lighting.override = None
        rl.rl_draw_render_batch_active()
        if depth:
            depth(GL_LEQUAL)
        rl.rl_enable_depth_test()
        rl.rl_enable_depth_mask()


def release():
    for key in ('outline', 'silhouette'):
        if key in _state:
            shader = _state.pop(key)[0]
            model_lighting.forget_skin(shader)
            rl.unload_shader(shader)


class SilhouettePass(Renderable3D):
    """Roda depois do cenário e antes dos personagens (``render_order`` entre os dois)."""
    render_order = 5

    def __init__(self, arena):
        self.arena = arena

    def render(self):
        from .visuals import CombatantVisual, model
        a = self.arena
        session = self.game.session
        me = a.actors.get(session.local_slot)
        if me is None:
            return
        cam = self.camera.transform.position if self.camera else None
        exact = _depth_func() is not None
        for target in a.actors.values():
            if target is me or not target.alive:
                continue
            ally = target.team == me.team
            receptor = (me.hero == 'neutrophil' and not ally and me.alive
                        and target.health.value < HEROES[target.hero].health*.5
                        and (cam is None or (target.transform.position-cam).magnitude() < 40))
            if not ally and not (target.reveal > 0 or target.marked > 0 or me.reveal > 0 or receptor):
                continue
            visual = target.GetComponent(CombatantVisual)
            if visual is None or visual.camera_inside():
                continue
            if not exact:
                # Sem glDepthFunc: só quando o tronco inteiro está atrás do cenário.
                chest = (target.transform.position+Vec3(0, .3, 0)).to_tuple
                if cam is None or a.clear_line(cam.to_tuple, chest):
                    continue
            draw_silhouette(model(target.hero), visual.prepare(), ALLY if ally else ENEMY,
                            .75 if ally else .9, True if exact else None)

    def on_destroy(self):
        super().on_destroy()
        release()
