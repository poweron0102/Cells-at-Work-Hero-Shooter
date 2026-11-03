"""Registro opcional de todo o tráfego de rede (RPCs e NetworkVariables) em JSON Lines.

Desligado por padrão: o custo, quando desligado, é um único ``if RpcLog.enabled``.
Liga com ``main.py --rpc-log [ARQUIVO]`` ou com a variável de ambiente
``EASYCELLS_RPC_LOG`` (``1`` usa o caminho padrão; qualquer outro valor é o arquivo).
Abra o arquivo gerado em ``Visualizador RPC.html``.
"""
import atexit
import json
import os
import pickle
import threading
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs") / "rpc"
ENV_VAR = "EASYCELLS_RPC_LOG"
_FLUSH_INTERVAL = 0.5
_MAX_ARGS_CHARS = 4000
TCP_HEADER = 4  # NetworkTCP.SIZE_SIZE: prefixo de tamanho de cada quadro TCP


def _json_default(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return f"<bytes {len(raw)}: {raw[:32].hex()}{'…' if len(raw) > 32 else ''}>"
    if isinstance(value, (set, frozenset)):
        return list(value)
    return repr(value)


def _encode_args(args):
    try:
        text = json.dumps(args, default=_json_default, ensure_ascii=False)
    except (TypeError, ValueError):
        text = json.dumps(repr(args), ensure_ascii=False)
    if len(text) > _MAX_ARGS_CHARS:
        text = json.dumps(text[:_MAX_ARGS_CHARS] + f"… (+{len(text) - _MAX_ARGS_CHARS} chars)")
    return text


class RpcLog:
    enabled = False
    path: Path | None = None
    _file = None
    _lock = threading.Lock()
    _seq = 0
    _start = 0.0
    _last_flush = 0.0
    _cause: int | None = None  # seq do pacote recebido que está sendo processado

    @classmethod
    def enable(cls, path: str | os.PathLike | None = None):
        """Começa a gravar em ``path`` (ou em logs/rpc/rpc_<data>_<pid>.jsonl)."""
        cls.disable()
        if path is None or str(path) in ("", "1"):
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = LOG_DIR / f"rpc_{stamp}_{os.getpid()}.jsonl"
        cls.path = Path(path).resolve()
        cls.path.parent.mkdir(parents=True, exist_ok=True)
        cls._file = open(cls.path, "w", encoding="utf-8", buffering=1 << 16)
        cls._seq = 0
        cls._start = cls._last_flush = time.perf_counter()
        cls.enabled = True
        cls._write({"type": "session", "started": datetime.now().isoformat(timespec="milliseconds"),
                    "pid": os.getpid()})
        print(f"[RpcLog] gravando tráfego de rede em {cls.path}")
        return cls.path

    @classmethod
    def enable_from_env(cls):
        value = os.environ.get(ENV_VAR, "").strip()
        if value and value.lower() not in ("0", "false", "off") and not cls.enabled:
            cls.enable(value)

    @classmethod
    def disable(cls):
        with cls._lock:
            cls.enabled = False
            if cls._file is not None:
                cls._file.close()
                cls._file = None

    @classmethod
    def flush(cls):
        with cls._lock:
            if cls._file is not None:
                cls._file.flush()

    # --- Gravação ---

    @classmethod
    def _write(cls, record: dict, args_json: str | None = None):
        line = json.dumps(record, ensure_ascii=False, default=_json_default)
        if args_json is not None:
            line = line[:-1] + ', "args": ' + args_json + "}"
        with cls._lock:
            if cls._file is None:
                return
            cls._file.write(line + "\n")
            now = time.perf_counter()
            if now - cls._last_flush >= _FLUSH_INTERVAL:
                cls._file.flush()
                cls._last_flush = now

    @classmethod
    def _base(cls, nm, direction: str, packet, protocol) -> tuple[dict, str] | None:
        try:
            op_code, target_id, payload, args = packet
        except (TypeError, ValueError):
            return None
        from EasyCells3D.NetworkComponents.NetworkComponent import OP_RPC, OP_VAR, VAR_SET, VAR_GET
        proto = getattr(protocol, "name", str(protocol))
        size = cls._size(packet, proto)
        cls._seq += 1
        record = {
            "type": "packet",
            "seq": cls._seq,
            "t": round(time.perf_counter() - cls._start, 4),
            "dir": direction,
            "role": "server" if nm.is_server else "client",
            "peer": nm.id,
            "op": "RPC" if op_code == OP_RPC else "VAR" if op_code == OP_VAR else str(op_code),
            "target": target_id,
            "protocol": proto,
            "size": size,
            "wire": size + TCP_HEADER if proto == "TCP" and size >= 0 else size,
        }
        if op_code == OP_RPC:
            record["name"] = payload
            send_to = cls._rpc_send_to(target_id, payload)
            if send_to:
                record["send_to"] = send_to
        else:
            record["name"] = {VAR_SET: "SET", VAR_GET: "GET"}.get(payload, str(payload))
        args_json = _encode_args(args)
        return record, args_json

    @staticmethod
    def _size(packet, proto: str) -> int:
        try:
            # Mesma serialização dos transportes: TCP usa protocolo 4, UDP o padrão.
            return len(pickle.dumps(packet, protocol=4 if proto == "TCP" else pickle.DEFAULT_PROTOCOL))
        except Exception:
            return -1

    @staticmethod
    def _rpc_send_to(target_id, method_name) -> str | None:
        from EasyCells3D.NetworkComponents.NetworkComponent import NetworkComponent, STATIC_NET_ID
        if target_id == STATIC_NET_ID:
            method = NetworkComponent._static_rpcs.get(method_name)
        else:
            component = NetworkComponent._active_components.get(target_id)
            method = getattr(component, method_name, None) if component is not None else None
        config = getattr(method, "_rpc_config", None)
        return config["send_to"].name if config else None

    @classmethod
    def log_send(cls, nm, packet, protocol, dest: str, recipients: int = 1):
        base = cls._base(nm, "out", packet, protocol)
        if base is None:
            return
        record, args_json = base
        record["dest"] = dest
        record["recipients"] = recipients
        if cls._cause is not None:
            record["cause"] = cls._cause
        cls._write(record, args_json)

    @classmethod
    def begin_receive(cls, nm, packet, sender_id: int, protocol):
        """Numera o pacote recebido antes do processamento, para ligar a ele os envios que causar."""
        base = cls._base(nm, "in", packet, protocol)
        if base is None:
            return None
        record, args_json = base
        record["from"] = sender_id
        previous, cls._cause = cls._cause, record["seq"]
        return record, args_json, previous

    @classmethod
    def end_receive(cls, entry, status: str):
        if entry is None:
            return
        record, args_json, previous = entry
        cls._cause = previous
        record["status"] = status
        cls._write(record, args_json)


atexit.register(RpcLog.disable)
