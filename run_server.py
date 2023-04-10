import server
import socket
import threading
import protocol
import sys


if __name__ == '__main__':
    host = sys.argv[1]
    port = int(sys.argv[2])
    id = int(sys.argv[3])
    server = server.Server(
        host, port, protocol.protocol_instance, id)
    try:
        server.run()
    except KeyboardInterrupt:
        server.disconnect()
        print('Server dropped')
