import server
import socket
import threading
import protocol

HOST = ''
PORT = 6000

if __name__ == '__main__':
    other_servers = [('', 6001), ('', 6002)]
    server_id = 0
    server = server.Server(
        HOST, PORT, protocol.protocol_instance, other_servers, server_id)
    try:
        server.run()
    except KeyboardInterrupt:
        server.disconnect()
        print('Server dropped')
