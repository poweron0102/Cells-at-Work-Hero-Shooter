"""One of six processes exercising client decisions and native replication."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from EasyCells3D.NetworkComponents import NetworkComponent, NetworkTransform, Rpc, SendTo
from UserComponents.cells.session import connect
from UserComponents.cells.catalog import BALANCE, CELLS

COLONY_SPOT = (-53, 0, -30)


class Scenario(NetworkComponent):
    """Arrange reproducible situations on every test peer; not shipped with the game."""
    def __init__(self, arena):
        super().__init__(9000, 0)
        self.arena = arena

    @Rpc(send_to=SendTo.ALL)
    def prepare(self):
        a = self.arena
        for actor in a.actors.values():
            actor.controls = {}
        for slot, position in ((1, (0, 1, 40)), (3, (0, 1, 34)), (4, (COLONY_SPOT[0], 1, COLONY_SPOT[2]))):
            actor = a.actors[slot]
            if actor.local:
                actor.body.teleport(Vec3(*position))
                actor.yaw = actor.pitch = 0

    @Rpc(send_to=SendTo.ALL)
    def build_on_client(self):
        """Slot 4 (a client) asks the host to build; the host validates and replicates it."""
        actor = self.arena.actors[4]
        if actor.local:
            self.arena.request_build(4, COLONY_SPOT)


def run(role, port, output):
    game = headless_game()
    net = connect(game, "127.0.0.1", int(port), role == "host", role)
    started = time.monotonic()
    arena = scenario = None
    injected = set()
    local_start = None
    moved_without_receive = False
    saw_death = saw_respawn = saw_colony = saw_escort = saw_closed = False
    paused_until = 0
    disconnected = False
    bot_start = None
    try:
        while time.monotonic()-started < 32:
            if net.manager.is_server and len(net.roster.value) == 6 and arena is None:
                net.start()
            if net.status == "loading" and arena is None:
                arena = mount_arena(game)
                scenario = game.CreateItem().AddComponent(Scenario(arena))
            step(game)
            if arena is None or net.status == "loading":
                time.sleep(.004)
                continue
            actor = arena.actors[net.local_slot]
            state = arena.state
            elapsed = state.elapsed
            if local_start is None:
                local_start = actor.transform.position.to_tuple
                actor.controls = dict(x=1, fire=True)
                paused_until = game.run_time+.25
                if role != "host":
                    net.manager.enable = False  # No host responses during local movement/firing.
            if game.run_time >= paused_until and "local" not in injected:
                injected.add("local")
                moved_without_receive = abs(actor.transform.x-local_start[0]) > .4
                assert moved_without_receive and actor.shot > 0, ("Local movement/fire waited for the host", actor.slot, actor.transform.position.to_tuple, local_start, actor.shot)
                actor.weapon.reload()
                assert actor.weapon.reload_time > 0, "Reload waited for the host"
                actor.charge = 100
                actor.ultimate()
                assert actor.charge == 0, "Special waited for the host"
                net.manager.enable = True
                actor.controls = {}
            if role == "host":
                if elapsed > 1 and "prepare" not in injected:
                    injected.add("prepare")
                    scenario.prepare()
                if elapsed > 2 and "resources" not in injected:
                    injected.add("resources")
                    state.resources[4] = BALANCE['colony_cost']
                    cell = arena.actors[0]
                    arena.add_drop('antigen', cell.feet, 1)
                if elapsed > 2.6 and "build" not in injected:
                    injected.add("build")
                    scenario.build_on_client()
                if elapsed > 15 and "finish" not in injected:
                    injected.add("finish")
                    # Close the wound, destroy every colony and eliminate the bacteria.
                    state.escort = state.escort_total
                    state.wound_closed = True
                    for colony in list(state.colonies):
                        state.damage_colony(colony['id'], 1e6)
                if "finish" in injected:
                    for other in arena.actors.values():
                        if other.team != CELLS and other.alive:
                            other.damage(5000, arena.actors[0])
            if actor.slot == 1 and elapsed > 2 and arena.actors[3].deaths.value == 0:
                actor.controls = dict(yaw=0, pitch=0, fire=True)
            elif elapsed > 2:
                actor.controls = {}
            saw_death |= not arena.actors[3].alive
            saw_respawn |= saw_death and arena.actors[3].alive
            saw_colony |= any(c['owner'] == 4 for c in state.colonies)
            saw_escort |= state.escort > 1
            saw_closed |= state.wound_closed
            if net.roster.value[5]["bot"] and bot_start is None:
                bot = arena.actors[5]
                bot_start = (bot.GetComponent(NetworkTransform).cont, bot.transform.position.to_tuple)
            if actor.slot == 5 and elapsed > 13:
                disconnected = True
                break
            if net.status == "results":
                break
            time.sleep(.004)
        assert saw_escort, "Escort progress was not replicated"
        assert saw_colony, ("Client colony request was not validated/replicated", actor.slot)
        assert saw_death and saw_respawn, ("Client hit/death/respawn did not propagate", actor.slot, saw_death, saw_respawn, arena.actors[3].health.value, arena.actors[3].deaths.value, arena.actors[1].shot)
        assert arena.actors[3].deaths.value >= 1
        assert arena.actors[1].kills.value >= 1
        assert arena.state.recognition >= BALANCE['antigen_per_sample'], arena.state.recognition
        transform = actor.GetComponent(NetworkTransform)
        assert transform.owner == net.manager.id and transform.cont > 0
        if not disconnected:
            assert saw_closed
            assert net.status == "results", "Match never finished"
            result = net.result["state"]
            assert result["winner"] == "cells"
            for key in ("winner", "wound_closed", "colonies", "recognition"):
                assert arena.state.serialize()[key] == result[key], ("Objective state diverged between peers", key)
            assert net.roster.value[5]["bot"], "Disconnected player was not replaced"
            assert arena.actors[5].GetComponent(NetworkTransform).owner == 0
            bot = arena.actors[5]
            assert bot.GetComponent(NetworkTransform).cont > bot_start[0]
            assert (bot.transform.position-Vec3(*bot_start[1])).magnitude() > .1
            for other in arena.actors.values():
                if other.slot != actor.slot:
                    assert other.GetComponent(NetworkTransform).cont > 0, "No remote UDP movement received"
        report = dict(role=role, slot=actor.slot, local_without_receive=moved_without_receive, colony=saw_colony,
                      escort=round(arena.state.escort, 1), death_respawn=saw_respawn, disconnect=disconnected,
                      transform_sequence=transform.cont, result=net.result)
        Path(output).write_text(json.dumps(report, indent=2), encoding="utf8")
    finally:
        game.close()


if __name__ == "__main__":
    run(*sys.argv[1:])
