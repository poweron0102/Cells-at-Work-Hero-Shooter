import pickle
import socket
import unittest
from EasyCells3D.NetworkTCP import NetworkServerTCP


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.local, self.remote = socket.socketpair()
        self.server = NetworkServerTCP.__new__(NetworkServerTCP)
        self.server.clients = [None, self.local]
        self.server._buffers = {}

    def tearDown(self):
        self.local.close()
        self.remote.close()

    def test_disconnect_clears_slot_without_renumbering(self):
        self.remote.close()
        self.assertIsNone(self.server.read(1))
        self.assertIsNone(self.server.clients[1])
        self.assertEqual(len(self.server.clients), 2)

    def test_fragmented_and_coalesced_packets(self):
        data = pickle.dumps({"command": [1, 0, True]})
        frame = len(data).to_bytes(4, "big") + data
        self.remote.sendall(frame[:2])
        self.assertIsNone(self.server.read(1))
        self.remote.sendall(frame[2:7])
        self.assertIsNone(self.server.read(1))
        self.remote.sendall(frame[7:] + frame)
        self.assertEqual(self.server.read(1), {"command": [1, 0, True]})
        self.assertEqual(self.server.read(1), {"command": [1, 0, True]})

    def test_executable_objects_are_rejected(self):
        data = pickle.dumps(len)
        self.remote.sendall(len(data).to_bytes(4, "big") + data)
        self.assertIsNone(self.server.read(1))
        self.assertIsNone(self.server.clients[1])

    def test_oversized_packet_closes_only_that_peer(self):
        self.remote.sendall((2_000_000).to_bytes(4, "big"))
        self.assertIsNone(self.server.read(1))
        self.assertIsNone(self.server.clients[1])


if __name__ == "__main__":
    unittest.main()
