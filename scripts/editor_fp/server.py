"""Editor das animações de primeira pessoa (braços com esqueleto: Macrófaga, Célula B).

    .venv\\Scripts\\python.exe scripts\\editor_fp\\server.py [--port 8765] [--no-browser]
    (ou dois cliques em "Editor Animacao 1a Pessoa.bat", na raiz do projeto)

Abre uma página no navegador (three.js). A pose é calculada AQUI, com o mesmo código do jogo
(``UserComponents/cells/fp_arms.py`` e ``weapons.gun_matrix``): o que aparece no editor é o que
aparece no jogo. "Salvar" grava ``Assets/Weapons/<herói>_fp_anim.json``, que o jogo lê (e relê
sozinho se estiver aberto). Uma cópia da versão anterior vai para ``.scratch/fp_anim_backups/``.
"""
import argparse
import json
import math
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from UserComponents.cells import fp_arms  # noqa: E402
from UserComponents.cells.models import _compose  # noqa: E402
from UserComponents.cells.weapons import ASSET_DIR, gun_matrix, m_rows, part_local  # noqa: E402

BACKUP_DIR = ROOT / '.scratch' / 'fp_anim_backups'
STATIC = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/index.html': ('index.html', 'text/html; charset=utf-8'),
          '/editor.js': ('editor.js', 'text/javascript; charset=utf-8')}
SAMPLES = 96  # quadros da recarga no "bake" (0..1)


class Hero:
    """Dados fixos de um herói: arma (peças e pose de repouso) e esqueleto dos braços."""

    def __init__(self, key):
        self.key = key
        self.weapon = json.loads((ASSET_DIR / f'{key}.json').read_text(encoding='utf-8'))
        self.fp = m_rows(self.weapon['fp'])
        self.parts = [SimpleNamespace(name=e['name'], anim=e.get('anim', 'static'),
                                      pivot=tuple(e.get('pivot', (0.0, 0.0, 0.0))),
                                      axis=tuple(e.get('axis', (0.0, 0.0, 1.0))), amount=float(e.get('amount', 0.0)))
                      for e in self.weapon['parts']]
        self.meta = fp_arms.load_meta(key)
        self.rigs = {s: fp_arms.HandRig(self.meta, s) for s in ('R', 'L')}

    def info(self):
        return dict(hero=self.key, kind=self.weapon['kind'], parts=[p.name for p in self.parts],
                    animated=[p.name for p in self.parts if p.anim != 'static'],
                    anims={p.name: p.anim for p in self.parts},
                    bones=self.meta['bones'], hands=self.meta['hands'],
                    wrist_limits={'x': fp_arms.WRIST_X, 'y': fp_arms.WRIST_Y})


def r5(v):
    return [round(x, 5) for x in v]


def flat(m):
    (r, t) = m
    return r5((r[0][0], r[0][1], r[0][2], t[0], r[1][0], r[1][1], r[1][2], t[1], r[2][0], r[2][1], r[2][2], t[2]))


def frame(h, cfg, p):
    """Um quadro: matriz da arma, peças, ossos e cartucho, tudo no espaço da vista (câmera na origem)."""
    if p is None:
        st, (roll, pitch, yaw, x, y, z), bump = {}, (0.0,) * 6, 0.0
    else:
        st, bump = fp_arms.reload_state(h.key, p, cfg)
        roll, pitch, yaw, x, y, z = fp_arms.reload_offsets(h.key, p, cfg)
    gun = gun_matrix(h.fp, x, y + bump, z, pitch, yaw, roll)
    locals_ = {part.name: part_local(part, st) for part in h.parts}

    def space(name):
        local = locals_.get(name) if name else None
        return gun if local is None else _compose(gun, local)

    arms = fp_arms.Arms(h.key, cfg)
    bones = {name: r5(head) + r5(fp_arms.quat(rot)) for name, head, rot in arms.pose(h.rigs, space, p)}
    shell = [r5(arms.shell[0]), r5(arms.shell[1])] if arms.shell else None
    # Pulso por mão: [flexão, desvio usados, flexão, desvio que o IK pedia] (graus).
    wrist = {s: [round(v, 2) for v in (*use, *need)] for s, (use, need) in arms.wrist.items()}
    return dict(p=p, gun=flat(gun), parts={k: flat(v) for k, v in locals_.items() if v is not None},
                bones=bones, shell=shell, wrist=wrist, state={k: round(v, 5) for k, v in st.items()})


def check_parts(h, cfg):
    names = {p.name for p in h.parts}
    for g in cfg['grips'].values():
        if g.part is not None and g.part not in names:
            raise ValueError(f'grips.{g.name}.part: a arma não tem a peça {g.part!r} (tem: {sorted(names)})')


def solved(h, cfg):
    """Ângulos dos dedos (graus) que o resolvedor acha para cada empunhadura, por mão."""
    out = {}
    for side, rig in h.rigs.items():
        out[side] = {name: {f: [round(math.degrees(a), 2) for a in v] for f, v in rig.solve(g).items()}
                     for name, g in cfg['grips'].items()}
    return out


class Api:
    def __init__(self):
        self.heroes = {k: Hero(k) for k in fp_arms.HEROES}
        self.lock = threading.Lock()

    def hero(self, key):
        h = self.heroes.get(key)
        if h is None:
            raise ValueError(f'herói desconhecido: {key!r}')
        return h

    def bake(self, body):
        h = self.hero(body.get('hero'))
        cfg = fp_arms.parse_config(body.get('anim'))
        check_parts(h, cfg)
        with self.lock:
            times = body.get('times')
            out = {'ok': True}
            if times is None:
                out['frames'] = [frame(h, cfg, i / SAMPLES) for i in range(SAMPLES + 1)]
                out['idle'] = frame(h, cfg, None)
                out['solved'] = solved(h, cfg)
            else:
                out['frames'] = [frame(h, cfg, None if t is None else float(t)) for t in times]
            return out

    def save(self, body):
        h = self.hero(body.get('hero'))
        data = body.get('anim')
        cfg = fp_arms.parse_config(data)
        check_parts(h, cfg)
        text = fp_arms.dump_anim(data)
        path = fp_arms.anim_path(h.key)
        if path.exists():
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime('%Y%m%d-%H%M%S')
            (BACKUP_DIR / f'{h.key}_{stamp}.json').write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
        tmp = path.with_suffix('.tmp')
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, path)
        return {'ok': True, 'path': str(path.relative_to(ROOT)), 'text': text}


class Handler(BaseHTTPRequestHandler):
    api = None

    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            if url.path in STATIC:
                name, ctype = STATIC[url.path]
                return self.send(200, (HERE / name).read_bytes(), ctype)
            if url.path.startswith('/assets/'):
                name = url.path[len('/assets/'):]
                if '/' in name or '\\' in name or '..' in name or not name.endswith('.glb'):
                    return self.send(404, {'error': 'não encontrado'})
                path = ASSET_DIR / name
                if not path.exists():
                    return self.send(404, {'error': 'não encontrado'})
                return self.send(200, path.read_bytes(), 'model/gltf-binary')
            if url.path == '/api/heroes':
                return self.send(200, [h.info() for h in self.api.heroes.values()])
            if url.path == '/api/anim':
                h = self.api.hero(q.get('hero', [''])[0])
                return self.send(200, json.loads(fp_arms.anim_path(h.key).read_text(encoding='utf-8')))
        except (OSError, ValueError) as exc:
            return self.send(400, {'ok': False, 'error': str(exc)})
        self.send(404, {'error': 'não encontrado'})

    def do_POST(self):
        url = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if url.path == '/api/bake':
                return self.send(200, self.api.bake(body))
            if url.path == '/api/save':
                return self.send(200, self.api.save(body))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            return self.send(200, {'ok': False, 'error': str(exc) or exc.__class__.__name__})
        self.send(404, {'error': 'não encontrado'})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()
    Handler.api = Api()
    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = HTTPServer(('127.0.0.1', port), Handler)
            break
        except OSError:
            continue
    if server is None:
        sys.exit('nenhuma porta livre')
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'Editor de animação de 1ª pessoa em {url}  (Ctrl+C para fechar)', flush=True)
    if not args.no_browser:
        threading.Timer(.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
