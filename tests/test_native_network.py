"""Regression tests for the engine APIs used by the multiplayer components."""
from types import SimpleNamespace
from struct import pack
import unittest
from unittest.mock import Mock

from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3
from EasyCells3D.NetworkComponents import NetworkComponent, NetworkManager, NetworkTransform, Rpc, SendTo
from EasyCells3D.NetworkComponents.NetworkComponent import Protocol
from simulation_support import headless_game, step


class HostCommand(NetworkComponent):
    def __init__(self):
        super().__init__(991, 0)
        self.calls = 0

    @Rpc(send_to=SendTo.SERVER)
    def execute(self):
        self.calls += 1


class InitCounter(Component):
    def __init__(self):
        self.calls = 0

    def init(self):
        self.calls += 1


class NativeNetworkTests(unittest.TestCase):
    def tearDown(self):
        NetworkManager.instance = None

    def test_server_rpc_executes_for_local_host_once(self):
        NetworkManager.instance = SimpleNamespace(is_server=True, id=0)
        command = HostCommand()
        command.execute()
        self.assertEqual(command.calls, 1)

    def test_owner_check_rejects_other_peers(self):
        NetworkManager.instance = SimpleNamespace(is_server=True, id=0)
        command = HostCommand()
        command.owner = 2
        command.handle_incoming_rpc("execute", (), sender_id=1)
        self.assertEqual(command.calls, 0)
        command.handle_incoming_rpc("execute", (), sender_id=2)
        self.assertEqual(command.calls, 1)

    def test_pending_init_survives_for_persistent_network_item(self):
        game = headless_game()
        try:
            root = game.CreateItem()
            root.destroy_on_load = False
            counter = root.CreateChild().AddComponent(InitCounter())
            game.new_game(game.level, supress=True)
            step(game)
            self.assertEqual(counter.calls, 1)
        finally:
            game.close()

    def make_transform(self, game, identifier, **kwargs):
        return game.CreateItem().AddComponent(NetworkTransform(
            identifier, owner=0, sync_rot_x=False, sync_rot_y=False, sync_rot_z=False,
            sync_scale_x=False, sync_scale_y=False, sync_scale_z=False, **kwargs))

    def test_network_transform_interpolates_and_snaps_respawn(self):
        game = headless_game()
        NetworkManager.instance = SimpleNamespace(is_server=False, id=1)
        try:
            transform = self.make_transform(game, 992, interpolation_speed=10)
            transform.deserialize(pack("ifff", 1, 2, 0, 0))
            self.assertEqual(transform.transform.x, 0)
            game.delta_time = .05
            transform.loop()
            self.assertAlmostEqual(transform.transform.x, 1)
            transform.deserialize(pack("ifff", 2, 25, 1, 10))
            self.assertEqual(transform.transform.x, 25)
            transform.deserialize(pack("ifff", 1, -100, 0, 0))
            self.assertEqual(transform.transform.x, 25, "Old UDP packets must not undo respawn")
        finally:
            game.close()

    def test_stationary_transform_recovers_after_initial_udp_packet_is_lost(self):
        game = headless_game()
        manager = SimpleNamespace(is_server=True, id=0, broadcast=Mock())
        NetworkManager.instance = manager
        try:
            sender = self.make_transform(game, 993)
            receiver = self.make_transform(game, 994)
            sender.transform.position = Vec3(7, 1, 9)
            sender.init()
            for _ in range(40):
                game.run_time += 1/60
                game.scheduler.update()
            packets = manager.broadcast.call_args_list
            self.assertGreaterEqual(len(packets), 2)
            # Discard the first datagram, like a client whose scene isn't ready yet.
            packet, protocol = packets[-1].args
            self.assertEqual(protocol, Protocol.UDP)
            receiver.deserialize(packet[3][0])
            self.assertEqual(receiver.transform.position.to_tuple, (7, 1, 9))
            sender.item.Destroy()
            count = manager.broadcast.call_count
            game.run_time += 1
            game.scheduler.update()
            self.assertEqual(manager.broadcast.call_count, count)
        finally:
            game.close()

    def test_clients_cannot_write_server_owned_transform(self):
        game = headless_game()
        NetworkManager.instance = SimpleNamespace(is_server=True, id=0)
        try:
            transform = self.make_transform(game, 995)
            transform.handle_incoming_rpc("sync_transform", (pack("ifff", 1, 100, 100, 100),), sender_id=4)
            self.assertEqual(transform.transform.position.to_tuple, (0, 0, 0))
        finally:
            game.close()

    def test_owner_transfer_starts_sending_and_stops_interpolating(self):
        game = headless_game()
        manager = SimpleNamespace(is_server=True, id=0, broadcast=Mock())
        NetworkManager.instance = manager
        try:
            transform = self.make_transform(game, 996, interpolation_speed=10)
            transform.owner = 2
            transform.init()
            game.scheduler.update()
            self.assertFalse(manager.broadcast.called)
            transform.deserialize(pack("ifff", 50, 2, 0, 0))
            transform.owner = 0
            transform.loop()
            self.assertIsNone(transform._target_position)
            game.run_time += .1
            game.scheduler.update()
            self.assertTrue(manager.broadcast.called)
            self.assertGreater(transform.cont, 50)
        finally:
            game.close()


if __name__ == "__main__":
    unittest.main()
