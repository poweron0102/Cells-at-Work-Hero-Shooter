"""Toon (cel) shader compartilhado pelos personagens 3D.

Usa os nomes padrão do raylib (vertexPosition/vertexNormal/vertexColor, mvp, matModel,
matNormal, matView, colDiffuse) para funcionar direto com ``rl.draw_mesh``.

* cor = vertexColor (linear no GLB, convertido para sRGB aqui) x texture0 x colDiffuse;
* luz direcional fixa no mundo com três faixas suaves;
* sombra do cenário (``lighting.py``): na sombra de um prédio o corpo inteiro vai para a faixa
  escura, e em túneis/sob pontes o céu ocluído escurece e os postes aquecem;
* rim light suave no contorno;
* ``highlight`` (rgb, intensidade) para revelar/escudo: realça o contorno e tinge de leve.

Carregamento preguiçoso: nada de GPU acontece na importação.
"""
import pyray as rl

from . import lighting

VERTEX = '''#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
in vec2 vertexTexCoord;
in vec4 vertexColor;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform mat4 matView;
out vec3 fragNormal;
out vec3 fragViewNormal;
out vec3 fragViewPos;
out vec3 fragWorld;
out vec4 fragColor;
out vec2 fragUV;
void main() {
    vec3 n = normalize(mat3(matNormal) * vertexNormal);
    fragNormal = n;
    fragWorld = (matModel * vec4(vertexPosition, 1.0)).xyz;
    fragViewNormal = mat3(matView) * n;
    fragViewPos = (matView * matModel * vec4(vertexPosition, 1.0)).xyz;
    fragColor = vertexColor;
    fragUV = vertexTexCoord;
    gl_Position = mvp * vec4(vertexPosition, 1.0);
}
'''

FRAGMENT = '''#version 330
in vec3 fragNormal;
in vec3 fragViewNormal;
in vec3 fragViewPos;
in vec3 fragWorld;
in vec4 fragColor;
in vec2 fragUV;
uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec4 highlight;
uniform vec3 lightDir;
uniform vec4 probe;
out vec4 finalColor;
const vec3 SHADOW_TINT = vec3(0.80, 0.80, 0.94);
''' + lighting.GLSL + '''
void main() {
    vec3 LIGHT = normalize(lightDir);
    vec3 n = normalize(fragNormal);
    vec3 vn = normalize(fragViewNormal);
    if (!gl_FrontFacing) { n = -n; vn = -vn; }
    // Cores do GLB são lineares (spec glTF): volta para sRGB para manter a paleta anime.
    vec4 texel = texture(texture0, fragUV);
    vec3 base = pow(max(fragColor.rgb, vec3(0.0)), vec3(1.0/2.2)) * texel.rgb * colDiffuse.rgb;
    // Luz do cenário: no mundo usa o próprio fragmento; a arma em 1ª pessoa usa ``probe`` (olho).
    bool atProbe = probe.w > 0.5;
    vec3 P = atProbe ? probe.xyz : fragWorld;
    vec3 N = atProbe ? vec3(0.0, 1.0, 0.0) : n;
    float sunCast = sunVisibility(P, atProbe ? vec3(0.0, 1.0, 0.0) : SUN_DIR);
    float sky = skyVisibility(P, N);
    float open = smoothstep(0.02, 0.3, sky);
    float d = mix(-0.6, dot(n, LIGHT), sunCast);
    float lit = mix(0.62, 0.84, smoothstep(-0.32, -0.24, d));
    lit = mix(lit, 1.0, smoothstep(0.24, 0.32, d));
    vec3 shade = mix(SHADOW_TINT, vec3(1.0), smoothstep(0.62, 1.0, lit)) * lit;
    vec3 col = base * shade;
    vec3 v = normalize(-fragViewPos);
    float rim = 1.0 - max(dot(vn, v), 0.0);
    float rimBand = smoothstep(0.58, 0.72, rim);
    col += base * rimBand * 0.16 * clamp(d + 0.6, 0.0, 1.0);
    // Céu ocluído (túnel, sob ponte) escurece menos que o cenário: o herói continua legível.
    col *= mix(vec3(0.6, 0.56, 0.66), vec3(1.0), open);
    col += base * lampLight(P, N, sky) * 0.6;
    col = mix(col, highlight.rgb, clamp(rimBand * highlight.a * 1.2 + highlight.a * 0.18, 0.0, 1.0));
    finalColor = vec4(col, fragColor.a * texel.a * colDiffuse.a);
}
'''

WORLD_LIGHT = lighting.SUN

_shader = None
_highlight_loc = -1
_highlight = None
_light_loc = -1
_light = None
_probe_loc = -1
_probe = None
override = None  # shader de um passe especial (contorno/silhueta); None = toon


def shader():
    """Shader toon (carregado na primeira chamada; requer contexto OpenGL)."""
    global _shader, _highlight_loc, _highlight, _light_loc, _light, _probe_loc, _probe
    if override is not None:
        return override
    if _shader is None:
        _shader = rl.load_shader_from_memory(VERTEX, FRAGMENT)
        _highlight_loc = rl.get_shader_location(_shader, 'highlight')
        _light_loc = rl.get_shader_location(_shader, 'lightDir')
        _probe_loc = rl.get_shader_location(_shader, 'probe')
        _highlight = _light = _probe = None
        set_highlight(0.0, 0.0, 0.0, 0.0)
        set_light(*WORLD_LIGHT)
        set_probe(None)
        lighting.register(_shader)
    return _shader


def set_light(x, y, z):
    """Direção (para a luz) usada pelo sombreamento em faixas; só envia quando muda."""
    global _light
    value = (x, y, z)
    if _shader is None or value == _light or _light_loc < 0:
        return
    _light = value
    rl.set_shader_value(_shader, _light_loc, rl.ffi.new('float[3]', value),
                        rl.ShaderUniformDataType.SHADER_UNIFORM_VEC3)


def set_probe(position):
    """Ponto do mundo usado para a sombra do cenário em vez do fragmento (arma em 1ª pessoa,
    desenhada no espaço da câmera). ``None`` volta ao normal."""
    global _probe
    value = (0.0, 0.0, 0.0, 0.0) if position is None else (*position, 1.0)
    if _shader is None or value == _probe or _probe_loc < 0:
        return
    _probe = value
    rl.set_shader_value(_shader, _probe_loc, rl.ffi.new('float[4]', value),
                        rl.ShaderUniformDataType.SHADER_UNIFORM_VEC4)


def set_highlight(r, g, b, a):
    """Cor/intensidade do realce de contorno; só envia ao GPU quando muda."""
    global _highlight
    value = (r, g, b, a)
    if _shader is None or value == _highlight or _highlight_loc < 0:
        return
    _highlight = value
    rl.set_shader_value(_shader, _highlight_loc, rl.ffi.new('float[4]', value),
                        rl.ShaderUniformDataType.SHADER_UNIFORM_VEC4)


def begin():
    rl.begin_shader_mode(shader())


def end():
    rl.end_shader_mode()


def release():
    global _shader, _highlight, _light, _probe
    if _shader is not None:
        lighting.unregister(_shader)
        rl.unload_shader(_shader)
        _shader = None
        _highlight = None
        _light = None
        _probe = None
