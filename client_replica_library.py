
from uuid import uuid4
import socket
import protocol
config = [('127.0.0.1', 6000, 1), ('127.0.0.1',
                                   6001, 2), ('127.0.0.1', 6002, 3)]


class ClientReplicaLibrary:
    def __init__(self, protocol):
        self.sockets = {}
        self.primary = None
        self.protocol = protocol

    def connect_to_service(self, msg_counter, uuid):
        msg_count = msg_counter
        print("connecting")
        for item in config:
            this_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            host = item[0]
            port = item[1]
            try:
                this_socket.connect((host, port))
            except:
                print("Couldn't connect")
            try:
                self.protocol.send(this_socket, self.protocol.encode(
                    'REGISTER_CLIENT_UUID', msg_count, {'uuid': uuid}))
            except:
                print("Couldn't send")
                continue
            msg_count += 1

            self.sockets[item[2]] = this_socket
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
