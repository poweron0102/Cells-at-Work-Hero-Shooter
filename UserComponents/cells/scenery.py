"""Bairro Arterial: arte exportada do Blender + shader de padroes procedurais.

O GLB guarda cor por vertice e, em UV.x, o id do padrao (tijolo, pedra,
ladrilho, madeira, agua animada...). O shader desenha os padroes no espaco do
mundo e aplica a iluminacao de ``lighting.py`` (sol com sombra projetada em
faixas, ceu ocluido em tuneis/sob pontes, postes), contorno de nanquim, ceu em
degrade e neblina quente que brilha na direcao do sol.

Contorno: um passe desenha so normal + distancia do mapa numa textura RGBA8 do
tamanho da tela. O shader principal le os
vizinhos de cada pixel e escurece onde a superficie termina (silhueta, do lado de
quem esta na frente) ou dobra (quina), como o traco dos cenarios do anime.
Carregado sob demanda: servidores e testes sem GPU nunca abrem o modelo.
"""
import pyray as rl
from EasyCells3D.Components.Camera3D import Renderable3D
from . import lighting
from . import layout

FOG = (0.955, 0.915, 0.835)

CHAIN_GLSL = '''
// Alambrado (padrao 18): losangos de arame de ~20 cm; entre os fios a tela e vazada.
bool chainHole(vec3 p, vec3 n) {
    vec3 a = abs(n);
    vec2 uv = a.y > 0.7 ? p.xz : (a.x > a.z ? vec2(p.z, p.y) : p.xy);
    vec2 q = uv * 5.0;
    vec2 f = fract(vec2(q.x + q.y, q.x - q.y) * 0.7071);
    return min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y)) > 0.1;
}
'''

VERTEX = '''#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
in vec4 vertexColor;
uniform mat4 mvp;
uniform mat4 matModel;
invariant gl_Position;
out vec3 wPos;
out vec3 wNor;
out vec4 vCol;
out float vPat;
void main() {
    vec4 w = matModel * vec4(vertexPosition, 1.0);
    wPos = w.xyz;
    wNor = normalize(mat3(matModel) * vertexNormal);
    vCol = vertexColor;
    vPat = vertexTexCoord.x;
    gl_Position = mvp * vec4(vertexPosition, 1.0);
}
'''

FRAGMENT = '''#version 330
in vec3 wPos;
in vec3 wNor;
in vec4 vCol;
in float vPat;
uniform vec4 colDiffuse;
uniform vec3 viewPos;
uniform float time;
uniform vec3 fogColor;
uniform float fogDensity;
uniform sampler2D inkBuf;   // passe de contorno: normal + distancia (ver INK_PACK)
uniform vec4 inkView;       // x, y = origem do viewport; z = ligado; w = raio em pixels
out vec4 finalColor;
''' + lighting.GLSL + '''

''' + CHAIN_GLSL + '''
// Buffer de contorno em RGBA8: rg = normal octaédrica, ba = distância em log (16 bits).
const float INK_NEAR = 0.05;
const float INK_LOG = 11.2898;  // log(4000 / 0.05)
vec3 inkNormal(vec2 e) {
    e = e * 2.0 - 1.0;
    vec3 n = vec3(e, 1.0 - abs(e.x) - abs(e.y));
    float t = max(-n.z, 0.0);
    n.x += n.x >= 0.0 ? -t : t;
    n.y += n.y >= 0.0 ? -t : t;
    return normalize(n);
}
// Devolve (normal, 1/distancia); ceu = distancia maxima.
vec4 inkAt(ivec2 p) {
    ivec2 last = textureSize(inkBuf, 0) - 1;
    vec4 raw = texelFetch(inkBuf, clamp(p, ivec2(0), last), 0);
    float t = floor(raw.b * 255.0 + 0.5) * 256.0 + floor(raw.a * 255.0 + 0.5);
    float dist = INK_NEAR * exp(t / 65535.0 * INK_LOG);
    return vec4(inkNormal(raw.rg), 1.0 / dist);
}
// Silhueta: o vizinho esta mais longe do que o plano deste pixel preve (a superficie
// acaba aqui). 1/distancia e afim na tela para planos, entao a previsao e exata no
// chao em angulo rasante e nao gera traco falso. Ceu = 0 (infinitamente longe).
float inkSilhouette(float i0, vec4 a, vec4 b) {
    float pa = max(2.0 * i0 - b.a, 1e-4);
    float pb = max(2.0 * i0 - a.a, 1e-4);
    // Relativo: quanto o vizinho real está atrás do previsto, em fração da distância.
    return max(pa / max(a.a, 1e-4), pb / max(b.a, 1e-4)) - 1.0;
}
float inkEdge(ivec2 px, out float d0) {
    int r = int(inkView.w);
    vec4 me = inkAt(px);
    vec4 l = inkAt(px - ivec2(r, 0)), rr = inkAt(px + ivec2(r, 0));
    vec4 dn = inkAt(px - ivec2(0, r)), up = inkAt(px + ivec2(0, r));
    d0 = 1.0 / max(me.a, 1e-4);
    float sil = max(inkSilhouette(me.a, l, rr), inkSilhouette(me.a, dn, up));
    float edge = smoothstep(0.035, 0.08, sil);
    // Quina: a normal muda em relacao ao vizinho da direita/de cima (um lado so: traco de 1 px).
    float bend = 1.0 - min(dot(me.rgb, rr.rgb), dot(me.rgb, up.rgb));
    return max(edge, smoothstep(0.18, 0.4, bend));
}

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
vec2 hash2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
vec2 voronoi(vec2 x) {
    vec2 n = floor(x), f = fract(x), mg = vec2(0), mr = vec2(0);
    float md = 8.0, id = 0.0;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
        vec2 g = vec2(i, j);
        vec2 r = g + hash2(n + g) * 0.85 - f;
        float d = dot(r, r);
        if (d < md) { md = d; mr = r; mg = g; id = hash(n + g); }
    }
    md = 8.0;
    for (int j = -2; j <= 2; j++) for (int i = -2; i <= 2; i++) {
        vec2 g = mg + vec2(i, j);
        vec2 r = g + hash2(n + g) * 0.85 - f;
        if (dot(mr - r, mr - r) > 0.00001) md = min(md, dot(0.5 * (mr + r), normalize(r - mr)));
    }
    return vec2(md, id);
}
vec2 planar(vec3 p, vec3 n) {
    vec3 a = abs(n);
    if (a.y > 0.7) return p.xz;
    if (a.x > a.z) return vec2(p.z, p.y);
    return p.xy;
}
vec3 bricks(vec2 uv, vec3 col, vec2 size, float mortar, float vary) {
    vec2 b = uv / size;
    float row = floor(b.y);
    b.x += mod(row, 2.0) * 0.5;
    vec2 f = fract(b);
    float r = hash(floor(b));
    col *= 1.0 - vary * 0.5 + vary * r;
    float m = max(1.0 - smoothstep(0.0, mortar, min(f.x, 1.0 - f.x) * size.x),
                  1.0 - smoothstep(0.0, mortar, min(f.y, 1.0 - f.y) * size.y));
    return mix(col, col * 0.66, m);
}

void main() {
    ivec2 inkPx = ivec2(gl_FragCoord.xy - inkView.xy);
    vec3 n = normalize(wNor);
    vec3 col = vCol.rgb * colDiffuse.rgb;
    int pat = int(floor(vPat));
    vec2 uv = planar(wPos, n);
    bool lit = true;
    if (pat == 18 && chainHole(wPos, n)) discard;
    if (pat == 1) {
        col = bricks(uv, col, vec2(0.52, 0.22), 0.03, 0.22);
    } else if (pat == 2) {
        vec2 v = voronoi(uv * 1.15);
        col *= 0.9 + 0.16 * v.y;
        col = mix(col, col * vec3(1.05, 0.93, 0.9), step(0.78, v.y));
        col = mix(col, col * 0.58, 1.0 - smoothstep(0.015, 0.055, v.x));
    } else if (pat == 3) {
        vec2 f = fract(uv);
        float r = hash(floor(uv));
        if (r > 0.9) col *= vec3(1.0, 0.8, 0.78);
        else if (r > 0.83) col *= vec3(1.02, 0.96, 0.72);
        else if (r > 0.79) col *= vec3(0.86, 0.9, 1.02);
        col *= 0.96 + 0.06 * hash(floor(uv) + 3.0);
        float l = max(1.0 - smoothstep(0.0, 0.035, min(f.x, 1.0 - f.x)), 1.0 - smoothstep(0.0, 0.035, min(f.y, 1.0 - f.y)));
        col = mix(col, col * 0.78, l);
    } else if (pat == 4) {
        float rowv = uv.y * 4.0;
        float row = floor(rowv);
        float seg = floor(uv.x * 0.45 + hash(vec2(row, 1.0)) * 3.0);
        col *= 0.88 + 0.18 * hash(vec2(row, seg));
        float l = 1.0 - smoothstep(0.0, 0.07, min(fract(rowv), 1.0 - fract(rowv)));
        col = mix(col, col * 0.7, l);
        col *= 0.96 + 0.06 * noise(vec2(uv.x * 6.0, rowv * 0.5));
    } else if (pat == 5) {
        vec2 q = wPos.xz * 0.35 + vec2(time * 0.22, 0.0);
        float w = noise(q * 2.0) * 0.6 + noise(q * 5.0 - vec2(0.0, time * 0.3)) * 0.4;
        col = mix(col * 0.9, col * 1.14, w);
        float sparkle = smoothstep(0.82, 0.9, noise(q * 9.0 + time * 0.5));
        col += vec3(0.18) * sparkle;
        vec3 v = normalize(viewPos - wPos);
        col = mix(col, vec3(0.93, 0.97, 0.92), pow(1.0 - max(v.y, 0.0), 4.0) * 0.5);
        lit = false;
    } else if (pat == 6) {
        col = bricks(uv + vec2(hash(vec2(floor(uv.y / 0.45), 7.0)), 0.0), col, vec2(0.95, 0.45), 0.035, 0.3);
    } else if (pat == 7) {
        col *= 0.95 + 0.07 * noise(uv * 0.7) + 0.03 * noise(uv * 4.0);
    } else if (pat == 8 || pat == 17) {
        vec2 f = fract(uv * vec2(1.2, 0.9));
        float fr = max(1.0 - step(0.06, min(f.x, 1.0 - f.x)), 1.0 - step(0.06, min(f.y, 1.0 - f.y)));
        col = mix(col, col * 1.25, 0.35 * fract(uv.y * 0.25 + uv.x * 0.15));
        if (pat == 8) col = mix(col, vec3(0.97, 0.96, 0.93), fr);
    } else if (pat == 9) {
        col *= 0.96 + 0.06 * noise(uv * 2.0);
    } else if (pat == 10) {
        col *= 0.86 + 0.18 * noise(uv * 1.3) + 0.05 * noise(uv * 9.0);
        col = mix(col, col * 0.7, smoothstep(0.75, 0.8, noise(uv * 6.0)));
    } else if (pat == 11) {
        float rowv = (abs(n.y) > 0.7 ? wPos.x : uv.y) * 2.6;
        col *= 0.9 + 0.1 * hash(vec2(floor(rowv), 2.0));
        col = mix(col, col * 0.72, 1.0 - smoothstep(0.0, 0.12, fract(rowv)));
    } else if (pat == 12) {
        vec2 g = fract(uv * 1.4 + vec2(uv.y * 0.15, 0.0));
        float l = max(1.0 - smoothstep(0.0, 0.08, min(g.x, 1.0 - g.x)), 1.0 - smoothstep(0.0, 0.08, min(g.y, 1.0 - g.y)));
        col = mix(vec3(0.36, 0.22, 0.26), col, l);
    } else if (pat == 13) {
        lit = false;
        col *= 1.15;
    } else if (pat == 14) {
        float s = step(0.5, fract((uv.x + uv.y) * 1.6));
        col = mix(col, vec3(0.12, 0.11, 0.12), s);
    } else if (pat == 15) {
        col *= 0.85 + 0.25 * noise(wPos.xz * 1.7 + wPos.y);
    } else if (pat == 16) {
        vec2 v = voronoi(uv * 0.9);
        col *= 0.85 + 0.2 * v.y;
        vec2 g = fract(uv * 1.2);
        float l = max(1.0 - smoothstep(0.0, 0.06, min(g.x, 1.0 - g.x)), 1.0 - smoothstep(0.0, 0.06, min(g.y, 1.0 - g.y)));
        col = mix(col, col * vec3(1.35, 1.05, 1.1), l * 0.6);
        col = mix(col, col * 0.6, 1.0 - smoothstep(0.02, 0.06, v.x));
    }
    float ndl = dot(n, SUN_DIR);
    float direct, sky;
    vec3 light = sceneLight(wPos, n, ndl, direct, sky);
    if (lit) {
        // Dois tons no lado iluminado (topo/fachada de frente x rasante), como pintura de cenario.
        float tone = mix(0.9, 1.0, smoothstep(0.28, 0.46, ndl));
        vec3 hemi = mix(vec3(0.96, 0.93, 0.95), vec3(1.02, 1.01, 1.02), n.y * 0.5 + 0.5);
        col *= mix(light, light * tone, direct) * hemi;
    } else if (pat == 5) {
        // Agua: so escurece na sombra (pontes, predios), sem perder o brilho proprio.
        col *= mix(light * 1.12, vec3(1.0), direct);
    } else if (pat == 13) {
        // Lanternas acesas: mais vivas onde esta escuro.
        col *= mix(1.35, 1.0, smoothstep(0.2, 0.7, sky));
    }
    if (inkView.z > 0.5 && pat != 5) {
        float d0;
        float ink = inkEdge(inkPx, d0);
        // Traco forte de perto, mais leve ao longe (a neblina termina de apagar).
        ink *= mix(0.9, 0.35, smoothstep(20.0, 110.0, d0));
        col = mix(col, col * vec3(0.30, 0.25, 0.30), ink);
    }
    vec3 V = wPos - viewPos;
    float dist = length(V);
    float fog = 1.0 - exp(-pow(dist * fogDensity, 1.6));
    float glow = pow(max(dot(V / max(dist, 1e-3), SUN_DIR), 0.0), 6.0);
    vec3 haze = mix(fogColor, vec3(1.0, 0.97, 0.88), glow * 0.6);
    col = mix(col, haze, clamp(fog, 0.0, 0.9));
    finalColor = vec4(col, 1.0);
}
'''

# Pre-passe so de profundidade: o shader caro (padroes + luz) roda uma vez por pixel visivel,
# nao em cada camada de sacada/predio escondida atras de outra.
PREPASS_VERTEX = '''#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
uniform mat4 mvp;
uniform mat4 matModel;
invariant gl_Position;
out vec3 wPos;
out vec3 wNor;
out float vPat;
void main() {
    wPos = (matModel * vec4(vertexPosition, 1.0)).xyz;
    wNor = normalize(mat3(matModel) * vertexNormal);
    vPat = vertexTexCoord.x;
    gl_Position = mvp * vec4(vertexPosition, 1.0);
}
'''
PREPASS_FRAGMENT = '''#version 330
in vec3 wPos;
in vec3 wNor;
in float vPat;
out vec4 finalColor;
''' + CHAIN_GLSL + '''
void main() {
    if (int(floor(vPat)) == 18 && chainHole(wPos, normalize(wNor))) discard;
    finalColor = vec4(1.0);
}
'''

INK_VERTEX = '''#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
in vec2 vertexTexCoord;
uniform mat4 mvp;
uniform mat4 matModel;
invariant gl_Position;
out vec3 wNor;
out vec3 wPos;
out float vPat;
out float invDist;
void main() {
    wNor = normalize(mat3(matModel) * vertexNormal);
    wPos = (matModel * vec4(vertexPosition, 1.0)).xyz;
    vPat = vertexTexCoord.x;
    gl_Position = mvp * vec4(vertexPosition, 1.0);
    invDist = 1.0 / max(gl_Position.w, 1e-3);
}
'''
INK_FRAGMENT = '''#version 330
in vec3 wNor;
in vec3 wPos;
in float vPat;
in float invDist;
out vec4 finalColor;
''' + CHAIN_GLSL + '''
const float INK_NEAR = 0.05;
const float INK_LOG = 11.2898;
vec2 oct(vec3 n) {
    n /= abs(n.x) + abs(n.y) + abs(n.z);
    vec2 e = n.xy;
    if (n.z < 0.0) e = (1.0 - abs(n.yx)) * vec2(n.x >= 0.0 ? 1.0 : -1.0, n.y >= 0.0 ? 1.0 : -1.0);
    return e * 0.5 + 0.5;
}
void main() {
    if (int(floor(vPat)) == 18 && chainHole(wPos, normalize(wNor))) discard;
    float t = clamp(log(1.0 / (invDist * INK_NEAR)) / INK_LOG, 0.0, 1.0);
    float v = floor(t * 65535.0 + 0.5);
    float hi = floor(v / 256.0);
    finalColor = vec4(oct(normalize(wNor)), hi / 255.0, (v - hi * 256.0) / 255.0);
}
'''

SKY_VERTEX = '''#version 330
in vec3 vertexPosition;
uniform mat4 mvp;
out vec3 dir;
void main() { dir = vertexPosition; gl_Position = mvp * vec4(vertexPosition, 1.0); }
'''
SKY_FRAGMENT = '''#version 330
in vec3 dir;
uniform vec3 fogColor;
out vec4 finalColor;
const vec3 SUN_DIR = normalize(vec3(%s));
void main() {
    vec3 d = normalize(dir);
    vec3 top = vec3(0.82, 0.9, 0.93);
    vec3 col = mix(fogColor, top, smoothstep(0.02, 0.55, d.y));
    float s = max(dot(d, SUN_DIR), 0.0);
    col = mix(col, vec3(1.0, 0.97, 0.88), pow(s, 6.0) * 0.6);
    col = mix(col, vec3(1.0, 0.99, 0.94), smoothstep(0.9965, 0.9985, s));
    finalColor = vec4(col, 1.0);
}
''' % ', '.join(f'{c:.4f}' for c in lighting.SUN)


INK_SLOT = 12  # unidade de textura do contorno (10 e 11 sao da iluminacao)
_GL = {}


class _Shared:
    model = None
    shader = None
    prepass = None
    ink_shader = None
    ink_target = None
    ink_size = None
    ink_locs = {}
    sky_shader = None
    sky = None
    users = 0
    locs = {}


def _load():
    if _Shared.model is not None:
        return
    model = rl.load_model(str(layout.MAP_FOLDER / layout.MAP_FILE))
    if not rl.is_model_valid(model):
        raise RuntimeError(f'Falha ao carregar {layout.MAP_FILE}')
    shader = rl.load_shader_from_memory(VERTEX, FRAGMENT)
    for i in range(model.materialCount):
        model.materials[i].shader = shader
    _Shared.model, _Shared.shader = model, shader
    _Shared.locs = {name: rl.get_shader_location(shader, name) for name in ('viewPos', 'time', 'fogColor', 'fogDensity')}
    _Shared.prepass = rl.load_shader_from_memory(PREPASS_VERTEX, PREPASS_FRAGMENT)
    _Shared.ink_shader = rl.load_shader_from_memory(INK_VERTEX, INK_FRAGMENT)
    _Shared.ink_locs = {name: rl.get_shader_location(shader, name) for name in ('inkBuf', 'inkView')}
    _set(shader, _Shared.ink_locs['inkView'], (0.0, 0.0, 0.0, 1.0), 'vec4')
    lighting.register(shader)
    try:
        lighting.bake(model, (layout.X0, layout.Z0, layout.X1, layout.Z1))
    except Exception as exc:  # noqa: BLE001 - sem a luz assada o mapa ainda desenha (faixas simples)
        print(f'WARNING: iluminacao do mapa desativada ({type(exc).__name__}: {exc})', flush=True)
    _Shared.sky_shader = rl.load_shader_from_memory(SKY_VERTEX, SKY_FRAGMENT)
    sky = rl.load_model_from_mesh(rl.gen_mesh_sphere(800, 16, 16))
    sky.materials[0].shader = _Shared.sky_shader
    _Shared.sky = sky


def _set(shader, loc, values, kind):
    if loc < 0:
        return
    if kind == 'vec3':
        rl.set_shader_value(shader, loc, rl.ffi.new('float[3]', values), rl.SHADER_UNIFORM_VEC3)
    elif kind == 'vec4':
        rl.set_shader_value(shader, loc, rl.ffi.new('float[4]', values), rl.SHADER_UNIFORM_VEC4)
    elif kind == 'vec2':
        rl.set_shader_value(shader, loc, rl.ffi.new('float[2]', values), rl.SHADER_UNIFORM_VEC2)
    elif kind == 'int':
        rl.set_shader_value(shader, loc, rl.ffi.new('int *', values), rl.SHADER_UNIFORM_INT)
    else:
        rl.set_shader_value(shader, loc, rl.ffi.new('float *', values), rl.SHADER_UNIFORM_FLOAT)


def prepare():
    """Carrega o mapa e assa a iluminacao fora de qualquer passe de desenho (usa framebuffers)."""
    _load()


def configure_depth():
    """Near plane at 8 cm (raylib default is 1 cm): far fewer depth fights on distant surfaces."""
    rl.rl_set_clip_planes(.08, 2000)


def draw_district(camera_position, time, fog_density=.0062, lit=True, ink=None):
    """Draw sky + district; ``camera_position`` is a raylib Vector3. ``lit=False`` skips the
    baked shadows/sky occlusion (flat colours, used by the minimap); ``ink`` (default: same
    as ``lit``) draws the ink outline."""
    if ink is None:
        ink = lit
    _load()
    shader, locs = _Shared.shader, _Shared.locs
    _set(shader, locs['viewPos'], (camera_position.x, camera_position.y, camera_position.z), 'vec3')
    _set(shader, locs['time'], time, 'float')
    _set(shader, locs['fogColor'], FOG, 'vec3')
    _set(shader, locs['fogDensity'], fog_density, 'float')
    sky_loc = rl.get_shader_location(_Shared.sky_shader, 'fogColor')
    _set(_Shared.sky_shader, sky_loc, FOG, 'vec3')
    lighting.bind()
    lighting.update_lamps((camera_position.x, camera_position.y, camera_position.z))
    rl.rl_disable_backface_culling()
    rl.rl_disable_depth_mask()
    rl.draw_model(_Shared.sky, camera_position, 1, rl.WHITE)
    rl.rl_enable_depth_mask()
    rl.rl_enable_backface_culling()
    model = _Shared.model
    if not (ink and _ink_pass(model, shader)):
        _set(shader, _Shared.ink_locs['inkView'], (0.0, 0.0, 0.0, 1.0), 'vec4')
    # Pre-passe de profundidade: o shader caro roda uma vez por pixel visivel.
    rl.rl_draw_render_batch_active()
    rl.rl_color_mask(False, False, False, False)
    _draw_model_with(model, _Shared.prepass, shader)
    rl.rl_color_mask(True, True, True, True)
    if not lit:
        lighting.enable(shader, False)
    rl.draw_model(model, rl.Vector3(0, 0, 0), 1, rl.WHITE)
    if not lit:
        lighting.enable(shader, True)


def _draw_model_with(model, temporary, shader):
    for i in range(model.materialCount):
        model.materials[i].shader = temporary
    rl.draw_model(model, rl.Vector3(0, 0, 0), 1, rl.WHITE)
    for i in range(model.materialCount):
        model.materials[i].shader = shader


def _viewport():
    """(x, y, w, h) do viewport atual via glGetIntegerv (GL 1.1); None se indisponivel."""
    if 'fn' not in _GL:
        fn = None
        try:
            import ctypes
            import sys
            if sys.platform == 'win32':
                lib = ctypes.WinDLL('opengl32')
            elif sys.platform == 'darwin':
                lib = ctypes.CDLL('/System/Library/Frameworks/OpenGL.framework/OpenGL')
            else:
                lib = ctypes.CDLL('libGL.so.1')
            fn = lib.glGetIntegerv
            fn.argtypes, fn.restype = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)], None
        except (OSError, AttributeError):
            fn = None
        _GL['fn'] = fn
    fn = _GL['fn']
    if fn is None:
        return None
    import ctypes
    out = (ctypes.c_int * 4)()
    fn(0x0BA2, out)  # GL_VIEWPORT
    return tuple(out)


def _ink_pass(model, shader):
    """Desenha normal + profundidade do mapa na textura de contorno, com as matrizes da
    camera atual. Devolve False (e o chamador usa o pre-passe comum) se nao der."""
    view = _viewport()
    if view is None or view[2] < 8 or view[3] < 8:
        return False
    x, y, w, h = view
    if _Shared.ink_size != (w, h):
        if _Shared.ink_target is not None:
            rl.unload_render_texture(_Shared.ink_target)
            _Shared.ink_target = None
        try:
            _Shared.ink_target = lighting._target(w, h, rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8, True)
        except RuntimeError:
            _Shared.ink_size = None
            return False
        rl.set_texture_filter(_Shared.ink_target.texture, rl.TextureFilter.TEXTURE_FILTER_POINT)
        _Shared.ink_size = (w, h)
    previous = rl.rl_get_active_framebuffer()
    rl.rl_draw_render_batch_active()
    rl.rl_enable_framebuffer(_Shared.ink_target.id)
    rl.rl_viewport(0, 0, w, h)
    rl.rl_clear_color(128, 128, 255, 255)  # ceu: distancia maxima
    rl.rl_clear_screen_buffers()
    rl.rl_disable_color_blend()  # o alfa guarda dados, nao transparencia
    _draw_model_with(model, _Shared.ink_shader, shader)
    rl.rl_draw_render_batch_active()
    rl.rl_enable_color_blend()
    if previous:
        rl.rl_enable_framebuffer(previous)
    else:
        rl.rl_disable_framebuffer()
    rl.rl_viewport(x, y, w, h)
    rl.rl_active_texture_slot(INK_SLOT)
    rl.rl_enable_texture(_Shared.ink_target.texture.id)
    rl.rl_active_texture_slot(0)
    locs = _Shared.ink_locs
    _set(shader, locs['inkBuf'], INK_SLOT, 'int')
    _set(shader, locs['inkView'], (float(x), float(y), 1.0, float(max(1, round(h / 1080)))), 'vec4')
    return True


def release():
    if _Shared.model is None:
        return
    lighting.unregister(_Shared.shader)
    lighting.release()
    rl.unload_model(_Shared.model)
    rl.unload_shader(_Shared.shader)
    rl.unload_shader(_Shared.prepass)
    rl.unload_shader(_Shared.ink_shader)
    if _Shared.ink_target is not None:
        rl.unload_render_texture(_Shared.ink_target)
    _Shared.ink_target = _Shared.ink_size = None
    _Shared.sky.materials[0].shader = rl.Shader()
    rl.unload_model(_Shared.sky)
    rl.unload_shader(_Shared.sky_shader)
    _Shared.model = _Shared.shader = _Shared.sky = _Shared.sky_shader = _Shared.prepass = None
    _Shared.ink_shader = None


class DistrictScenery(Renderable3D):
    def __init__(self):
        self.time = 0.0

    def init(self):
        super().init()
        configure_depth()
        if rl.is_window_ready():
            prepare()

    def render(self):
        self.time += rl.get_frame_time()
        position = self.camera.rl_camera.position if self.camera else rl.Vector3(0, 10, 0)
        draw_district(position, self.time)

    def on_destroy(self):
        super().on_destroy()
        release()
