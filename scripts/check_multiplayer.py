"""Run one host and five real clients on loopback, with authoritative simulation."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / ".scratch" / "network-check"
    output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    processes, logs = [], []
    try:
        for i, role in enumerate(["host", "client1", "client2", "client3", "client4", "client5"]):
            log = (output/f"{role}.log").open("w", encoding="utf8")
            logs.append(log)
            args = [sys.executable, "tests/network_peer.py", role, str(port), str(output/f"{role}.json")]
            processes.append(subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            if i == 0:
                time.sleep(.8)
        failures = []
        for i, process in enumerate(processes):
            if process.wait(timeout=35) != 0:
                failures.append(i)
        for log in logs:
            log.flush()
        for i, log in enumerate(logs):
            text = Path(log.name).read_text(encoding="utf8")
            if any(marker in text for marker in ("Traceback", "Error in ", "Erro processando pacote")) and i not in failures:
                failures.append(i)
        if failures:
            for i in failures:
                print(Path(logs[i].name).read_text(encoding="utf8"))
            raise SystemExit("Multiplayer integration failed")
        for role in ["host", "client1", "client2", "client3", "client4", "client5"]:
            print((output/f"{role}.json").read_text(encoding="utf8"))
        print("PASS: one host + five clients; native RPCs (TCP), NetworkTransform (UDP), phases, antigen, death/respawn and event.")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
