
from uuid import uuid4
import socket
import protocol


class ClientReplicaLibrary:
    def __init__(self, protocol, server_configs):
        self.sockets = {}
        self.primary = None
        self.protocol = protocol

        self.config = [(config['host'], config['port'], config['id'])
                       for config in server_configs]

    def connect_to_service(self, msg_counter, uuid):
        """Connect to each server in the config and register the client."""
        msg_count = msg_counter
        print("Connecting...")
        for host, port, id in self.config:
            this_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                this_socket.connect((host, port))
            except:
                print(f"Couldn't connect to server at {host}:{port}.")
            try:
                self.protocol.send(this_socket, self.protocol.encode(
                    'REGISTER_CLIENT_UUID', msg_count, {'uuid': uuid}))
            except:
                print(f"Couldn't register client to server at {host}:{port}.")
                continue
            msg_count += 1

            self.sockets[id] = this_socket
            # Set primary correctly
        if (len(self.sockets) == 0):
            raise ConnectionError("Connection Failed")
        return self._get_primary(msg_count)

    def disconnect(self):
        for socket in self.sockets.values:
            socket.close()

    def readFromServer(self, process_operation):
        while not self.primary is None:
            value = self.protocol.read_packets(self.primary, process_operation)
            print(value)
            if (value is None):
                print("Changing primary")
                self.primary = None
                for socket in self.sockets.values():
                    ack = self.protocol.read_small_packets(socket)
                    if (ack is None):
                        continue
                    else:
                        (md, msg) = ack
                        self.primary = self.sockets[int(
                            self.protocol.parse_data(md.operation_code, msg)['id'])]
                        print(f"New primary {self.primary}")
                        break
        self.disconnect()
        print("Disconnected from server")

    def _get_primary(self, msg_counter):
        msg_count = msg_counter
        for socket in self.sockets.values():
            self.protocol.send(socket, self.protocol.encode(
                'GET_PRIMARY', msg_count))
            msg_count += 1
            ack = self.protocol.read_small_packets(socket)
            if (ack is None):
                continue
            else:
                (md, msg) = ack
                self.primary = self.sockets[int(
                    self.protocol.parse_data(md.operation_code, msg)['id'])]
                print(int(self.protocol.parse_data(
                    md.operation_code, msg)['id']))
                break
        return msg_count

    def send(self, message):
        self.protocol.send(self.primary, message)
