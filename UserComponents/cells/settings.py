"""Preferências locais do jogador (``saves/config.json``): vídeo, áudio, controles e jogo.

A tela de configurações (``options.SettingsScreen``) chama ``set_value``; quem depende de
uma preferência lê ``get`` (barato: um dicionário em memória) ou compara ``revision`` para
reagir a mudanças, como o ``AudioFeedback`` que recarrega as vozes sozinho. Valores
corrompidos ou fora da faixa no arquivo voltam ao padrão, e erros de leitura/escrita nunca
impedem o jogo de abrir. ``CELLS_VOICE=en`` ainda força a dublagem pela linha de comando.
"""
import json
import os
import re
from pathlib import Path

PATH = Path("saves/config.json")
VOICE_LANGUAGES = {"ja": "Japonês (original)", "en": "Inglês (dublagem)"}
DEFAULTS = {
    # vídeo
    "display_mode": "window", "resolution": "1280x720", "fps_limit": 60, "vsync": False, "fov": 75,
    "shadow_quality": "high", "show_fps": False,
    # áudio
    "master_volume": 1.0, "sfx_volume": 1.0, "voice_volume": 1.0, "voice_language": "ja",
    # controles
    "mouse_sensitivity": 1.0, "zoom_sensitivity": .45, "invert_y": False,
    # jogo
    "record_replay": False, "map": "bairro",
}
CHOICES = {
    "voice_language": tuple(VOICE_LANGUAGES),
    "display_mode": ("window", "borderless"),
    "fps_limit": (30, 60, 120, 144, 165, 240, 0),  # 0 = sem limite
    "shadow_quality": ("low", "medium", "high"),
}
RANGES = {
    "master_volume": (0.0, 1.0), "sfx_volume": (0.0, 1.0), "voice_volume": (0.0, 1.0),
    "fov": (60, 110), "mouse_sensitivity": (.1, 4.0), "zoom_sensitivity": (.1, 1.5),
}
RESOLUTION = re.compile(r"^\d{3,5}x\d{3,5}$")

_cache = None
_dirty = False
revision = 0  # muda a cada set_value(); quem depende das preferências compara


def load():
    global _cache
    if _cache is None:
        try:
            data = json.loads(PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        _cache = dict(DEFAULTS)
        if isinstance(data, dict):
            _cache.update({k: v for k, v in data.items() if k in DEFAULTS})
    return _cache


def sanitize(key, value):
    """``value`` se for válido para ``key``; senão o padrão."""
    default = DEFAULTS[key]
    if key in CHOICES:
        return value if value in CHOICES[key] and type(value) is type(default) else default
    if key in RANGES:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            return default
        lo, hi = RANGES[key]
        value = max(lo, min(hi, value))
        return int(round(value)) if isinstance(default, int) else float(value)
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if key == "resolution":
        return value if isinstance(value, str) and RESOLUTION.match(value) else default
    return value if isinstance(value, type(default)) else default


def get(key):
    if key == "voice_language" and os.environ.get("CELLS_VOICE") in VOICE_LANGUAGES:
        return os.environ["CELLS_VOICE"]
    return sanitize(key, load().get(key, DEFAULTS[key]))


def set_value(key, value, save_now=True):
    """Muda a preferência. ``save_now=False`` adia a gravação (sliders sendo arrastados);
    chame ``save()`` depois."""
    global revision, _dirty
    data = load()
    value = sanitize(key, value)
    if data.get(key) == value and type(data.get(key)) is type(value):
        return
    data[key] = value
    revision += 1
    _dirty = True
    if save_now:
        save()


def save():
    global _dirty
    if not _dirty or _cache is None:
        return
    _dirty = False
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def reset(keys):
    """Volta as chaves ``keys`` ao padrão (botão "Restaurar padrões" de cada aba)."""
    for key in keys:
        set_value(key, DEFAULTS[key], save_now=False)
    save()
