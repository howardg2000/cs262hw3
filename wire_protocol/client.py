import socket
from time import sleep
import time
import protocol
import threading
from typing import Literal
import logging
import uuid
import client_replica_library

std_out_lock = threading.Lock()


class Client:
    def __init__(self, protocol):
        self.client_library = client_replica_library.Client_Replica_Library(protocol)
        self.protocol = protocol
        self.message_counter = 0
        self.uuid = str(uuid.uuid4())
        self.username = None

    def connect(self):
        """
        Starts a socket and starts a thread to connect to the client and receive messages
        """
        try:
            self.message_counter = self.client_library.connect_to_service(self.message_counter, self.uuid)
            # Create a thread to listen continuously listen to server and respond to server messages
            thread = threading.Thread(
                target=self.listen_to_server, daemon=True)
            thread.start()
            print('Connected to server')
        except:
            raise ConnectionError('Connection failed')

    def disconnect(self):
        self.client_library.disconnect()

    def listen_to_server(self):
        """
        Listens to the server and processes the received messages
        """
        self.client_library.readFromServer(self.process_operation_curry(std_out_lock))

    def _get_prompt(self):
        command_line_prefix = f'{self.username} >' if self.username else '>'
        return f"{command_line_prefix} Enter command (type 'help' for list of commands): "

    def run(self):
        """
        Handles the user's inputs to the command line, and for each possible command
        sends out a request to the server.
        """
        # Core user interface loop
        while True:
            user_input = input(self._get_prompt())
            user_input = user_input.lower().strip()
            match user_input:
                case 'help':
                    atomic_print(
                        std_out_lock, 'Enter one of the following command numbers: \n1 - Create account \n2 - Login \n3 - List accounts \n4 - Send message \n5 - Logoff \n6 - Delete account')
                case '1' | 'create account':
                    self._login_or_create_account('CREATE_ACCOUNT')
                case '2' | 'login':
                    self._login_or_create_account('LOG_IN')
                case '3' | 'list accounts':
                    self._list_accounts()
                case '4' | 'send message':
                    self._send_message()
                case '5' | 'logoff' | 'exit':
                    self._logoff()
                case '6' | 'delete account':
                    self._delete_account()
                case _:
                    atomic_print(std_out_lock, 'Invalid command')
            sleep(0.2)

    def _login_or_create_account(self, action: Literal['LOG_IN', 'CREATE_ACCOUNT']):
        """
        Handles sending a login or create account request to the server

        Args:
        action (Literal): the requested action to carry out
        """
        username = input('Enter username: ')
        # Check valid username, only letters and numbers
        if username.strip().isalnum() and 5 <= len(username) <= 20:
            message = self.protocol.encode(
                action, self.message_counter, {'username': username})
            self.message_counter += 1
            self.client_library.send(message)
        else:
            atomic_print(
                std_out_lock, 'Invalid username. Username must be between 5 and 20 characters and only contain letters and numbers.')

    def _list_accounts(self):
        """
        Handles sending a list account request to the server
        """
        # Send list accounts query
        query = input('Enter query: ')
        logging.info('Start time', time.time())
        message = self.protocol.encode(
            'LIST_ACCOUNTS', self.message_counter, {'query': query})
        self.message_counter += 1
        self.client_library.send(message)

    def _send_message(self):
        """
        Handles sending a send message request to the server
        """
        # Get recipient username and message and send
        user = input('Enter recipient username: ')
        user_msg = input('Enter message: ')
        message = self.protocol.encode(
            'SEND_MESSAGE', self.message_counter, {'recipient': user, 'message': user_msg})
        self.message_counter += 1
        self.client_library.send(message)

    def _logoff(self):
        """
        Handles sending a log off request to the server
        """
        message = self.protocol.encode(
            'LOG_OFF', self.message_counter)
        self.message_counter += 1
        self.client_library.send(message)

    def _delete_account(self):
        """
        Handles sending a delete account request to the server
        """
        message = self.protocol.encode(
            'DELETE_ACCOUNT', self.message_counter)
        self.message_counter += 1
        self.client_library.send(message)

    def process_operation_curry(self, out_lock):
        """Processes the operation. This is a curried function to work with the
        read packets api provided in protocol. See the relevant process functions
        for functionality.

        Args:
            out_lock (threading.Lock): lock to control accesses to stdou
        """
        def process_operation(client_socket, metadata: protocol.Metadata, msg, id_accum):
            """Processes the operation. When the response is an error, we print the
            error message. When we are receiving the message, we print out the sender
            and the message.

            Args:
                client (socket.socket): The client socket; not used for this function
                metadata (protocol.Metadata): The metadata parsed from the message
                msg (str): message to parse for operation arguments
                id_accum (it): integer accumulator for message
            """
            operation_code = metadata.operation_code.value
            args = self.protocol.parse_data(operation_code, msg)
            atomic_print(out_lock, '')
            match operation_code:
                case 2:  # Create account response
                    if args['status'] == "Success":
                        self.username = args['username']
                        atomic_print(
                            out_lock, "Account creation successful. You are now logged in.")
                    else:
                        atomic_print(out_lock, args['status'])
                case 4:  # List accounts response
                    logging.info('End time', time.time())
                    if args['status'] == "Success":
                        accounts = args['accounts'].split(';')
                        accounts_str = '\n'.join(accounts)
                        atomic_print(
                            out_lock, f"Account search results:\n{accounts_str}")
                    else:
                        atomic_print(out_lock, args['status'])
                case 6:  # Send message response
                    if not args['status'] == "Success":
                        atomic_print(out_lock, args['status'])
                case 8:  # Delete Account response
                    if args['status'] == "Success":
                        self.username = None
                        atomic_print(
                            out_lock, "Deleting account successful; you are now logged out.")
                    else:
                        atomic_print(out_lock, args['status'])
                case 10:  # Login response
                    if args['status'] == "Success":
                        self.username = args['username']
                        atomic_print(out_lock, "You are now logged in.")
                    else:
                        atomic_print(out_lock, args['status'])
                case 12:  # Logoff response
                    if args['status'] == "Success":
                        self.username = None
                        atomic_print(out_lock, "You are now logged out.")
                    else:
                        atomic_print(out_lock, args['status'])
                case 13:  # Receive message
                    atomic_print(
                        out_lock, f"Message from {args['sender']}: {args['message']} \n\n{self._get_prompt()}")
        return process_operation


def atomic_print(lock, msg, end=None):
    """
    Atomically prints the msg and the optional end string

    Args:
        lock (threading.Lock): lock to lock stdout
        msg (str): message to print
        end (str): optional end string to print
    """
    lock.acquire()
    print(msg, end=end)
    lock.release()
