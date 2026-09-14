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


class Scenario(NetworkComponent):
    """Arrange reproducible combat on every test peer; not shipped with the game."""
    def __init__(self, arena):
        super().__init__(9000, 0)
        self.arena = arena

    @Rpc(send_to=SendTo.ALL)
    def prepare(self):
        a = self.arena
        a.state.capture = [100, 100, 0]
        a.state.next_event = 1
        for actor in a.actors.values():
            actor.controls = {}
        for slot, position in ((1, (0, 1, 20)), (3, (0, 1, 14))):
            actor = a.actors[slot]
            if actor.local:
                actor.body.teleport(Vec3(*position))
                actor.yaw = actor.pitch = 0

    @Rpc(send_to=SendTo.ALL)
    def samples(self):
        a = self.arena
        macro = next(actor for actor in a.actors.values() if actor.hero == "macrophage")
        a.samples = [dict(id=(99, i), pos=macro.transform.position.to_tuple, life=24) for i in range(2)]
        if macro.local:
            a.collect(macro)


def run(role, port, output):
    game = headless_game()
    net = connect(game, "127.0.0.1", int(port), role == "host", role)
    started = time.monotonic()
    arena = scenario = None
    phases, injected = set(), set()
    local_start = None
    moved_without_receive = False
    saw_death = saw_respawn = False
    paused_until = 0
    disconnected = False
    bot_start = None
    try:
        while time.monotonic()-started < 30:
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
            elapsed = arena.state.elapsed
            phases.add(arena.state.phase)
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
                actor.ability()
                actor.weapon.reload()
                assert actor.ability_cd > 0 and actor.weapon.reload_time > 0, "Ability/reload waited for the host"
                if actor.slot == 1:
                    actor.ultimate()
                    assert actor.reveal == 9 and actor.special_cd == 45, "Ultimate waited for the host"
                net.manager.enable = True
                actor.controls = {}
            if role == "host":
                if elapsed > 1 and "prepare" not in injected:
                    injected.add("prepare")
                    scenario.prepare()
                if elapsed > 2 and "samples" not in injected:
                    injected.add("samples")
                    scenario.samples()
                if elapsed > 15 and "finish" not in injected:
                    injected.add("finish")
                    arena.damage_core(0, 1000)
                    arena.damage_core(1, 1000)
            if actor.slot == 1 and elapsed > 2 and arena.actors[3].deaths.value == 0:
                actor.controls = dict(yaw=0, pitch=0, fire=True)
            elif elapsed > 2:
                actor.controls = {}
            saw_death |= not arena.actors[3].alive
            saw_respawn |= saw_death and arena.actors[3].alive
            if net.roster.value[5]["bot"] and bot_start is None:
                bot = arena.actors[5]
                bot_start = (bot.GetComponent(NetworkTransform).cont, bot.transform.position.to_tuple)
            if actor.slot == 5 and elapsed > 13:
                disconnected = True
                break
            if net.status == "results":
                break
            time.sleep(.004)
        assert phases == {0, 1, 2}, phases
        assert saw_death and saw_respawn, ("Client hit/death/respawn did not propagate", actor.slot, saw_death, saw_respawn, arena.actors[3].health.value, arena.actors[3].deaths.value, arena.actors[1].shot)
        assert arena.actors[3].deaths.value == 1
        assert arena.actors[1].kills.value == 1
        assert arena.state.event_index >= 1
        assert arena.state.recognition >= 50
        transform = actor.GetComponent(NetworkTransform)
        assert transform.owner == net.manager.id and transform.cont > 0
        if not disconnected:
            assert net.status == "results", "Match never finished"
            assert net.result["state"]["winner"] == "cells"
            assert arena.state.serialize() == net.result["state"], "Objective rules diverged between peers"
            assert net.roster.value[5]["bot"], "Disconnected player was not replaced"
            assert arena.actors[5].GetComponent(NetworkTransform).owner == 0
            bot = arena.actors[5]
            assert bot.GetComponent(NetworkTransform).cont > bot_start[0]
            assert (bot.transform.position-Vec3(*bot_start[1])).magnitude() > .1
            for other in arena.actors.values():
                if other.slot != actor.slot:
                    assert other.GetComponent(NetworkTransform).cont > 0, "No remote UDP movement received"
        report = dict(role=role, slot=actor.slot, phases=sorted(phases), local_without_receive=moved_without_receive,
                      death_respawn=saw_respawn, disconnect=disconnected, transform_sequence=transform.cont,
                      result=net.result)
        Path(output).write_text(json.dumps(report, indent=2), encoding="utf8")
    finally:
        game.close()


if __name__ == "__main__":
    run(*sys.argv[1:])
