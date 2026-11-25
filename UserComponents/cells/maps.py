"""Mapas jogáveis e os modos de objetivo de cada um.

Cada mapa vive em ``Assets/Maps/<pasta>/`` (``<arquivo>.glb``, ``runtime.json`` e ``nav.json``),
gerado pelos scripts de ``referencias/scripts/mapa/``. O anfitrião escolhe o mapa no lobby; a
escolha viaja numa variável de rede da sessão e ``layout.select`` carrega os marcadores antes de
montar a arena.

Modos (o lado bacteriano é o mesmo em todos: colônias, infecção, recursos e antígenos):

* ``escort``   plaquetas avançam até a ferida; ao chegar, a entrada bacteriana fecha.
* ``convoy``   comboio de hemácias com CO2 atravessa o coração até o pulmão; as valvas abrem e
               fecham no ritmo do batimento e uma colônia junto a uma valva a emperra fechada.
* ``training`` eritroblastos fazem o treino de entrega na medula; atingidos, largam a caixa e
               voltam chorando ao berçário; a formatura de várias crianças sela a entrada.
"""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAPS_DIR = ROOT/'Assets'/'Maps'


@dataclass(frozen=True)
class MapInfo:
    key: str
    folder: str
    title: str        # nome curto (HUD e lobby)
    episode: str      # referência do anime
    mode: str
    blurb: str        # uma linha para o lobby

    @property
    def path(self):
        return MAPS_DIR/self.folder

    @property
    def model_file(self):
        return f'{self.folder}.glb'

    def exists(self):
        return (self.path/'runtime.json').exists() and (self.path/self.model_file).exists()


MAPS = {
    'bairro': MapInfo('bairro', 'BairroArterial', 'Bairro Arterial', 'S01E02', 'escort',
                      'Canais e pontes; plaquetas até a ferida.'),
    'timo': MapInfo('timo', 'Timo', 'Timo', 'S01E09', 'escort',
                    'Campo de treino e labirinto; plaquetas até a ferida.'),
    'medula': MapInfo('medula', 'MedulaOssea', 'Medula Óssea', 'S01E06', 'training',
                      'Berçário; proteja o treino de entrega dos eritroblastos.'),
    'coracao': MapInfo('coracao', 'Coracao', 'Coração', 'S01E08', 'convoy',
                       'Átrio direito; o comboio só passa com a valva aberta.'),
}
ORDER = ('bairro', 'timo', 'medula', 'coracao')
DEFAULT = 'bairro'

# Textos do objetivo das células em cada modo (HUD sem acentos: a fonte da HUD é só ASCII).
MODES = {
    'escort': dict(
        objective='ESCOLTA', payload='plaquetas', target='ferida', unit='m',
        sealed='FERIDA FECHADA', sealed_short='ferida fechada', result='ESCOLTA',
        start='Escolte as plaquetas ate a ferida',
        announce='FERIDA FECHADA - a entrada bacteriana foi selada',
        win_reason='escolta, colonias e infeccao'),
    'convoy': dict(
        objective='COMBOIO', payload='comboio', target='pulmao', unit='m',
        sealed='CIRCULACAO RESTABELECIDA', sealed_short='circulacao restabelecida', result='COMBOIO',
        start='Leve o comboio de hemacias ate o pulmao',
        announce='CIRCULACAO RESTABELECIDA - a lesao do endocardio foi selada',
        win_reason='comboio, valvas e colonias'),
    'training': dict(
        objective='FORMATURA', payload='eritroblastos', target='formatura', unit='',
        sealed='MEDULA EM ALERTA', sealed_short='medula em alerta', result='FORMATURA',
        start='Proteja o treino de entrega dos eritroblastos',
        announce='FORMATURA! A medula entrou em alerta e selou a entrada bacteriana',
        win_reason='formatura, colonias e infeccao'),
}


def info(key):
    return MAPS.get(key) or MAPS[DEFAULT]


def available():
    """Mapas exportados (com GLB e runtime.json), na ordem do lobby."""
    return [k for k in ORDER if MAPS[k].exists()]


def next_map(key, step=1):
    keys = available() or [DEFAULT]
    i = keys.index(key) if key in keys else 0
    return keys[(i+step) % len(keys)]
