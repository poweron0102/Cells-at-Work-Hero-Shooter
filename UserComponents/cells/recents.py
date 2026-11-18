"""Nomes e IPs usados recentemente, salvos só neste computador (``saves/recentes.json``).

Cada lista guarda ``{"value", "t"}`` (t = horário Unix do último uso), do mais recente
para o mais antigo. Erros de leitura/escrita nunca impedem o jogo de abrir.
"""
import json
import time
from pathlib import Path

PATH = Path("saves/recentes.json")
LIMIT = 6
KINDS = ("names", "ips")


def load():
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    clean = {}
    for kind in KINDS:
        entries = data.get(kind, []) if isinstance(data, dict) else []
        clean[kind] = [dict(value=str(e["value"]), t=float(e.get("t", 0)))
                       for e in entries if isinstance(e, dict) and str(e.get("value", "")).strip()][:LIMIT]
    return clean


def _save(data):
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def push(kind, value):
    """Coloca ``value`` no topo da lista (sem duplicar) e salva."""
    value = value.strip()
    data = load()
    if value:
        data[kind] = [dict(value=value, t=time.time())] + [e for e in data[kind] if e["value"] != value]
        data[kind] = data[kind][:LIMIT]
        _save(data)
    return data


def remove(kind, value):
    data = load()
    data[kind] = [e for e in data[kind] if e["value"] != value]
    _save(data)
    return data


def when(t, now=None):
    """Rótulo curto de quando foi usado: hoje, ontem, há 3 dias..."""
    if not t:
        return ""
    now = now or time.time()
    days = int(time.strftime("%j", time.localtime(now))) - int(time.strftime("%j", time.localtime(t)))
    days += 365 * (time.localtime(now).tm_year - time.localtime(t).tm_year)
    if days <= 0:
        return "hoje"
    if days == 1:
        return "ontem"
    if days < 7:
        return f"há {days} dias"
    if days < 14:
        return "semana passada"
    return f"há {days // 7} semanas"
