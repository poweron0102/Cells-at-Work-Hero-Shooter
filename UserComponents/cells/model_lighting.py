"""Toon (cel) shader compartilhado pelos personagens 3D.

Usa os nomes padrão do raylib (vertexPosition/vertexNormal/vertexColor, mvp, matModel,
matNormal, matView, colDiffuse) para funcionar direto com ``rl.draw_mesh``.

* cor = vertexColor (linear no GLB, convertido para sRGB aqui) x textura de cor (sRGB, quando
  a malha tem uma; a textura branca 1x1 padrão do raylib não é amostrada) x colDiffuse (tint);
* luz direcional fixa no mundo com três faixas suaves;
* sombra do cenário (``lighting.py``): na sombra de um prédio o corpo inteiro vai para a faixa
  escura, e em túneis/sob pontes o céu ocluído escurece e os postes aquecem;
* rim light suave no contorno;
* ``highlight`` (rgb, intensidade) para revelar/escudo: realça o contorno e tinge de leve;
* skinning na GPU (``SKIN_GLSL``) para os personagens com esqueleto: o raylib deste projeto só
  deforma na CPU (e reenvia a malha a cada desenho), caro demais para as multidões.

Carregamento preguiçoso: nada de GPU acontece na importação.
"""
import pyray as rl
import raylib as _raw

from . import lighting

MAX_BONES = 48
# Índices/pesos de osso nas posições 7 e 8 do VAO (models._Rig envia esses buffers).
# ``skinned`` = 0 deixa a malha como está (cenário, armas, personagens por partes).
SKIN_GLSL = '''
layout(location = 7) in vec4 vertexBoneIndices;
layout(location = 8) in vec4 vertexBoneWeights;
uniform mat4 boneMatrices[48];
uniform float skinned;
mat4 skinMatrix() {
    if (skinned < 0.5) return mat4(1.0);
    ivec4 i = ivec4(vertexBoneIndices + 0.5);
    vec4 w = vertexBoneWeights;
    return boneMatrices[i.x] * w.x + boneMatrices[i.y] * w.y + boneMatrices[i.z] * w.z + boneMatrices[i.w] * w.w;
}
'''

VERTEX = '''#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
in vec4 vertexColor;
in vec2 vertexTexCoord;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform mat4 matView;
out vec3 fragNormal;
out vec3 fragViewNormal;
out vec3 fragViewPos;
out vec3 fragWorld;
out vec4 fragColor;
out vec2 fragTexCoord;
''' + SKIN_GLSL + '''
void main() {
    mat4 sk = skinMatrix();
    vec4 pos = sk * vec4(vertexPosition, 1.0);
    vec3 n = normalize(mat3(matNormal) * (mat3(sk) * vertexNormal));
    fragNormal = n;
    fragWorld = (matModel * pos).xyz;
    fragViewNormal = mat3(matView) * n;
    fragViewPos = (matView * matModel * pos).xyz;
    fragColor = vertexColor;
    fragTexCoord = vertexTexCoord;
    gl_Position = mvp * pos;
}
'''

FRAGMENT = '''#version 330
in vec3 fragNormal;
in vec3 fragViewNormal;
in vec3 fragViewPos;
in vec3 fragWorld;
in vec4 fragColor;
in vec2 fragTexCoord;
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
    vec3 base = pow(max(fragColor.rgb, vec3(0.0)), vec3(1.0/2.2)) * colDiffuse.rgb;
    // Malhas sem UV (cor por vértice) usam a textura 1x1 padrão: não amostra coordenadas indefinidas.
    if (textureSize(texture0, 0).x > 1) base *= texture(texture0, fragTexCoord).rgb;
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
    finalColor = vec4(col, fragColor.a * colDiffuse.a);
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


_skin_locs = {}


def set_skin(target, matrices=None, count=0):
    """Liga o skinning na GPU em ``target`` com ``count`` matrizes (ponteiro ``Matrix *``) ou
    desliga (``None``). Devolve False se o shader não tem skinning."""
    locs = _skin_locs.get(target.id)
    if locs is None:
        locs = _skin_locs[target.id] = (rl.get_shader_location(target, 'boneMatrices'),
                                        rl.get_shader_location(target, 'skinned'))
    bones, flag = locs
    if flag < 0:
        return False
    rl.rl_enable_shader(target.id)  # rlSetUniform* escrevem no programa ativo
    if matrices is not None and bones >= 0:
        _raw.rlSetUniformMatrices(bones, matrices, count)
    _raw.rlSetUniform(flag, rl.ffi.new('float *', 1.0 if matrices is not None else 0.0),
                      rl.ShaderUniformDataType.SHADER_UNIFORM_FLOAT, 1)
    return True


def forget_skin(target):
    """Esquece as posições de uniform de um shader descarregado (o id pode ser reutilizado)."""
    _skin_locs.pop(target.id, None)


def begin():
    rl.begin_shader_mode(shader())


def end():
    rl.end_shader_mode()


def release():
    global _shader, _highlight, _light, _probe
    if _shader is not None:
        lighting.unregister(_shader)
        forget_skin(_shader)
        rl.unload_shader(_shader)
        _shader = None
        _highlight = None
        _light = None
        _probe = None
