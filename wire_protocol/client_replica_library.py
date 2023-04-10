
config =[('127.0.0.1', 6000, 1), ('127.0.0.1', 6001, 2)]
import protocol
import socket
from uuid import uuid4

class Client_Replica_Library:
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
                self.protocol.send(this_socket, self.protocol.encode('REGISTER_CLIENT_UUID', msg_count, {'uuid': uuid}))
            except:
                print("couldnt send")
                continue
            msg_count += 1
            
            self.sockets[item[2]] = this_socket
            #Set primary correctly
            print("UDPATEING SOCKET")
        self.primary = this_socket
        if (len(self.sockets) == 0):
            raise ConnectionError("Connection Failed")
        return msg_count
     
    def disconnect(self):
        for socket in self.sockets.values:
            socket.close()
        
    def readFromServer(self, process_operation):
        def process_switch(client_socket, metadata: protocol.Metadata, msg, id_accum):    
            operation_code = metadata.operation_code.value
            args = self.protocol.parse_data(operation_code, msg)
            match operation_code:
                case 14: # Switch Primary
                    self.primary = self.sockets[('host', 'port')]
                case _: 
                    process_operation(client_socket, metadata, msg, id_accum)
        value = self.protocol.read_packets(self.primary, process_switch)
        if (value is None):
            for socket in self.sockets.values():
                ack = self.protocol.read_small_packets(socket)
                if (ack is None):
                    continue
                else:
                    (md, msg) = ack
                    self.primary = self.sockets(int(self.protocol.parse_data(md.operation_code, msg)['id']))
                    break
    
    def send(self, message):
        self.protocol.send(self.primary, message)




            
          



