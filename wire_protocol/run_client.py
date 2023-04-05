import client
import protocol

if __name__ == '__main__':
    host = input('Enter host: ')
    port = int(input('Enter port: '))

    client_instance = client.Client(host, port, protocol.protocol_instance)

    try:
        client_instance.connect()
        client_instance.run()
    except KeyboardInterrupt:
        client_instance.disconnect()
        print('Disconnected from server.')
    except Exception as e:
        client_instance.disconnect()
        print('Disconnected from server. Please try again later.')
