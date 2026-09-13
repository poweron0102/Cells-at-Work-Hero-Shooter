"""Archive all images on official character pages; install full-body portraits."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1] / 'Assets' / 'characters'
SITE = 'https://cellsatwork-anime.com'
PAGES = [SITE + '/1st/character/', SITE + '/character/']
PORTRAITS = {'red_blood_cell': 'erythrocyte', 'neutrophil': 'leukocyte',
            'killer_t': 'killer_t_cell', 'macrophage': 'macrophage', 'platelet': 'platelet',
            'b_cell': 'b_cell', 'pneumococcus': 's_pneumoniae',
            'staphylococcus': 's_aureus', 'pseudomonas': 's_aeruginosa',
            'streptococcus': 's_pyogenes'}
SEASON_TWO = {'red_blood_cell': '01', 'neutrophil': '02', 'killer_t': '03',
              'macrophage': '04', 'platelet': '05'}


class Links(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.page, self.images, self.pages = page, set(), set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('src', 'href', 'data-src'):
            url = urljoin(self.page, attrs.get(key, ''))
            parsed = urlparse(url)
            if parsed.netloc != 'cellsatwork-anime.com':
                continue
            if '/assets/img/character/' in parsed.path and parsed.path.endswith(('.png', '.jpg', '.jpeg')):
                self.images.add(url)
            if tag == 'a' and '/character/' in parsed.path and (
                    parsed.path.endswith('.html') or parsed.path.rstrip('/').split('/')[-1].isdigit()):
                self.pages.add(url)


def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'CellsAtWork-reference-archive/1.0'}), timeout=40) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise


def parse(page):
    parser = Links(page)
    parser.feed(fetch(page).decode('utf-8'))
    return parser


def archive(url):
    path = ROOT / 'official' / urlparse(url).path.lstrip('/')
    if not path.exists():
        data = fetch(url)
        if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')):
            raise ValueError(f'Invalid image: {url}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    return dict(url=url, file=path.relative_to(ROOT).as_posix(), bytes=len(data), sha256=sha256(data).hexdigest())


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        indices = list(pool.map(parse, PAGES))
        pages = sorted(set().union(*(p.pages for p in indices)))
        print(f'Reading {len(pages)} character detail pages...', flush=True)
        details = list(pool.map(parse, pages))
        images = set().union(*(p.images for p in indices + details))
        aliases = {name: f'{SITE}/1st/assets/img/character/{slug}/stand.png' for name, slug in PORTRAITS.items()}
        aliases.update({name: f'{SITE}/assets/img/character/chara_{number}.png' for name, number in SEASON_TWO.items()})
        images.update(aliases.values())
        print(f'Archiving {len(images)} images (existing files are cached)...', flush=True)
        records = list(pool.map(archive, sorted(images)))
    by_url = {r['url']: r for r in records}
    for name, url in aliases.items():
        (ROOT / f'{name}.png').write_bytes((ROOT / by_url[url]['file']).read_bytes())
    (ROOT / 'manifest.json').write_text(json.dumps(dict(pages=PAGES + pages, images=records, portraits=aliases), indent=2), encoding='utf-8')
    print(f'Archived {len(records)} images from {len(pages)+2} character pages; installed {len(aliases)} portraits.', flush=True)


if __name__ == '__main__':
    main()
