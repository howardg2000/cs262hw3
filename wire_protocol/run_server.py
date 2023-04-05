import server
import socket
import threading
import protocol

HOST = ''
PORT = 6000

if __name__ == '__main__':
    server = server.Server(HOST, PORT, protocol.protocol_instance)
    try:
        server.run()
    except KeyboardInterrupt:
        server.disconnect()
        print('Server dropped')
