from enum import Enum
import errno
import select
import socket
from typing import Callable, Dict, List
import logging

METADATA_SIZES = {
    "version": 1,
    "header_length": 1,
    "operation_code": 1,
    "message_size": 3,
    "payload_size": 2,
    "message_id": 2,
}

METADATA_LENGTH = sum(METADATA_SIZES.values())
MAX_PACKET_SIZE = 2048
MAX_PAYLOAD_SIZE = MAX_PACKET_SIZE - METADATA_LENGTH
VERSION = 1


class OperationCode(Enum):
    CREATE_ACCOUNT = 1
    CREATE_ACCOUNT_RESPONSE = 2
    LIST_ACCOUNTS = 3
    LIST_ACCOUNTS_RESPONSE = 4
    SEND_MESSAGE = 5
    SEND_MESSAGE_RESPONSE = 6
    DELETE_ACCOUNT = 7
    DELETE_ACCOUNT_RESPONSE = 8
    LOG_IN = 9
    LOG_IN_RESPONSE = 10
    LOG_OFF = 11
    LOG_OFF_RESPONSE = 12
    RECV_MESSAGE = 13
    SWITCH_PRIMARY = 14
    GET_PRIMARY = 15
    ASSIGN_PRIMARY = 16
    ASSIGN_PRIMARY_RESPONSE = 17
    UPDATE_ACCOUNT_STATE = 18
    UPDATE_LOGIN_STATE = 19
    UPDATE_MESSAGE_STATE = 20
    REGISTER_CLIENT_UUID = 21
    ACK = 22
    HEARTBEAT = 23
    GET_PRIMARY_RESPONSE = 24

# Necessary arguments needed for each operation
OPERATION_ARGS = {
    'CREATE_ACCOUNT': ['username'],
    'CREATE_ACCOUNT_RESPONSE': ['status', 'username'],
    'LIST_ACCOUNTS': ['query'],
    'LIST_ACCOUNTS_RESPONSE': ['status', 'accounts'],
    'SEND_MESSAGE': ['recipient', 'message'],
    'SEND_MESSAGE_RESPONSE': ['status'],
    'DELETE_ACCOUNT': [],
    'DELETE_ACCOUNT_RESPONSE': ['status'],
    'LOG_IN': ['username'],
    'LOG_IN_RESPONSE': ['status', 'username'],
    'LOG_OFF': [],
    'LOG_OFF_RESPONSE': ['status'],
    'RECV_MESSAGE': ['sender', 'message'],
    'SWITCH_PRIMARY': ['id'],
    'GET_PRIMARY': [],
    'ASSIGN_PRIMARY': [],
    'ASSIGN_PRIMARY_RESPONSE': ['id'],
    'UPDATE_ACCOUNT_STATE': ['add_flag', 'username'],
    'UPDATE_LOGIN_STATE': ['add_flag', 'username', 'uuid'],
    'UPDATE_MESSAGE_STATE': ['add_one', 'recipient', 'sender', 'message'],
    'REGISTER_CLIENT_UUID': ['uuid'],    
    'ACK': [],
    'HEARTBEAT': [],
    'GET_PRIMARY_RESPONSE': ['id'],
}


class Message:
    def __init__(self, version, operation, data):
        self.version = version
        self.operation = operation
        self.data = data

    def __str__(self):
        return f"Version: {self.version}, Operation: {self.operation}, Data: {self.data}"

    def get_version(self) -> int:
        return self.version


class Metadata:
    def __init__(self, version: bytes, header_length: bytes, operation_code: bytes,
                 message_size: bytes, payload_size: bytes, message_id: bytes) -> None:
        self.version = int.from_bytes(version, 'big')
        self.header_length = int.from_bytes(header_length, 'big')
        self.operation_code = OperationCode(
            int.from_bytes(operation_code, 'big'))
        self.message_size = int.from_bytes(message_size, 'big')
        self.payload_size = int.from_bytes(payload_size, 'big')
        self.message_id = int.from_bytes(message_id, 'big')


class Protocol:
    def __init__(self, version: int, metadata_sizes: Dict[str, int]) -> None:
        self.version = version
        self.metadata_sizes = metadata_sizes
        self.header_length = self._get_header_length()

        self.separator = '\r'

    def _get_header_length(self) -> int:
        return self.metadata_sizes['operation_code'] + \
            self.metadata_sizes['message_size'] + \
            self.metadata_sizes['payload_size'] + \
            self.metadata_sizes['message_id']

    def encode(self, operation: OperationCode, message_id: int, operation_args={}) -> List[bytes]:
        """Encode an operation into a list of byte packets to be sent to the server.

        This function just joins the keyword arguments into a data string and passes it to _encode

        Args:
            operation (OperationCode): Enum value of the operation to be encoded.
            message_id (int): The message ID of the resulting message to send.
            operation_args (dict, optional): Dict of key-value arguments for the operation. 
                Refer to OPERATION_ARGS for what arguments are required for each operation. Defaults to {}.

        Raises:
            ValueError: Missing required arguments for target operation.

        Returns:
            List[bytes]: List of bytes representing packets to be sent to the server.
        """
        # Check for necessary arguments
        if set(OPERATION_ARGS[operation]).intersection(set(operation_args.keys())) != set(OPERATION_ARGS[operation]):
            raise ValueError(
                f"Missing arguments for operation {operation}. Required arguments: {OPERATION_ARGS[operation]}")
        # Join keyword arguments with separator
        data = self.separator.join(
            [f"{key}={value}" if key in OPERATION_ARGS[operation] else "" for key, value in operation_args.items()])
        data += '\n'


        # Encode metadata and data into byte packets (may be multiple packets for large messages)
        return self._encode(OperationCode[operation].value, message_id, data)

    def _encode(self, operation: int, message_id: int, data: str) -> List[bytes]:
        """Encode an operation into a list of byte packets to be sent to the server containing the metadata and data.

        The encoding scheme is described in the project README.

        Args:
            operation (int): Operation code of the operation to be encoded.
            message_id (int): The message ID of the resulting message to send.
            data (str): String of data to be encoded.

        Returns:
            List[bytes]: List of bytes representing packets to be sent to the server.
        """
        # Encode data
        encoded_data = self._encode_data(data)
        # Encode metadata
        bytes = bytearray(self._encode_component('version', self.version))
        bytes.extend(self._encode_component(
            'header_length', self.header_length))
        bytes.extend(self._encode_component('operation_code', operation))
        bytes.extend(self._encode_component('message_size', len(encoded_data)))

        encoded_payloads = []

        # Split into payloads of MAX_PAYLOAD_SIZE bytes, all with same common metadata
        for i in range(0, len(encoded_data), MAX_PAYLOAD_SIZE):
            payload = encoded_data[i:i+MAX_PAYLOAD_SIZE]
            # Calculate payload size for this specific payload
            payload_bytes = bytes + \
                self._encode_component('payload_size', len(payload))
            payload_bytes.extend(
                self._encode_component('message_id', message_id))
            payload_bytes.extend(payload)
            encoded_payloads.append(payload_bytes)

        logging.info(
            f"Packet sizes: {sum([len(payload) for payload in encoded_payloads])}")
        return encoded_payloads

    def _encode_component(self, component: str, value: int) -> bytes:
        return value.to_bytes(self.metadata_sizes[component], byteorder='big')

    def _encode_data(self, data: str) -> bytes:
        return data.encode('ascii')

    def send(self, client_socket, message: List[bytes], socket_lock=None) -> bool:
        """Send a list of encoded packets to the client_socket

        Args:
            client_socket (socket.socket): The socket to send the packets to
            message (List[bytes]): List of bytes to send to the client_socket, each representing a packet
            socket_lock (threading.Lock, optional): Thread lock for client if needed. Defaults to None.

        Returns:
            bool: True if all packets were sent successfully, False otherwise
        """
        for packet in message:
            status = self._send_one_packet(
                client_socket, packet, socket_lock)
            if not status:
                return False
        return True
    
    def read_small_packets(self, client_socket):
        try:
            md = bytes()
            while (len(md) < METADATA_LENGTH):
                if (METADATA_LENGTH - len(md) > 0):
                    mdToAdd = client_socket.recv(METADATA_LENGTH - len(md))
                    if (int.from_bytes(mdToAdd, 'big') <= 0):
                        # Socket disconnected
                        return None
                    md += mdToAdd
            packet_md = self.parse_metadata(md)
            payload = bytes()
            while (len(payload) < packet_md.payload_size):
                if (packet_md.payload_size - len(payload) > 0):
                    payloadToAdd = client_socket.recv(packet_md.payload_size - len(payload))
                    if (int.from_bytes(payloadToAdd, 'big') <= 0):
                        # Socket disconnected
                        return None
                    payload += payloadToAdd
            return (packet_md, payload.decode('ascii')[:-1])
        except:
            return None


    def _send_one_packet(self, client_socket, packet: bytes, socket_lock=None) -> bool:
        """Send a single of encoded packet to the client_socket

        Args:
            client_socket (socket.socket): The socket to send the packets to
            packet (bytes): Bytes to send to the client_socket, representing a packet
            socket_lock (threading.Lock, optional): Thread lock for client if needed. Defaults to None.

        Returns:
            bool: True if the packet was sent successfully, False otherwise
        """
        if socket_lock is not None:
            socket_lock.acquire()
        total_sent = 0
        # Send the packet in chunks until all bytes are sent
        while total_sent < len(packet):
            try:
                bytes_sent = client_socket.send(packet, MAX_PACKET_SIZE)
                if bytes_sent == 0:
                    # Socket connection broken
                    if socket_lock is not None:
                        socket_lock.release()
                    return False
                total_sent += bytes_sent
            except socket.error as e:
                # For nonblocking sockets, EAGAIN and EWOULDBLOCK are raised when there is no data to write
                # so we just need to wait for more data This code actually will never run because we are now using
                # blocking sockets.
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                    # Socket connection broken, unknown error
                    if socket_lock is not None:
                        socket_lock.release()
                    return False
                # Wait for client_socket until ready for writing
                select.select([], [client_socket], [])

        if socket_lock is not None:
            socket_lock.release()

        return True

    def parse_data(self, op: int, data: str) -> Dict[str, str]:
        """Parses the data string into a dictionary of keyword arguments for the given operation.

        Args:
            op (int): Operation code
            data (str): Data string to parse

        Returns:
            Dict[str, str]: Key-value pairs of keyword arguments
        """
        kv_pairs = data.split(
            self.separator, len(OPERATION_ARGS[OperationCode(op).name]))
        kv_pairs = [kv_pair for kv_pair in kv_pairs if kv_pair]
        return dict(map(lambda x: tuple(x.split("=", 1)), kv_pairs))

    def parse_metadata(self, bytes: bytes) -> Metadata:
        """
            Takes in a bytes object and parses the metadata at the beginning according to the specifications.
        """
        return Metadata(bytes[0:1], bytes[1:2], bytes[2:3], bytes[3:6], bytes[6:8], bytes[8:10])

    def read_packets(self, client: socket.socket, message_processor: Callable) -> None:
        """Continuously reads packets from the client and calls message_processor on each completed message.

        Here packet refers to a single data transmission from the client which contains a header (metadata) and a payload.
        A singular message may be split into multiple packets, each packet only contains a portion of one message.
        Each recv call may return bytes that make up multiple packets, and a single packet may be split up among multiple recv calls,
        so we need to keep track of the current message we are building and the leftover bytes from the last recv call.

        Args:
            client (socket.socket): The socket to read from.
            message_processor (Callable): The function to call on each completed message.
                The function should take in the message metadata, data, and message ID for outbound messages.
        """
        curr_msg_id = -1
        curr_op = -1
        msg_id_accum = 0

        # Leftover bytes after the last complete packet in the last recv call.
        # ALWAYS starts with a header (though may be incomplete).
        left_over_packet = bytes()
        running_msg = ""

        # Infinite loop to read packets
        while True:
            try:
                received_data = client.recv(MAX_PACKET_SIZE)
                if (int.from_bytes(received_data, 'big') <= 0):
                    # Socket disconnected
                    return None
                curr_msg_to_parse = left_over_packet + received_data
                if (len(curr_msg_to_parse) < METADATA_LENGTH):
                    left_over_packet = curr_msg_to_parse
                else:
                    # Keeps track of whether we should continue reading the next packet in this recv output
                    # Set to false if we don't have the whole packet yet and need to wait for the rest
                    continue_packet_iteration = True

                    while continue_packet_iteration and len(curr_msg_to_parse) > METADATA_LENGTH:
                        # Invariant here is that we at least have the metadata available
                        packet_metadata = self.parse_metadata(curr_msg_to_parse)
                        if packet_metadata.version != VERSION:
                            return None
                        else:
                            # Read current packet's payload and add it to the running message
                            curr_payload_size = packet_metadata.payload_size

                            # Check if we have the whole packet
                            if (len(curr_msg_to_parse[METADATA_LENGTH:]) < curr_payload_size):
                                # We don't have the whole payload yet, so we need to wait to receive the next packet
                                continue_packet_iteration = False
                            else:
                                # Whole packet available, parse payload size of the built up msg starting from after the metadata
                                packet_to_parse = curr_msg_to_parse[METADATA_LENGTH:
                                                                    curr_payload_size + METADATA_LENGTH]
                                incomplete_msg = packet_to_parse.decode(
                                    'ascii')
                                # Check if this is a continuation of the current running message
                                if (curr_msg_id == packet_metadata.message_id and curr_op == packet_metadata.operation_code):
                                    running_msg += incomplete_msg
                                else:
                                    # Else this is a new message
                                    running_msg = incomplete_msg
                                    curr_msg_id = packet_metadata.message_id
                                    curr_op = packet_metadata.operation_code
                                # If running msg is done, then do something based on metadata
                                if (running_msg[-1] == '\n'):
                                    message_processor(client, packet_metadata, running_msg[:-1],
                                                    msg_id_accum)
                                    msg_id_accum += 1
                                    curr_msg_id = -1
                                    curr_op = -1
                                    running_msg = ''
                                # Once we've processed the current packet, we want to set the curr_msg_to_parse
                                # to be the rest of the received, and then continue iterating to process the rest of the packets
                                curr_msg_to_parse = curr_msg_to_parse[curr_payload_size +
                                                                    METADATA_LENGTH:]
                    left_over_packet = curr_msg_to_parse
            except:
                return None


protocol_instance = Protocol(VERSION, METADATA_SIZES)
