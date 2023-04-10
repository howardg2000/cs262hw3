import unittest
from unittest.mock import call, patch, MagicMock

from client_replica_library import ClientReplicaLibrary


class TestClientReplicaLibrary(unittest.TestCase):

    def setUp(self):
        self.protocol = MagicMock()
        self.server_configs = [{'host': 'localhost', 'port': 8000, 'id': 1},
                               {'host': 'localhost', 'port': 8001, 'id': 2},
                               {'host': 'localhost', 'port': 8002, 'id': 3}]
        self.client_replica_library = ClientReplicaLibrary(self.protocol,
                                                           self.server_configs)

    def tearDown(self):
        pass

    def test_connect_to_service_successful(self):
        msg_counter = 1
        uuid = '1234'
        mock_md = MagicMock(operation_code=1)
        self.protocol.read_small_packets.return_value = (mock_md, 'msg')
        self.protocol.encode.return_value = b'REGISTER_CLIENT_UUID'
        self.protocol.parse_data.return_value = {'id': '1'}
        with patch('socket.socket') as mock_socket:
            mock_connect = mock_socket.return_value.connect
            mock_send = self.protocol.send
            self.client_replica_library.connect_to_service(msg_counter, uuid)
            self.assertEqual(mock_socket.call_count, 3)
            mock_connect.assert_has_calls(
                [call(('localhost', 8000)), call(('localhost', 8001)), call(('localhost', 8002))])

    def test_connect_to_service_connection_failed(self):
        msg_counter = 1
        uuid = '1234'
        mock_md = MagicMock(operation_code=1)
        self.protocol.read_small_packets.return_value = (mock_md, 'msg')
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.connect.side_effect = ConnectionRefusedError
            self.client_replica_library.connect_to_service(
                msg_counter, uuid)
            self.assertEqual(mock_socket.call_count, 3)

    def test_send(self):
        message = b'message'
        mock_send = self.protocol.send
        self.client_replica_library.send(message)
        mock_send.assert_called_with(
            self.client_replica_library.primary, message)


if __name__ == '__main__':
    unittest.main()
