import grpc
import chat_service_pb2_grpc
from client import Client

if __name__ == '__main__':
    host = input('Enter host: ')
    port = int(input('Enter port: '))

    with grpc.insecure_channel(f'{host}:{port}') as channel:
        stub = chat_service_pb2_grpc.ChatServiceStub(channel)
        client = Client(stub)
        print('Connected to server')

        client.run()
