"""Preferências locais do jogador (``saves/config.json``), como o idioma da dublagem.

Ainda não há tela de opções: para trocar a dublagem edite ``saves/config.json``
(``{"voice_language": "en"}``) ou defina a variável de ambiente ``CELLS_VOICE=en``.
Uma futura tela deve chamar ``set_value("voice_language", ...)``; o ``AudioFeedback``
percebe a mudança e recarrega as vozes sozinho. Erros de leitura/escrita nunca
impedem o jogo de abrir.
"""
import json
import os
from pathlib import Path

PATH = Path("saves/config.json")
VOICE_LANGUAGES = {"ja": "Japonês (original)", "en": "Inglês (dublagem)"}
DEFAULTS = {"voice_language": "ja", "voice_volume": 1.0, "sfx_volume": 1.0, "record_replay": False}

_cache = None
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


def get(key):
    if key == "voice_language" and os.environ.get("CELLS_VOICE") in VOICE_LANGUAGES:
        return os.environ["CELLS_VOICE"]
    value = load().get(key, DEFAULTS[key])
    if key == "voice_language" and value not in VOICE_LANGUAGES:
        return DEFAULTS[key]
    return value


def set_value(key, value):
    global revision
    data = load()
    data[key] = value
    revision += 1
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
