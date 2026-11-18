"""Iluminação do Bairro Arterial no estilo do anime.

O cenário é estático, então a luz é "assada" uma vez quando o mapa carrega:

* **Sol**: mapa de sombra ortográfico (R32F) cobrindo a área jogável. Sombra projetada com
  borda nítida (cel) e a mesma cor lavanda da face que está de costas para o sol, como nos
  cenários pintados da série.
* **Céu**: volume de visibilidade do céu (fatias horizontais de 0,5 m num atlas R8). Para
  calcular, o mapa é desenhado de 24 direções do domo do céu, uma abertura morfológica tira o
  que é fino (fios, corrimãos, postes, peitoris) e cada voxel testa quantas direções enxergam
  o céu. Em jogo bastam duas leituras: túneis, o vão sob pontes e passarelas e o pé das
  paredes escurecem suavemente.
* **Postes**: as lanternas (padrão GLOW do GLB) viram luzes quentes que só aparecem onde falta
  céu (túneis e passagens cobertas); de dia, ao ar livre, ficam discretas.

Os personagens usam as mesmas texturas (``model_lighting``), então escurecem ao entrar na
sombra de um prédio ou num túnel. Tudo exige contexto OpenGL e acontece sob demanda.
"""
import math

import pyray as rl

# Direção PARA o sol (mundo do jogo: x leste, y cima, z sul). Sol alto vindo do sudoeste:
# a avenida (norte-sul) recebe luz ao longo do eixo e as fachadas leste/oeste ficam em tons
# diferentes; quem olha para o sul (bactérias) vê o contraluz enevoado da referência.
SUN = (-0.36, 0.80, 0.48)

# Paleta (multiplica a cor da superfície). Sombras frias/lavanda, luz levemente quente.
SUN_COLOR = (1.05, 1.0, 0.93)
SHADE_COLOR = (0.72, 0.69, 0.86)
DEEP_COLOR = (0.42, 0.35, 0.44)
LAMP_COLOR = (1.0, 0.72, 0.38)

SUN_RES = 4096           # lado maior do mapa de sombra (~5 cm por texel)
SKY_TILE = 512           # cada direção do domo, só durante o bake
VOXEL = 0.5              # volume do céu: 0,5 m em x/z e em y
MAX_LAMPS = 12
LAMP_RANGE = 7.5
SUN_SLOT, SKY_SLOT = 10, 11
PAD = 6.0
TOP = 46.0               # altura até onde a área jogável recebe oclusão do céu
BOTTOM = -4.0
SUN_PAD = 26.0           # o sol cobre também o começo do horizonte de prédios
SUN_TOP = 72.0


def _norm(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _dot(a, b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def _corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def sky_directions():
    """24 direções do domo em anéis, com peso de Lambert (cos zenital x ângulo sólido)."""
    dirs = []
    for elev, count, offset in ((16, 9, 0), (40, 8, 22.5), (64, 5, 10), (84, 2, 45)):
        e = math.radians(elev)
        weight = math.sin(e) * math.cos(e) / count
        for k in range(count):
            a = math.radians(offset + k * 360 / count)
            d = _norm((math.cos(e) * math.cos(a), math.sin(e), math.cos(e) * math.sin(a)))
            dirs.append((d, weight))
    total = sum(w for _, w in dirs)
    return [(d, w / total) for d, w in dirs]


def frame(direction, area_lo, area_hi, model_lo, model_hi):
    """Linhas da projeção ortográfica vista de ``direction``.

    Devolve (row_u, row_v, row_z, row_w, tamanho): ``dot(vec4(p,1), row)`` dá u/v em [-1, 1]
    na área jogável, z de recorte (o mais perto do céu fica em -1) e a distância "para o céu"
    a partir do ponto mais baixo do modelo (sempre > 0; textura limpa = 0 = nada bloqueia).
    """
    d = _norm(direction)
    up = (0.0, 1.0, 0.0) if abs(d[1]) < 0.95 else (0.0, 0.0, -1.0)
    r = _norm(_cross(up, d))
    u = _cross(d, r)
    area = _corners(area_lo, area_hi)
    us = [_dot(c, r) for c in area]
    vs = [_dot(c, u) for c in area]
    ws = [_dot(c, d) for c in _corners(model_lo, model_hi)]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    w0, w1 = min(ws) - 2.0, max(ws) + 2.0
    hu, hv = (u1 - u0) / 2, (v1 - v0) / 2
    uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
    row_u = (r[0] / hu, r[1] / hu, r[2] / hu, -uc / hu)
    row_v = (u[0] / hv, u[1] / hv, u[2] / hv, -vc / hv)
    k = -2.0 / (w1 - w0)
    row_z = (d[0] * k, d[1] * k, d[2] * k, 1.0 + 2.0 * w0 / (w1 - w0))
    row_w = (d[0], d[1], d[2], -w0 + 1.0)
    return row_u, row_v, row_z, row_w, (u1 - u0, v1 - v0)


def volume_layout(area):
    """Geometria do volume do céu: origem, texels por fatia, fatias e grade do atlas."""
    x0, z0, x1, z1 = area
    ox, oz = x0 - PAD, z0 - PAD
    w = int(math.ceil((x1 - x0 + 2 * PAD) / VOXEL))
    h = int(math.ceil((z1 - z0 + 2 * PAD) / VOXEL))
    slices = int(math.ceil((TOP - BOTTOM) / VOXEL)) + 1
    cols = max(1, min(slices, 4096 // w))
    rows = int(math.ceil(slices / cols))
    return {'origin': (ox, BOTTOM, oz), 'w': w, 'h': h, 'slices': slices, 'cols': cols,
            'atlas': (w * cols, h * rows)}


def _fmt(values):
    return ', '.join(f'{c:.4f}' for c in values)


# ---------------------------------------------------------------------------------------------
# GLSL compartilhado (cenário e personagens)
# ---------------------------------------------------------------------------------------------

GLSL = '''
uniform sampler2D sunMap;
uniform sampler2D skyVol;
uniform vec4 sunU;
uniform vec4 sunV;
uniform vec4 sunW;
uniform vec4 volA;   // origem x, y, z; 1/voxel
uniform vec4 volB;   // texels por fatia (x, z), fatias, colunas do atlas
uniform vec2 volC;   // tamanho do atlas
uniform vec4 lamps[%(lamps)d];
uniform float lightingOn;
const vec3 SUN_DIR = normalize(vec3(%(sun)s));
const vec3 SUN_COLOR = vec3(%(sun_color)s);
const vec3 SHADE_COLOR = vec3(%(shade)s);
const vec3 DEEP_COLOR = vec3(%(deep)s);
const vec3 LAMP_COLOR = vec3(%(lamp)s);

// Visibilidade do sol (1 = iluminado): PCF em tenda 3x3 (16 leituras com pesos bilineares),
// afiada em seguida: borda nítida de cel sem o serrilhado dos texels.
float sunVisibility(vec3 p, vec3 n) {
    if (lightingOn < 0.5) return 1.0;
    float ndl = dot(n, SUN_DIR);
    vec4 q = vec4(p + n * 0.05 + SUN_DIR * 0.03, 1.0);
    vec2 uv = vec2(dot(q, sunU), dot(q, sunV)) * 0.5 + 0.5;
    if (uv.x <= 0.0 || uv.y <= 0.0 || uv.x >= 1.0 || uv.y >= 1.0) return 1.0;
    // Some suavemente perto da borda do mapa de sombra (sem corte reto no horizonte).
    vec2 edge = min(uv, 1.0 - uv);
    float fade = smoothstep(0.0, 0.04, min(edge.x, edge.y));
    float ref = dot(q, sunW) + 0.06 + 0.10 * clamp(1.0 - abs(ndl), 0.0, 1.0);
    vec2 size = vec2(textureSize(sunMap, 0));
    vec2 st = uv * size - 0.5;
    vec2 base = floor(st);
    vec2 f = st - base;
    float sum = 0.0;
    for (int j = -1; j <= 2; j++) {
        float wy = j == -1 ? 1.0 - f.y : (j == 2 ? f.y : 1.0);
        for (int i = -1; i <= 2; i++) {
            float wx = i == -1 ? 1.0 - f.x : (i == 2 ? f.x : 1.0);
            float stored = texture(sunMap, (base + vec2(i, j) + 0.5) / size).r;
            sum += wx * wy * step(stored, ref);
        }
    }
    return mix(1.0, smoothstep(0.25, 0.75, sum / 9.0), fade);
}

// Fração do céu visível (0 = túnel fechado, 1 = céu aberto), lida do volume assado.
// Lê a 0,8 m da superfície: a interpolação nunca usa o voxel encostado nela (que pode
// ter amostras dentro da parede).
float skyVisibility(vec3 p, vec3 n) {
    if (lightingOn < 0.5) return 1.0;
    vec3 q = p + n * 0.8;
    vec2 t = (q.xz - volA.xz) * volA.w;
    float s = (q.y - volA.y) * volA.w;
    if (t.x < 0.0 || t.y < 0.0 || t.x > volB.x || t.y > volB.y || s > volB.z - 1.0) return 1.0;
    s = max(s, 0.0);
    // Índices inteiros: floor(k / colunas) em float erra nos múltiplos exatos.
    int cols = int(volB.w + 0.5);
    int k0 = int(s);
    int k1 = min(k0 + 1, int(volB.z + 0.5) - 1);
    t = clamp(t, vec2(0.5), volB.xy - 0.5);
    vec2 o0 = vec2(float(k0 %% cols), float(k0 / cols)) * volB.xy;
    vec2 o1 = vec2(float(k1 %% cols), float(k1 / cols)) * volB.xy;
    float a = texture(skyVol, (o0 + t) / volC).r;
    float b = texture(skyVol, (o1 + t) / volC).r;
    return mix(a, b, s - float(k0));
}

// Luz quente dos postes; só onde há pouco céu (túneis, sob pontes). Ao ar livre, de dia,
// não aparece (e o laço nem roda).
vec3 lampLight(vec3 p, vec3 n, float sky) {
    if (lightingOn < 0.5 || sky >= 0.3) return vec3(0.0);
    vec3 sum = vec3(0.0);
    for (int i = 0; i < %(lamps)d; i++) {
        vec4 l = lamps[i];
        vec3 d = l.xyz - p;
        float dist = length(d);
        if (dist >= l.w) continue;
        float fall = 1.0 - smoothstep(0.0, l.w, dist);
        float facing = clamp(dot(n, d / max(dist, 1e-3)) * 0.6 + 0.4, 0.0, 1.0);
        sum += LAMP_COLOR * fall * fall * facing;
    }
    return sum * (1.0 - smoothstep(0.08, 0.3, sky));
}

// Cor da luz que chega a um ponto (multiplica o albedo).
vec3 sceneLight(vec3 p, vec3 n, float ndl, out float direct, out float sky) {
    sky = skyVisibility(p, n);
    float form = smoothstep(-0.03, 0.05, ndl);
    // Face de costas para o sol já está na sombra: não precisa ler o mapa.
    direct = form > 0.0 ? form * sunVisibility(p, n) : 0.0;
    float open = smoothstep(0.02, 0.3, sky);
    vec3 shade = mix(DEEP_COLOR, SHADE_COLOR, open);
    vec3 lit = SUN_COLOR * mix(0.84, 1.0, open);
    return mix(shade, lit, direct) + lampLight(p, n, sky) * (1.0 - direct * 0.7);
}
''' % {
    'lamps': MAX_LAMPS,
    'sun': _fmt(SUN),
    'sun_color': _fmt(SUN_COLOR),
    'shade': _fmt(SHADE_COLOR),
    'deep': _fmt(DEEP_COLOR),
    'lamp': _fmt(LAMP_COLOR),
}

DEPTH_VS = '''#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
uniform mat4 matModel;
uniform vec4 rowU;
uniform vec4 rowV;
uniform vec4 rowZ;
uniform vec4 rowW;
out float towardLight;
out vec3 wPos;
out float vPat;
void main() {
    vec4 p = matModel * vec4(vertexPosition, 1.0);
    gl_Position = vec4(dot(p, rowU), dot(p, rowV), dot(p, rowZ), 1.0);
    towardLight = dot(p, rowW);
    wPos = p.xyz;
    vPat = vertexTexCoord.x;
}
'''

DEPTH_FS = '''#version 330
in float towardLight;
in vec3 wPos;
in float vPat;
out vec4 finalColor;
void main() {
    int pat = int(floor(vPat));
    // Água e brilho dos postes não fazem sombra.
    if (pat == 5 || pat == 13) discard;
    // Redes (padrão 12) deixam passar luz entre os fios: sombra quadriculada.
    if (pat == 12) {
        vec2 g = fract(vec2(wPos.x + wPos.y * 0.3, wPos.z + wPos.y * 0.3) * 1.4);
        if (min(min(g.x, 1.0 - g.x), min(g.y, 1.0 - g.y)) > 0.12) discard;
    }
    finalColor = vec4(towardLight, 0.0, 0.0, 1.0);
}
'''

# Abertura morfológica (erosão + dilatação 3x3) nos mapas do céu: some o que tem menos de
# ~1 m de largura e as coberturas grandes ficam como estavam.
MORPH_FS = '''#version 330
uniform sampler2D src;
uniform float useMax;
out vec4 finalColor;
void main() {
    ivec2 p = ivec2(gl_FragCoord.xy);
    ivec2 last = textureSize(src, 0) - 1;
    float v = useMax > 0.5 ? -1e30 : 1e30;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            float s = texelFetch(src, clamp(p + ivec2(i, j), ivec2(0), last), 0).r;
            v = useMax > 0.5 ? max(v, s) : min(v, s);
        }
    }
    finalColor = vec4(v, 0.0, 0.0, 1.0);
}
'''

# Um pixel do atlas = um voxel. Testa as 24 direções (4 amostras cada) contra os mapas.
VOLUME_FS = '''#version 330
uniform sampler2D dirMaps;
uniform vec4 dirU[%(n)d];
uniform vec4 dirV[%(n)d];
uniform vec4 dirW[%(n)d];   // xyz = direção, w = deslocamento (ver frame())
uniform float dirWeight[%(n)d];
uniform vec4 volA;
uniform vec4 volB;
uniform vec2 tileGrid;
out vec4 finalColor;
// Amostras pequenas (< 0,15 m): um voxel colado na parede não deve "ver" o lado de dentro.
const vec3 TAPS[4] = vec3[4](vec3(0.12, 0.06, 0.04), vec3(-0.04, -0.06, 0.12),
                             vec3(-0.12, 0.06, -0.04), vec3(0.04, -0.06, -0.12));
void main() {
    ivec2 px = ivec2(gl_FragCoord.xy);
    ivec2 size = ivec2(volB.xy + 0.5);
    ivec2 cell = px / size;
    int slice = cell.y * int(volB.w + 0.5) + cell.x;
    if (slice >= int(volB.z + 0.5)) { finalColor = vec4(1.0); return; }
    vec2 local = vec2(px - cell * size) + 0.5;
    vec3 p = vec3(volA.x + local.x / volA.w, volA.y + float(slice) / volA.w, volA.z + local.y / volA.w);
    int gx = int(tileGrid.x + 0.5);
    float open = 0.0;
    for (int i = 0; i < %(n)d; i++) {
        vec2 tile = vec2(float(i %% gx), float(i / gx));
        float vis = 0.0;
        for (int j = 0; j < 4; j++) {
            vec4 q = vec4(p + TAPS[j], 1.0);
            vec2 uv = vec2(dot(q, dirU[i]), dot(q, dirV[i])) * 0.5 + 0.5;
            if (uv.x <= 0.002 || uv.y <= 0.002 || uv.x >= 0.998 || uv.y >= 0.998) { vis += 1.0; continue; }
            float stored = texture(dirMaps, (uv + tile) / tileGrid).r;
            vis += 1.0 - smoothstep(0.15, 0.7, stored - dot(q, dirW[i]));
        }
        open += dirWeight[i] * vis * 0.25;
    }
    finalColor = vec4(vec3(open), 1.0);
}
'''


# ---------------------------------------------------------------------------------------------
# Estado e baking
# ---------------------------------------------------------------------------------------------

class _State:
    sun_tex = None
    sky_tex = None
    sun_rows = None
    volume = None
    lamps = ()
    lamp_values = None
    shaders = {}  # shader.id -> (shader, locs)


def baked():
    return _State.sun_tex is not None


def _target(width, height, pixel_format, depth):
    """Framebuffer com uma textura de cor amostrável (+ profundidade em renderbuffer)."""
    fbo = rl.rl_load_framebuffer()
    if not fbo:
        raise RuntimeError('Sem framebuffer para a iluminação')
    rl.rl_enable_framebuffer(fbo)
    tex = rl.rl_load_texture(rl.ffi.NULL, width, height, pixel_format, 1)
    rl.rl_framebuffer_attach(fbo, tex, rl.RL_ATTACHMENT_COLOR_CHANNEL0, rl.RL_ATTACHMENT_TEXTURE2D, 0)
    depth_id = 0
    if depth:
        depth_id = rl.rl_load_texture_depth(width, height, True)
        rl.rl_framebuffer_attach(fbo, depth_id, rl.RL_ATTACHMENT_DEPTH, rl.RL_ATTACHMENT_RENDERBUFFER, 0)
    ok = rl.rl_framebuffer_complete(fbo)
    rl.rl_disable_framebuffer()
    if not ok:
        rl.rl_unload_framebuffer(fbo)
        rl.rl_unload_texture(tex)
        raise RuntimeError('Framebuffer da iluminação incompleto')
    target = rl.RenderTexture()
    target.id = fbo
    target.texture.id = tex
    target.texture.width, target.texture.height = width, height
    target.texture.mipmaps = 1
    target.texture.format = pixel_format
    target.depth.id = depth_id
    target.depth.width, target.depth.height = width, height
    return target


def _keep_texture(target, linear):
    """Descarta FBO + profundidade e devolve só a textura de cor."""
    texture = rl.Texture()
    texture.id = target.texture.id
    texture.width, texture.height = target.texture.width, target.texture.height
    texture.mipmaps, texture.format = 1, target.texture.format
    rl.rl_unload_framebuffer(target.id)
    rl.set_texture_wrap(texture, rl.TextureWrap.TEXTURE_WRAP_CLAMP)
    rl.set_texture_filter(texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR if linear
                          else rl.TextureFilter.TEXTURE_FILTER_POINT)
    return texture


def _set(shader, loc, value, kind):
    if loc < 0:
        return
    T = rl.ShaderUniformDataType
    if kind == 'float':
        rl.set_shader_value(shader, loc, rl.ffi.new('float *', value), T.SHADER_UNIFORM_FLOAT)
    elif kind == 'int':
        rl.set_shader_value(shader, loc, rl.ffi.new('int *', value), T.SHADER_UNIFORM_INT)
    elif kind in ('vec2', 'vec4'):
        rl.set_shader_value(shader, loc, rl.ffi.new(f'float[{len(value)}]', value),
                            T.SHADER_UNIFORM_VEC2 if kind == 'vec2' else T.SHADER_UNIFORM_VEC4)
    elif kind == 'float[]':
        rl.set_shader_value_v(shader, loc, rl.ffi.new(f'float[{len(value)}]', value),
                              T.SHADER_UNIFORM_FLOAT, len(value))
    elif kind == 'vec4[]':
        flat = [c for v in value for c in v]
        rl.set_shader_value_v(shader, loc, rl.ffi.new(f'float[{len(flat)}]', flat),
                              T.SHADER_UNIFORM_VEC4, len(value))


def _draw_with(model, shader):
    # cffi devolve uma vista da memória do material: guarda id/locs, não o struct.
    previous = [(model.materials[i].shader.id, model.materials[i].shader.locs) for i in range(model.materialCount)]
    for i in range(model.materialCount):
        model.materials[i].shader = shader
    try:
        rl.draw_model(model, rl.Vector3(0, 0, 0), 1, rl.WHITE)
        rl.rl_draw_render_batch_active()
    finally:
        for i, (sid, locs) in enumerate(previous):
            model.materials[i].shader.id = sid
            model.materials[i].shader.locs = locs


def find_lamps(model):
    """Centros das cabeças de poste (faces com padrão GLOW = 13) no GLB."""
    try:
        import numpy as np
    except ImportError:
        return ()
    points = []
    for i in range(model.meshCount):
        mesh = model.meshes[i]
        n = mesh.vertexCount
        if n <= 0 or mesh.texcoords == rl.ffi.NULL:
            continue
        uv = np.frombuffer(rl.ffi.buffer(mesh.texcoords, n * 8), dtype=np.float32).reshape(n, 2)
        mask = (uv[:, 0] >= 13.0) & (uv[:, 0] < 14.0)
        if not mask.any():
            continue
        pos = np.frombuffer(rl.ffi.buffer(mesh.vertices, n * 12), dtype=np.float32).reshape(n, 3)
        points.append(pos[mask].copy())
    if not points:
        return ()
    pts = np.concatenate(points)
    groups = {}
    for key, p in zip(map(tuple, np.floor(pts).astype(np.int64)), pts):
        groups.setdefault(key, []).append(p)
    merged = []
    for group in groups.values():
        c = np.mean(group, axis=0)
        if all(np.linalg.norm(c - m) > 1.0 for m in merged):
            merged.append(c)
    return tuple((float(c[0]), float(c[1]), float(c[2])) for c in merged)


def _depth_pass(model, shader, locs, rows, viewport):
    for name, value in zip(('rowU', 'rowV', 'rowZ', 'rowW'), rows):
        _set(shader, locs[name], value, 'vec4')
    rl.rl_viewport(*viewport)
    _draw_with(model, shader)


def _begin_depth(target):
    rl.begin_texture_mode(target)
    rl.clear_background(rl.BLANK)
    rl.rl_enable_depth_test()
    rl.rl_disable_backface_culling()


def _filter_pass(shader, loc_src, source, use_max, loc_max):
    target = _target(source.width, source.height, rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R32, False)
    _set(shader, loc_max, 1.0 if use_max else 0.0, 'float')
    rl.begin_texture_mode(target)
    rl.clear_background(rl.BLANK)
    rl.begin_shader_mode(shader)
    rl.set_shader_value_texture(shader, loc_src, source)
    rl.draw_rectangle(0, 0, source.width, source.height, rl.WHITE)
    rl.end_shader_mode()
    rl.end_texture_mode()
    return _keep_texture(target, linear=True)


def _opening(texture):
    """Erosão seguida de dilatação. Consome ``texture`` (liberada mesmo se falhar)."""
    shader = rl.load_shader_from_memory(rl.ffi.NULL, MORPH_FS)
    loc_src = rl.get_shader_location(shader, 'src')
    loc_max = rl.get_shader_location(shader, 'useMax')
    try:
        try:
            eroded = _filter_pass(shader, loc_src, texture, False, loc_max)
        finally:
            rl.unload_texture(texture)
        try:
            return _filter_pass(shader, loc_src, eroded, True, loc_max)
        finally:
            rl.unload_texture(eroded)
    finally:
        rl.unload_shader(shader)


def bake(model, area):
    """Gera a sombra do sol e o volume do céu. ``area`` = (x0, z0, x1, z1) jogável."""
    release()
    x0, z0, x1, z1 = area
    area_lo = (x0 - PAD, BOTTOM, z0 - PAD)
    area_hi = (x1 + PAD, TOP, z1 + PAD)
    box = rl.get_model_bounding_box(model)
    model_lo = (box.min.x, box.min.y, box.min.z)
    model_hi = (box.max.x, box.max.y, box.max.z)
    depth = rl.load_shader_from_memory(DEPTH_VS, DEPTH_FS)
    dlocs = {n: rl.get_shader_location(depth, n) for n in ('rowU', 'rowV', 'rowZ', 'rowW')}
    dirs = sky_directions()
    volume_shader = rl.load_shader_from_memory(rl.ffi.NULL, VOLUME_FS % {'n': len(dirs)})
    dir_tex = None
    rl.rl_draw_render_batch_active()
    try:
        # Sol: textura com a proporção da área vista do sol.
        sun_lo = (x0 - SUN_PAD, BOTTOM, z0 - SUN_PAD)
        sun_hi = (x1 + SUN_PAD, SUN_TOP, z1 + SUN_PAD)
        su, sv, sz, sw, (fu, fv) = frame(SUN, sun_lo, sun_hi, model_lo, model_hi)
        scale = SUN_RES / max(fu, fv)
        w, h = max(256, int(fu * scale)), max(256, int(fv * scale))
        target = _target(w, h, rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R32, True)
        _begin_depth(target)
        _depth_pass(model, depth, dlocs, (su, sv, sz, sw), (0, 0, w, h))
        rl.end_texture_mode()
        _State.sun_tex = _keep_texture(target, linear=False)
        _State.sun_rows = (su, sv, sw)

        # Céu, passo 1: profundidade vista de cada direção do domo, num atlas.
        T = SKY_TILE
        grid = (6, int(math.ceil(len(dirs) / 6)))
        target = _target(T * grid[0], T * grid[1], rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R32, True)
        rows = []
        _begin_depth(target)
        for i, (d, _) in enumerate(dirs):
            ru, rv, rz, rw, _ = frame(d, area_lo, area_hi, model_lo, model_hi)
            _depth_pass(model, depth, dlocs, (ru, rv, rz, rw), ((i % grid[0]) * T, (i // grid[0]) * T, T, T))
            rows.append((ru, rv, rw))
        rl.end_texture_mode()
        dir_tex = _opening(_keep_texture(target, linear=True))

        # Céu, passo 2: cada pixel do atlas de fatias é um voxel; integra as direções.
        layout = volume_layout(area)
        aw, ah = layout['atlas']
        target = _target(aw, ah, rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_GRAYSCALE, False)
        vloc = {n: rl.get_shader_location(volume_shader, n)
                for n in ('dirMaps', 'dirU', 'dirV', 'dirW', 'dirWeight', 'volA', 'volB', 'tileGrid')}
        ox, oy, oz = layout['origin']
        vol_a = (ox, oy, oz, 1.0 / VOXEL)
        vol_b = (float(layout['w']), float(layout['h']), float(layout['slices']), float(layout['cols']))
        _set(volume_shader, vloc['dirU'], [r[0] for r in rows], 'vec4[]')
        _set(volume_shader, vloc['dirV'], [r[1] for r in rows], 'vec4[]')
        _set(volume_shader, vloc['dirW'], [r[2] for r in rows], 'vec4[]')
        _set(volume_shader, vloc['dirWeight'], [w for _, w in dirs], 'float[]')
        _set(volume_shader, vloc['volA'], vol_a, 'vec4')
        _set(volume_shader, vloc['volB'], vol_b, 'vec4')
        _set(volume_shader, vloc['tileGrid'], (float(grid[0]), float(grid[1])), 'vec2')
        rl.begin_texture_mode(target)
        rl.clear_background(rl.WHITE)
        rl.begin_shader_mode(volume_shader)
        rl.set_shader_value_texture(volume_shader, vloc['dirMaps'], dir_tex)
        rl.draw_rectangle(0, 0, aw, ah, rl.WHITE)
        rl.end_shader_mode()
        rl.end_texture_mode()
        _State.sky_tex = _keep_texture(target, linear=True)
        _State.volume = (vol_a, vol_b, (float(aw), float(ah)))
    except Exception:
        rl.end_texture_mode()
        release()
        raise
    finally:
        rl.rl_enable_backface_culling()
        rl.rl_disable_depth_test()
        if dir_tex is not None:
            rl.unload_texture(dir_tex)
        rl.unload_shader(depth)
        rl.unload_shader(volume_shader)
    _State.lamps = find_lamps(model)
    for shader_, locs_ in list(_State.shaders.values()):
        _upload(shader_, locs_)


NAMES = ('sunMap', 'skyVol', 'sunU', 'sunV', 'sunW', 'volA', 'volB', 'volC', 'lamps', 'lightingOn')


def register(shader):
    """Liga um shader que inclui ``GLSL`` às texturas de luz (agora e após cada bake)."""
    locs = {n: rl.get_shader_location(shader, n) for n in NAMES}
    _State.shaders[shader.id] = (shader, locs)
    _upload(shader, locs)
    return locs


def unregister(shader):
    _State.shaders.pop(shader.id, None)


def _upload(shader, locs):
    on = baked()
    _set(shader, locs['lightingOn'], 1.0 if on else 0.0, 'float')
    if not on:
        return
    _set(shader, locs['sunMap'], SUN_SLOT, 'int')
    _set(shader, locs['skyVol'], SKY_SLOT, 'int')
    su, sv, sw = _State.sun_rows
    _set(shader, locs['sunU'], su, 'vec4')
    _set(shader, locs['sunV'], sv, 'vec4')
    _set(shader, locs['sunW'], sw, 'vec4')
    vol_a, vol_b, vol_c = _State.volume
    _set(shader, locs['volA'], vol_a, 'vec4')
    _set(shader, locs['volB'], vol_b, 'vec4')
    _set(shader, locs['volC'], vol_c, 'vec2')
    _set(shader, locs['lamps'], _State.lamp_values or [(0.0, 0.0, 0.0, 0.0)] * MAX_LAMPS, 'vec4[]')


def enable(shader, on):
    """Liga/desliga a luz assada num shader registrado (o minimapa é desenhado sem sombras)."""
    entry = _State.shaders.get(shader.id)
    if entry is not None:
        _set(shader, entry[1]['lightingOn'], 1.0 if on and baked() else 0.0, 'float')


def bind():
    """Prende as texturas de luz nas unidades reservadas (o raylib não usa 10 e 11)."""
    if not baked():
        return
    rl.rl_active_texture_slot(SUN_SLOT)
    rl.rl_enable_texture(_State.sun_tex.id)
    rl.rl_active_texture_slot(SKY_SLOT)
    rl.rl_enable_texture(_State.sky_tex.id)
    rl.rl_active_texture_slot(0)


def update_lamps(camera_position):
    """Envia os postes mais próximos da câmera para todos os shaders registrados."""
    if not baked() or not _State.lamps:
        return
    cx, cy, cz = camera_position
    near = sorted(_State.lamps, key=lambda p: (p[0]-cx)**2 + (p[1]-cy)**2 + (p[2]-cz)**2)[:MAX_LAMPS]
    values = [(p[0], p[1] - 0.1, p[2], LAMP_RANGE) for p in near]
    values += [(0.0, 0.0, 0.0, 0.0)] * (MAX_LAMPS - len(values))
    if values == _State.lamp_values:
        return
    _State.lamp_values = values
    for shader, locs in _State.shaders.values():
        _set(shader, locs['lamps'], values, 'vec4[]')


def release():
    for name in ('sun_tex', 'sky_tex'):
        tex = getattr(_State, name)
        if tex is not None:
            rl.unload_texture(tex)
            setattr(_State, name, None)
    _State.sun_rows = _State.volume = _State.lamp_values = None
    _State.lamps = ()
    for shader, locs in list(_State.shaders.values()):
        _set(shader, locs['lightingOn'], 0.0, 'float')
