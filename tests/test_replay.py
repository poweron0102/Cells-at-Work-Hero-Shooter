"""Gravação de replay no anfitrião e reprodução como espectador (sem janela)."""
import math
from collections import Counter
import shutil
import tempfile
import unittest
from pathlib import Path
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.NewGame import NewGame
from EasyCells3D.NetworkComponents import NetworkManager, NetworkTransform
from UserComponents.cells import replay
from UserComponents.cells.replay import ReplayRecorder, load_replay, open_replay, list_replays
from UserComponents.cells.session import connect
import Levels.replay as replay_level


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(tempfile.mkdtemp(prefix="replay_test_"))
        cls.previous = replay.REPLAY_DIR
        replay.REPLAY_DIR = cls.folder
        game = headless_game()
        net = connect(game, "127.0.0.1", 0, True, "Anfitriao")
        net.start(True)
        arena = mount_arena(game)
        recorder = game.CreateItem().AddComponent(ReplayRecorder(net, arena))
        cls.history = []
        for frame in range(30 * 40):
            step(game, 1/30)
            if frame % 30 == 0:
                cls.history.append((recorder.last_t, {s: a.transform.position.to_tuple for s, a in arena.actors.items()}))
        cls.final = {s: a.transform.position.to_tuple for s, a in arena.actors.items()}
        cls.health = {s: a.health.value for s, a in arena.actors.items()}
        cls.elapsed = arena.state.elapsed
        cls.status = net.status
        cls.path = recorder.path
        game.close()
        cls.data = load_replay(cls.path)
        cls.names = Counter(p[2] for _, packets, _ in cls.data.chunks for p in packets if p[0] == 1)

    @classmethod
    def tearDownClass(cls):
        replay.REPLAY_DIR = cls.previous
        shutil.rmtree(cls.folder, ignore_errors=True)

    def setUp(self):
        # Voltar no tempo remonta a cena "replay"; sem janela, só a arena (sem UI nem efeitos).
        self.init = replay_level.init
        replay_level.init = lambda game: replay_level.build(game, visuals=False)

    def tearDown(self):
        replay_level.init = self.init

    def player(self):
        game = headless_game()
        open_replay(game, self.data)
        director = replay_level.build(game, visuals=False)
        step(game, 1/30)
        return game, director

    def test_file_is_complete_and_listed(self):
        self.assertEqual(self.status, "playing")
        self.assertTrue(self.data.complete)
        self.assertAlmostEqual(self.data.duration, 40, delta=.2)
        self.assertEqual(self.data.skipped, 0)
        self.assertEqual(len(self.data.header["roster"]), 6)
        names = {p[2] for _, packets, _ in self.data.chunks for p in packets if p[0] == 1}
        self.assertIn("sync_transform", names)
        self.assertIn("sync", names)
        self.assertTrue(any(aims for _, _, aims in self.data.chunks))
        listed = list_replays()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["path"], str(self.path))
        self.assertAlmostEqual(listed[0]["duration"], self.data.duration, delta=.1)

    def test_seek_reproduces_host_positions_and_state(self):
        game, director = self.player()
        try:
            self.assertIsNone(game.session.local_slot)
            director.seek(self.data.duration)
            for slot, actor in director.arena.actors.items():
                self.assertLess(math.dist(actor.transform.position.to_tuple, self.final[slot]), .6, slot)
                self.assertEqual(actor.health.value, self.health[slot])
            self.assertAlmostEqual(director.arena.state.elapsed, self.elapsed, delta=.5)
            self.assertEqual(game.session.status, "playing")
        finally:
            game.close()
        self.assertIsNone(NetworkManager.instance)

    def test_real_time_playback_follows_the_recording(self):
        game, director = self.player()
        try:
            director.seek(25)
            shots = 0
            for _ in range(30 * 8):
                step(game, 1/30)
                shots += len(director.arena.tracers)
            t, positions = next((t, p) for t, p in self.history if t >= director.clock - .05)
            for _ in range(int((t - director.clock) * 30) + 1):
                step(game, 1/30)
            for slot, actor in director.arena.actors.items():
                self.assertLess(math.dist(actor.transform.position.to_tuple, positions[slot]), 1.2, slot)
            self.assertGreater(shots, 0)
        finally:
            game.close()

    def test_pause_and_backward_seek_rebuild_the_scene(self):
        game, director = self.player()
        try:
            director.seek(12)
            game.replay.paused = True
            step(game, 1/30)
            self.assertAlmostEqual(director.clock, 12, delta=.01)
            with self.assertRaises(NewGame):
                director.seek(4)
            self.assertEqual(game.replay.seek_to, 4)
            fresh = next(d for d in (item.GetComponent(replay.ReplayDirector) for item in game.item_list) if d)
            self.assertIsNot(fresh, director)
            step(game, 1/30)
            self.assertAlmostEqual(fresh.clock, 4, delta=.01)
        finally:
            game.close()

    def test_host_records_what_clients_send_and_their_aim(self):
        game = headless_game()
        try:
            net = connect(game, "127.0.0.1", 0, True, "Anfitriao")
            net.start(True)
            arena = mount_arena(game)
            recorder = game.CreateItem().AddComponent(ReplayRecorder(net, arena))
            step(game, 1/30)
            actor = arena.actors[1]
            sync = actor.GetComponent(NetworkTransform)
            roster = {k: dict(v) for k, v in net.roster.value.items()}
            roster[1].update(owner=5, bot=False)  # o slot 1 passa a ser de um cliente
            net.roster.value = roster
            step(game, 1/30)
            recorder.pending.clear()
            # Posição de um cliente: o anfitrião repassa aos outros e o gravador guarda uma vez.
            data = sync.serialize()
            sync.cont = 0
            self.assertEqual(sync.handle_incoming_rpc("sync_transform", (data,), 5), "ok")
            self.assertEqual(len(recorder.pending), 1)
            # Mira: só o anfitrião recebe, e só do dono.
            self.assertEqual(actor.handle_incoming_rpc("report_aim", (.42,), 5), "ok")
            self.assertEqual(actor.handle_incoming_rpc("report_aim", (-1.0,), 3), "denied")
            self.assertAlmostEqual(actor.pitch, .42)
            self.assertEqual(len(recorder.pending), 1)
            for _ in range(4):
                step(game, 1/30)
            self.assertTrue(recorder.path.exists())
        finally:
            game.close()
        data = load_replay(recorder.path)
        aims = [aims for _, _, aims in data.chunks if aims]
        self.assertAlmostEqual(aims[-1][1], .42)


if __name__ == "__main__":
    unittest.main()
