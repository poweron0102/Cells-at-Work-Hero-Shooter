"""TCP identities survive reversed UDP handshakes, retries and disconnects."""
import time
import unittest
from unittest.mock import Mock

from EasyCells3D.NetworkComponents import NetworkComponent, NetworkManager, Rpc, SendTo, Protocol
from EasyCells3D.NetworkComponents.NetworkComponent import OP_RPC
from EasyCells3D.Transport import TcpTransport, UdpTransport
from simulation_support import headless_game, step


class PeerProbe(NetworkComponent):
    def __init__(self):
        super().__init__(777, owner=2)
        self.received = []

    @Rpc(send_to=SendTo.NOT_ME, protocol=Protocol.UDP)
    def record(self, value):
        self.received.append(value)


class UdpIdentityTests(unittest.TestCase):
    def setUp(self):
        self.game = headless_game()
        self.disconnected = Mock()
        self.manager = self.game.CreateItem().AddComponent(NetworkManager(
            "127.0.0.1", 0, True, disconnect_callback=self.disconnected))
        self.probe = self.game.CreateItem().AddComponent(PeerProbe())
        self.clients = []
        step(self.game)

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.game.close()

    def until(self, condition):
        deadline = time.monotonic()+3
        while not condition():
            self.assertLess(time.monotonic(), deadline, "Networking timed out")
            step(self.game)
            time.sleep(.005)

    def tcp(self):
        client = TcpTransport("127.0.0.1", self.manager.port, 4, False, lambda _: None)
        self.clients.append(client)
        self.until(lambda: client._impl.connected)
        return client

    def udp(self, tcp):
        client = UdpTransport("127.0.0.1", self.manager.port, 4, False, lambda _: None, tcp)
        self.clients.append(client)
        self.until(lambda: client._impl.id is not None)
        return client

    def test_reversed_handshakes_route_owner_rpc_and_exclude_actual_sender(self):
        first, second = self.tcp(), self.tcp()
        udp_second, udp_first = self.udp(second), self.udp(first)
        self.assertEqual((udp_first._impl.id, udp_second._impl.id), (1, 2))
        packet = (OP_RPC, 777, "record", ("second peer",))
        udp_second.send(packet)
        self.until(lambda: self.probe.received == ["second peer"])
        received = []

        def relayed():
            data = udp_first.read()
            if data is not None:
                received.append(data)
            return bool(received)

        self.until(relayed)
        self.assertEqual(received, [packet])
        self.assertIsNone(udp_second.read(), "NOT_ME echoed to the sender")
        step(self.game)
        second.close()
        self.until(lambda: self.disconnected.called)
        self.disconnected.assert_called_once_with(2)
        self.assertIsNone(self.manager.transports[Protocol.UDP].clients[2])
        third = self.tcp()
        self.assertEqual(self.udp(third)._impl.id, 3)

    def test_lost_handshake_acknowledgement_is_replied_to_again(self):
        tcp = self.tcp()
        server = self.manager.transports[Protocol.UDP]._impl
        send = server.send
        calls = []

        def lose_first_ack(data, peer):
            calls.append((data, peer))
            if len(calls) == 1:
                send((OP_RPC, 777, "record", ("before handshake",)), peer)
            else:
                send(data, peer)

        server.send = lose_first_ack
        udp = self.udp(tcp)
        self.assertEqual(udp._impl.id, tcp._impl.id)
        self.assertEqual(calls[:2], [(1, 1), (1, 1)])
        self.assertEqual(len(server.clients), 2)


if __name__ == "__main__":
    unittest.main()
