"""Bairro Arterial: arte exportada do Blender + shader de padroes procedurais.

O GLB guarda cor por vertice e, em UV.x, o id do padrao (tijolo, pedra,
ladrilho, madeira, agua animada...). O shader desenha os padroes no espaco do
mundo, usa a iluminacao pre-calculada do GLB, ceu em degrade e neblina quente.
Exports sem bake mantem a luz em faixas (cel shading).
Carregado sob demanda: servidores e testes sem GPU nunca abrem o modelo.
"""
import pyray as rl
from EasyCells3D.Components.Camera3D import Renderable3D
from .layout import MAP_FOLDER, MAP_FILE

FOG = (0.955, 0.915, 0.835)

VERTEX = '''#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
in vec4 vertexColor;
uniform mat4 mvp;
uniform mat4 matModel;
out vec3 wPos;
out vec3 wNor;
out vec4 vCol;
out float vPat;
out float vBaked;
void main() {
    vec4 w = matModel * vec4(vertexPosition, 1.0);
    wPos = w.xyz;
    wNor = normalize(mat3(matModel) * vertexNormal);
    vCol = vertexColor;
    vPat = vertexTexCoord.x;
    // glTF exporters may flip V: both 1.5 and -0.5 mark baked data.
    vBaked = step(0.75, abs(vertexTexCoord.y - 0.5));
    gl_Position = mvp * vec4(vertexPosition, 1.0);
}
'''

FRAGMENT = '''#version 330
in vec3 wPos;
in vec3 wNor;
in vec4 vCol;
in float vPat;
in float vBaked;
uniform vec4 colDiffuse;
uniform vec3 viewPos;
uniform float time;
uniform vec3 fogColor;
uniform float fogDensity;
out vec4 finalColor;

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
    vec3 n = normalize(wNor);
    vec3 col = vCol.rgb * colDiffuse.rgb;
    int pat = int(floor(vPat));
    vec2 uv = planar(wPos, n);
    bool lit = true;
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
    if (lit && vBaked < 0.5) {
        vec3 L = normalize(vec3(-0.42, 0.82, 0.38));
        float d = dot(n, L);
        float band = d > 0.38 ? 1.0 : (d > -0.02 ? 0.86 : 0.74);
        vec3 hemi = mix(vec3(0.9, 0.84, 0.84), vec3(1.03, 1.02, 1.05), n.y * 0.5 + 0.5);
        col *= band * hemi;
        if (abs(n.y) < 0.5) col *= mix(0.8, 1.0, smoothstep(-0.4, 1.3, wPos.y));
    }
    float dist = length(wPos - viewPos);
    float fog = 1.0 - exp(-pow(dist * fogDensity, 1.6));
    col = mix(col, fogColor, clamp(fog, 0.0, 0.9));
    finalColor = vec4(col, 1.0);
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
void main() {
    float h = normalize(dir).y;
    vec3 top = vec3(0.82, 0.9, 0.93);
    vec3 col = mix(fogColor, top, smoothstep(0.02, 0.55, h));
    col = mix(col, vec3(1.0, 0.97, 0.88), smoothstep(0.995, 1.0, dot(normalize(dir), normalize(vec3(-0.42, 0.82, 0.38)))));
    finalColor = vec4(col, 1.0);
}
'''


class _Shared:
    model = None
    shader = None
    sky_shader = None
    sky = None
    users = 0
    locs = {}


def _load():
    if _Shared.model is not None:
        return
    model = rl.load_model(str(MAP_FOLDER / MAP_FILE))
    if not rl.is_model_valid(model):
        raise RuntimeError(f'Falha ao carregar {MAP_FILE}')
    shader = rl.load_shader_from_memory(VERTEX, FRAGMENT)
    for i in range(model.materialCount):
        model.materials[i].shader = shader
    _Shared.model, _Shared.shader = model, shader
    _Shared.locs = {name: rl.get_shader_location(shader, name) for name in ('viewPos', 'time', 'fogColor', 'fogDensity')}
    _Shared.sky_shader = rl.load_shader_from_memory(SKY_VERTEX, SKY_FRAGMENT)
    sky = rl.load_model_from_mesh(rl.gen_mesh_sphere(800, 16, 16))
    sky.materials[0].shader = _Shared.sky_shader
    _Shared.sky = sky


def _set(shader, loc, values, kind):
    if loc < 0:
        return
    if kind == 'vec3':
        rl.set_shader_value(shader, loc, rl.ffi.new('float[3]', values), rl.SHADER_UNIFORM_VEC3)
    else:
        rl.set_shader_value(shader, loc, rl.ffi.new('float *', values), rl.SHADER_UNIFORM_FLOAT)


def configure_depth():
    """Near plane at 8 cm (raylib default is 1 cm): far fewer depth fights on distant surfaces."""
    rl.rl_set_clip_planes(.08, 2000)


def draw_district(camera_position, time, fog_density=.0062):
    """Draw sky + district; ``camera_position`` is a raylib Vector3."""
    _load()
    shader, locs = _Shared.shader, _Shared.locs
    _set(shader, locs['viewPos'], (camera_position.x, camera_position.y, camera_position.z), 'vec3')
    _set(shader, locs['time'], time, 'float')
    _set(shader, locs['fogColor'], FOG, 'vec3')
    _set(shader, locs['fogDensity'], fog_density, 'float')
    sky_loc = rl.get_shader_location(_Shared.sky_shader, 'fogColor')
    _set(_Shared.sky_shader, sky_loc, FOG, 'vec3')
    rl.rl_disable_backface_culling()
    rl.rl_disable_depth_mask()
    rl.draw_model(_Shared.sky, camera_position, 1, rl.WHITE)
    rl.rl_enable_depth_mask()
    rl.rl_enable_backface_culling()
    rl.draw_model(_Shared.model, rl.Vector3(0, 0, 0), 1, rl.WHITE)


def release():
    if _Shared.model is None:
        return
    rl.unload_model(_Shared.model)
    rl.unload_shader(_Shared.shader)
    _Shared.sky.materials[0].shader = rl.Shader()
    rl.unload_model(_Shared.sky)
    rl.unload_shader(_Shared.sky_shader)
    _Shared.model = _Shared.shader = _Shared.sky = _Shared.sky_shader = None


class DistrictScenery(Renderable3D):
    def __init__(self):
        self.time = 0.0

    def init(self):
        super().init()
        configure_depth()

    def render(self):
        self.time += rl.get_frame_time()
        position = self.camera.rl_camera.position if self.camera else rl.Vector3(0, 10, 0)
        draw_district(position, self.time)

    def on_destroy(self):
        super().on_destroy()
        release()
