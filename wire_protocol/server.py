import socket
from time import sleep
import time
import protocol
import threading
import re
import logging


class LoggedInAccounts:
    def __init__(self, filename):
        self.filename = filename
        self.logged_in = {}  # Map of username to (client_socket, socket lock)
        self.lock = threading.Lock()

    def atomic_login(self, username, client_socket, addr, socket_lock):
        self.lock.acquire()
        self.logged_in[username] = (client_socket, socket_lock)
        with open(self.filename, "a") as f:
            # File only contain the address of the client because this is all we need to reconnec to client.
            # The primary server should populate the logged_in dict with the socket object and lock
            # while keeping the file consistent with the dict. Replicas should only keep the file consistent
            # and populate the dict if they become the primary server.
            # Each addr corresponds to a unique client_socket object
            f.write(f"{username} {addr[0]} {addr[1]}")
        self.lock.release()

    def atomic_is_logged_in(self, client_socket, socket_lock):
        self.lock.acquire()
        is_logged_in = (client_socket, socket_lock) in self.logged_in.values()
        self.lock.release()
        return is_logged_in

    def username_is_logged_in(self, username):
        self.lock.acquire()
        is_logged_in = username in self.logged_in.keys()
        self.lock.release()
        return is_logged_in

    def atomic_logoff(self, client_socket, socket_lock):
        self.lock.acquire()
        if (client_socket, socket_lock) in self.logged_in.values():
            username = [k for k, v in self.logged_in.items() if v == (
                client_socket, socket_lock)][0]
            self.logged_in.pop(username)

            # Remove the username entry from the file
            with open(self.filename, 'r') as f:
                lines = f.readlines()
            with open(self.filename, 'w') as f:
                for line in lines:
                    if line.strip().split()[0] != username:
                        f.write(line)

            self.logged_in_lock.release()
            return username
        self.logged_in_lock.release()
        return False

    def get_username(self, client_socket, socket_lock):
        self.lock.acquire()
        username = [k for k, v in self.logged_in.items() if v == (
            client_socket, socket_lock)][0]
        self.lock.release()
        return username


class AccountList:
    def __init__(self, filename, logged_in_accounts: LoggedInAccounts):
        self.filename = filename
        self.lock = threading.Lock()
        self.logged_in_accounts = logged_in_accounts

    def atomic_create_account(self, username, client_socket, addr, socket_lock):
        self.lock.acquire()
        with open(self.filename, 'a') as f:
            f.write(username)
        self.logged_in_accounts.atomic_login(
            username, client_socket, addr, socket_lock)  # accountLock > login
        # if we release the lock earlier, someone else can create the same acccount and try to log in while we wait for the log in lock
        self.lock.release()

    def atomic_remove(self, username):
        self.lock.acquire()
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        with open(self.filename, 'w') as f:
            for line in lines:
                if line.strip() != username:
                    f.write(line)
        self.lock.release()

    def atomic_contains(self, username):
        self.lock.acquire()
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        for line in lines:
            if line.strip() == username:
                return True
        self.lock.release()
        return False

    def search_accounts(self, query):
        pattern = re.compile(
            fr"{query}", flags=re.IGNORECASE)
        self.lock.acquire()
        result = []
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        for line in lines:
            account = line.strip()
            if pattern.match(account):
                result.append(account)
        self.lock.release()
        return result


class UndeliveredMessages:
    def __init__(self, filename):
        self.filename = filename
        self.lock = threading.Lock()

    def add_message(self, recipient, sender, message):
        self.lock.acquire()
        with open(self.filename, 'a') as f:
            f.write(f"{recipient} {sender} {message}")
        self.lock.release()

    def get_messages(self, recipient):
        # Get all outsanding messages for a recipient. Read operation.
        self.lock.acquire()
        messages = []
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        for line in lines:
            msg_recipient, sender, message = line.strip().split(' ', 2)
            if msg_recipient == recipient:
                messages.append(message)
        self.lock.release()
        return messages

    def remove_message(self, recipient, sender, message):
        # Remove message from file once it has been delivered. Update operation.
        self.lock.acquire()
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        with open(self.filename, 'w') as f:
            for line in lines:
                if line.strip() != f'{recipient} {sender} {message}':
                    f.write(line)
        self.lock.release()


class Server:
    def __init__(self, host, port, protocol, other_servers, server_id):
        self.host = host
        self.port = port
        self.other_servers = other_servers
        self.server_id = server_id

        self.msg_counter = 0

        self.logged_in_file = "logs/logged_in.log"
        self.logged_in = LoggedInAccounts(self.logged_in_file)

        self.account_list_file = "logs/account_list.log"
        self.account_list = AccountList(self.account_list_file, self.logged_in)

        # Map of recipient username to list of (sender, message) for that recipient
        self.undelivered_msgs_file = "logs/undelivered_msgs.log"
        self.undelivered_msgs = UndeliveredMessages(self.undelivered_msgs_file)

        self.protocol = protocol

    def disconnect(self):
        self.socket.close()

    def handle_connection(self, client_socket, addr, socket_lock):
        """Function to handle a client on a single thread, which continuously reads the socket and processes the messages

        Args:
            client (socket.socket): The socket to read from.
            socket_lock (threading.Lock): Lock to prevent concurrent socket read
        """
        if self.is_primary:
            self.handle_client(client_socket, addr, socket_lock)
        else:
            self.handle_primary(client_socket, addr, socket_lock)

    def handle_client(self, client, addr, socket_lock):
        """Function to handle a client on a single thread, which continuously reads the socket and processes the messages

        Args:
            client (socket.socket): The socket to read from.
            socket_lock (threading.Lock): Lock to prevent concurrent socket read
        """
        value = self.protocol.read_packets(
            client, self.process_operation_curried(socket_lock, addr))
        if value is None:
            client.close()
        self.logged_in_lock.acquire()
        username = [k for k, v in self.logged_in.items() if v == (
            client, socket_lock)]
        if len(username) > 0:
            self.logged_in.pop(username[0])
        self.logged_in_lock.release()
        print("Closing client.")

    def handle_primary(self, client, addr, socket_lock):
        """Function for replica server to handle primary requests.

        Args:
            client (socket.socket): The socket to read from.
            socket_lock (threading.Lock): Lock to prevent concurrent socket read
        """
        # TODO: update process_operation_curried to handle the update messages from the primary
        raise NotImplementedError
        value = self.protocol.read_packets(
            client, self.process_operation_curried(socket_lock, addr))
        if value is None:
            client.close()
        self.logged_in_lock.acquire()
        username = [k for k, v in self.logged_in.items() if v == (
            client, socket_lock)]
        if len(username) > 0:
            self.logged_in.pop(username[0])
        self.logged_in_lock.release()
        print("Closing client.")

    def atomicIsLoggedIn(self, client_socket, socket_lock):
        """Atomically checks if the client is logged in

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        return self.logged_in.atomic_is_logged_in(client_socket, socket_lock)

    def atomicLogIn(self, client_socket, addr, socket_lock, account_name):
        """Atomically logs client in with the account name

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
            account_name (str): The account name to log in
        """
        self.logged_in.atomic_login(
            account_name, client_socket, addr, socket_lock)

    def atomicIsAccountCreated(self, recipient):
        """Atomically checks if an account is created

        Args:
            recipient (str): The account name to check
        """
        return self.account_list.atomic_contains(recipient)

    def process_create_account(self, args, client_socket, addr, socket_lock):
        """Processes a create account request. We require that the requester is not
        logged in and that the account doesn't exist

        Args:
            args (dict): The args object for creating an account parsed from the received message
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        account_name = args["username"]
        if self.atomicIsLoggedIn(client_socket, socket_lock):
            response = {
                'status': 'Error: User can\'t create an account while logged in.', 'username': account_name}
        else:
            if self.atomicIsAccountCreated(account_name):
                response = {
                    'status': 'Error: Account already exists.', 'username': account_name}
            else:
                self.account_list.atomic_create_account(
                    account_name, client_socket, addr, socket_lock)
                print("Account created: " + account_name)
                response = {'status': 'Success', 'username': account_name}
        return response

    def process_list_accounts(self, args):
        """Processes a list account request. We don't require the requester to be logged in.

        Args:
            account_name (str): The args object for creating an account parsed from the received message
        """
        logging.info('Received', time.time())
        try:
            result = self.account_list.search_accounts(args["query"])
            response = {'status': 'Success', 'accounts': ";".join(result)}
        except:
            response = {'status': 'Error: regex is malformed.', 'accounts': ''}
        finally:
            return response

    def process_send_msg(self, args, client_socket, socket_lock):
        """Processes a send message request. We require that the requester is
        logged in and the recipient exists.

        Args:
            args (dict): The args object for sending a message
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        if not self.logged_in.atomic_is_logged_in(client_socket, socket_lock):
            response = {
                'status': 'Error: Need to be logged in to send a message.'}
        else:
            username = self.logged_in.get_username(client_socket, socket_lock)
            recipient = args["recipient"]
            message = args["message"]
            print("sending message", recipient, message)
            if not self.account_list.atomic_contains(recipient):
                response = {
                    'status': 'Error: The recipient of the message does not exist.'}
            else:
                self.undelivered_msgs.add_message(recipient, username, message)
                response = {'status': 'Success'}
        return response

    def process_delete_account(self, client_socket, socket_lock):
        """Processes a delete account request. We require that the requester is
        logged in.

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        username = self.logged_in.atomic_logoff(client_socket, socket_lock)
        if not username:
            response = {
                'status': 'Error: Need to be logged in to delete your account.'}
        else:
            self.account_list.atomic_remove(username)
            response = {'status': 'Success'}

        return response

    def process_login(self, args, client_socket, addr, socket_lock):
        """Processes a login request. We require that the requester is
        not logged in, the account exists, and no one else is logged into the account.

        Args:
            args (dict): The args object for sending a message
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        # TODO: This seems to raise some race conditions because I got rid of the locks and moved them
        # into the account list and logged in classes. To fix, we can just move those locks back out
        # into this server class like before, and use the locks to protect any operations on the
        # account and logged in classes.
        if self.atomicIsLoggedIn(client_socket, socket_lock):
            response = {
                'status': 'Error: Already logged into an account, please log off first.', 'username': ''}
        else:
            account_name = args['username']
            if not self.atomicIsAccountCreated(account_name):
                response = {
                    'status': 'Error: Account does not exist.', 'username': account_name}
            elif self.logged_in.username_is_logged_in(account_name):
                response = {
                    'status': 'Error: Someone else is logged into that account.', 'username': account_name}
            else:
                self.atomicLogIn(client_socket, account_name,
                                 addr, socket_lock)
                response = {'status': 'Success', 'username': account_name}
        return response

    def process_logoff(self, client_socket, socket_lock):
        """Processes a logoff request. We require that the requester is
        logged in.

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        if self.logged_in.atomic_logoff(client_socket, socket_lock):
            response = {'status': 'Success'}
        else:
            response = {
                'status': 'Error: Need to be logged in to log out of your account.'}
        return response

    def process_operation_curried(self, socket_lock, addr):
        """Processes the operation. This is a curried function to work with the 
        read packets api provided in protocol. See the relevant process functions
        for functionality.

        Args:
            socket_lock (threading.Lock): The socket's associated lock
        """
        def process_operation(client_socket, metadata: protocol.Metadata, msg, id_accum):
            """Processes the operation. See the relevant process functions
            for functionality.

            Args:
                client (socket.socket): The client socket
                metadata (protocol.Metadata): The metadata parsed from the message
                msg (str): message to parse for operation arguments
                id_accum (it): integer accumulator for message 
            """
            operation_code = metadata.operation_code.value
            args = self.protocol.parse_data(operation_code, msg)
            match operation_code:
                case 1:  # CREATE_ACCOUNT
                    response = self.protocol.encode(
                        'CREATE_ACCOUNT_RESPONSE', id_accum, self.process_create_account(args, client_socket, addr, socket_lock))
                case 3:  # LIST ACCOUNTS
                    response = self.protocol.encode(
                        'LIST_ACCOUNTS_RESPONSE', id_accum, self.process_list_accounts(args))
                case 5:  # SENDMSG
                    # in this case we want to add to undelivered messages, which the server iterator will figure out i think
                    # here we check the person sending is logged in and the recipient account has been created
                    response = self.protocol.encode(
                        'SEND_MESSAGE_RESPONSE', id_accum, self.process_send_msg(args, client_socket, socket_lock))
                case 7:  # DELETE
                    response = self.protocol.encode(
                        'DELETE_ACCOUNT_RESPONSE', id_accum, self.process_delete_account(client_socket, socket_lock))
                case 9:  # LOGIN
                    response = self.protocol.encode(
                        'LOG_IN_RESPONSE', id_accum, self.process_login(args, client_socket, addr, socket_lock))
                case 11:  # LOGOFF
                    response = self.protocol.encode(
                        'LOG_OFF_RESPONSE', id_accum, self.process_logoff(client_socket, socket_lock))
            if not response is None:
                self.protocol.send(client_socket, response, socket_lock)
        return process_operation

    def handle_undelivered_messages(self):
        """Sends any undelivered messages to the recipients. If the recipient is not logged in
        or sending fails, the undelivered message remains on the work queue. 
        """
        # TODO: I haven't touched this yet, need to update to use the new helper classes
        self.undelivered_msg_lock.acquire()
        for recipient, message_infos in self.undelivered_msg.items():
            self.logged_in_lock.acquire()
            if recipient in self.logged_in:
                client_socket, socket_lock = self.logged_in[recipient]
                undelivered_messages = []
                for (sender, msg) in message_infos:
                    response = self.protocol.encode(
                        "RECV_MESSAGE", self.msg_counter, {"sender": sender, "message": msg})
                    status = self.protocol.send(
                        client_socket, response, socket_lock)
                    if not status:
                        undelivered_messages.append((sender, msg))
                    self.msg_counter = self.msg_counter + 1
                self.undelivered_msg[recipient] = undelivered_messages
            self.logged_in_lock.release()
        self.undelivered_msg_lock.release()

    def send_messages(self):
        """ Handles undelivered messages in a loop, and sleeps to provide better 
        responsiveness on the client side
        """
        while True:
            self.handle_undelivered_messages()
            sleep(0.01)

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket = server_socket
        server_socket.setblocking(0)
        server_socket.bind((self.host, self.port))
        print("Server started.")
        server_socket.listen()

        # Need to determine the order in which this happens, because it should connect to all other servers before getting any client connections
        self._connect_to_other_servers()

        if self.is_primary:
            message_delivery_thread = threading.Thread(
                target=self.send_messages, daemon=True)
            message_delivery_thread.start()
        while(True):
            try:
                clientsocket, addr = server_socket.accept()
                clientsocket.setblocking(1)
                lock = threading.Lock()
                thread = threading.Thread(
                    target=self.handle_connection, args=(clientsocket, addr, lock, ), daemon=True)
                thread.start()
                print('Connection created with:', addr)
            except BlockingIOError:
                pass
            finally:
                self.handle_undelivered_messages()

    def _connect_to_other_servers(self):
        """Connects to the primary server and other servers in the system.
        """
        other_server_sockets = []
        for host, port in self.other_servers:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, int(port)))
            other_server_sockets.append(s)
            print("Server connection success to port val:" +
                  str(port) + "\n")
        self.other_server_sockets = other_server_sockets

        # Need code for determining which is primary server, simple scheme is send id to all servers
        # and the one with the lowest id is primary. This can also be used if the primary goes down,
        # so all servers know who the new primary is.
        self.determine_primary_server()

    def determine_primary_server(self):
        # Send id to all servers and the one with the lowest id is primary
        # Check to make sure this doesn't deadlock
        for server_socket in self.other_server_sockets:
            self.protocol.send(server_socket, self.protocol.encode(
                "INIT_ID_REQUEST", self.msg_counter, {"id": self.id}))

        self.is_primary = self.id < min(self.other_server_ids)
