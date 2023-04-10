import server
import socket
import threading
import protocol

if __name__ == '__main__':
    other_servers = [] #[('', 6001), ('', 6002)]
    host = input(f'Enter host for this machine: ')
    port = int(input(f'Enter port for this machine: '))
    id = int(input(f'Enter id for this machine: '))
    server = server.Server(
        host, port, protocol.protocol_instance, id)
    try:
        server.run()
    except KeyboardInterrupt:
        server.disconnect()
        print('Server dropped')
