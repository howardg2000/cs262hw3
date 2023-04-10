import client
import protocol
import sys
import json

if __name__ == '__main__':
    config_file = sys.argv[1]
    with open(config_file, 'r') as f:
        config = json.load(f)
    client_instance = client.Client(
        protocol.protocol_instance, config['servers'])
    try:
        client_instance.connect()
        client_instance.run()
    except KeyboardInterrupt:
        client_instance.disconnect()
        print('Disconnected from server.')
    except Exception as e:
        client_instance.disconnect()
        print(e)
        print('Disconnected from server. Please try again later.')
