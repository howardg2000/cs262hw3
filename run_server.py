import server
import json
import protocol
import sys


if __name__ == '__main__':
    config_file = sys.argv[1]
    id = int(sys.argv[2])
    with open(config_file, 'r') as f:
        config = json.load(f)
    server = server.Server(
        config["servers"], id, protocol.protocol_instance)
    try:
        server.run()
    except KeyboardInterrupt:
        server.disconnect()
        print('Server dropped')
