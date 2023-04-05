
from concurrent import futures

import grpc
import chat_service_pb2_grpc
from server import ChatServiceServicer

HOST = '[::]'
PORT = 6000


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(
        ChatServiceServicer(), server)
    server.add_insecure_port(f'{HOST}:{PORT}')
    server.start()
    print(f"Server started on {HOST}:{PORT}")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
