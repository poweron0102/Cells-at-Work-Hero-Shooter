"""One of six separate Python processes in the LAN integration check."""
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.network import connect
from UserComponents.cells.catalog import CELLS


def run(role, port, output):
    game = headless_game()
    net = connect(game, "127.0.0.1", int(port), role == "host", role)
    started = time.monotonic()
    arena = None
    phases, positions, deaths = set(), [], []
    frames = 0
    previous_snapshot = None
    injected = set()
    try:
        while time.monotonic()-started < 20:
            step(game)
            if role == "host":
                if len(net.roster) == 6 and not arena:
                    net.start()
                    arena = mount_arena(game)
                if arena and arena.actors[0].__dict__.get("weapon"):
                    elapsed = arena.state.elapsed
                    if elapsed > 1 and "breach" not in injected:
                        injected.add("breach")
                        arena.state.capture = [100, 100, 0]
                    if elapsed > 2 and "antigen" not in injected:
                        injected.add("antigen")
                        macro = next(a for a in arena.actors.values() if a.hero == "macrophage")
                        arena.samples = [dict(pos=macro.transform.position.to_tuple, life=20) for _ in range(2)]
                        arena.collect(macro)
                    if elapsed > 3 and "damage" not in injected:
                        injected.add("damage")
                        arena.actors[3].damage(1000, arena.actors[0])
                    if elapsed > 10 and "event" not in injected:
                        injected.add("event")
                        arena.state.next_event = 0
                    if elapsed > 18:
                        break
            elif net.local_slot is not None:
                player = net.roster[net.local_slot]
                # Includes forged state fields: the host must ignore these.
                net.input(dict(x=0, z=1 if frames < 100 else 0,
                               yaw=0 if player["team"] == CELLS else math.pi, pitch=0,
                               fire=False, health=99999, winner="bacteria"))
                if net.latest and net.latest is not previous_snapshot:
                    previous_snapshot = net.latest
                    phases.add(net.latest["state"]["phase"])
                    a = net.latest["actors"][net.local_slot]
                    positions.append(a["pos"])
                    deaths.append(a["alive"])
                    assert a["health"] < 99999
                    frames += 1
                    if net.latest["state"]["elapsed"] > 17:
                        break
            time.sleep(.004)
        if role == "host":
            assert arena is not None, "Six peers failed to join"
            assert len(net.roster) == 6
            assert arena.state.phase == 2
            assert arena.state.recognition >= 50
            assert arena.actors[3].deaths == 1 and arena.actors[3].alive
            assert arena.state.event_index >= 1
            report = dict(role=role, peers=6, phase=arena.state.phase, respawn=True, event=True)
        else:
            assert phases == {0, 1, 2}, phases
            assert len(positions) > 20
            assert max(p[2] for p in positions)-min(p[2] for p in positions) > .5
            report = dict(role=role, slot=net.local_slot, snapshots=frames, phases=sorted(phases), movement=True,
                          saw_death=False in deaths, saw_respawn=False in deaths and deaths[-1])
        Path(output).write_text(json.dumps(report, indent=2), encoding="utf8")
    finally:
        game.close()


if __name__ == "__main__":
    run(*sys.argv[1:])
