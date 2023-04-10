import unittest
import protocol
import socket
from unittest.mock import MagicMock

METADATA_SIZES = {
    "version": 1,
    "header_length": 1,
    "operation_code": 1,
    "message_size": 3,
    "payload_size": 2,
    "message_id": 2,
}

METADATA_LENGTH = sum(METADATA_SIZES.values())


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.protocol = protocol.protocol_instance

    def test_read_packets(self):
        encoding = self.protocol.encode(
            'CREATE_ACCOUNT', 0, {'username': 'kevin'})[0]
        client = MagicMock()
        processFn = MagicMock(return_value=True)
        md = self.protocol.parse_metadata(encoding)
        m = MagicMock()
        zero = 0
        m.side_effect = [encoding, zero.to_bytes(2, 'big')]
        client.recv = m
        self.protocol.read_packets(client, processFn)
        curr_payload_size = md.payload_size
        packet_to_parse = encoding[METADATA_LENGTH:
                                   curr_payload_size + METADATA_LENGTH]
        incomplete_msg = packet_to_parse.decode(
            'ascii')
        processFn.assert_called_with(
            client, unittest.mock.ANY, incomplete_msg[:-1], 0)

    def test_read_packets_broken_up(self):
        encoding = self.protocol.encode(
            'CREATE_ACCOUNT', 0, {'username': 'kevin'})[0]
        client = MagicMock()
        processFn = MagicMock(return_value=True)
        md = self.protocol.parse_metadata(encoding)
        m = MagicMock()
        zero = 0
        m.side_effect = [
            encoding[:len(encoding)//2], encoding[len(encoding)//2:], zero.to_bytes(2, 'big')]
        client.recv = m
        self.protocol.read_packets(client, processFn)
        curr_payload_size = md.payload_size
        packet_to_parse = encoding[METADATA_LENGTH:
                                   curr_payload_size + METADATA_LENGTH]
        incomplete_msg = packet_to_parse.decode(
            'ascii')
        processFn.assert_called_with(
            client, unittest.mock.ANY, incomplete_msg[:-1], 0)
        
    def test_read_packets_multi_msg(self):
        encoding1 = self.protocol.encode(
            'CREATE_ACCOUNT', 0, {'username': 'kevin'})[0]
        encoding2 = self.protocol.encode(
            'CREATE_ACCOUNT', 1, {'username': 'joseph'})[0]
        client = MagicMock()
        processFn = MagicMock(return_value=True)
        md = self.protocol.parse_metadata(encoding2)
        m = MagicMock()
        zero = 0
        m.side_effect = [encoding1 + encoding2, zero.to_bytes(2, 'big')]
        client.recv = m
        self.protocol.read_packets(client, processFn)
        curr_payload_size = md.payload_size
        packet_to_parse = encoding2[METADATA_LENGTH:
                                   curr_payload_size + METADATA_LENGTH]
        incomplete_msg = packet_to_parse.decode(
            'ascii')
        processFn.assert_called_with(
            client, unittest.mock.ANY, incomplete_msg[:-1], 1)
    
    def test_read_packets_single_msg_multiple_recv(self):
        encoding1 = self.protocol.encode(
            'CREATE_ACCOUNT', 0, {'username': 'kevin' * 2048})
        client = MagicMock()
        processFn = MagicMock(return_value=True)
        m = MagicMock()
        zero = 0
        m.side_effect = encoding1 + [zero.to_bytes(2, 'big')]
        client.recv = m
        self.protocol.read_packets(client, processFn)

        processFn.assert_called_with(
            client, unittest.mock.ANY, 'username=' + 'kevin'*2048, 0)

    def test_parse_data(self):
        data = 'recipient=kevin\rmessage=hello'
        parse = self.protocol.parse_data(5, data)
        self.assertEqual(parse['recipient'], 'kevin')
        self.assertEqual(parse['message'], 'hello')

    def test_parse_metadata(self):
        encoding = self.protocol.encode(
            'CREATE_ACCOUNT', 0, {'username': 'kevin'})[0]
        md = self.protocol.parse_metadata(encoding)
        self.assertEqual(md.header_length, 8)
        self.assertEqual(md.message_id, 0)
        self.assertEqual(md.message_size, 15)
        self.assertEqual(md.operation_code,
                         protocol.OperationCode.CREATE_ACCOUNT)
        self.assertEqual(md.payload_size, 15)
        self.assertEqual(md.version, 1)


if __name__ == '__main__':
    unittest.main()
