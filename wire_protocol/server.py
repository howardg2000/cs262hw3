import socket
from time import sleep
import time
import protocol
import threading
import re
import logging
from utils import account_list
from utils import logged_in_accounts
from utils import undelivered_messages


class Server:
    def __init__(self, host, port, protocol, server_id):
        self.host = host
        self.port = port
        self.other_server_sockets_accepted = [] # List of socket objects that we are listening to
        self.other_server_sockets_connected = {} # Map of server_id to (socket, socket_lock) for servers listening to us
        self.other_server_lock = threading.Lock()

        self.primary_id = -1 # The id of the primary server
        self.server_id = server_id

        self.msg_counter = 0    
        self.acknowledgement_lock = threading.Lock() # Lock for the recognition of acks from replicas

        self.clients = {} # map of (client socket, socket_lock) to uuid
        self.clients_lock = threading.Lock()

        self.account_list = account_list.AccountList(f"logs/account_list_{server_id}.log")  # Manages account list
        self.account_list_lock = threading.Lock()

        self.logged_in = logged_in_accounts.LoggedInAccounts(f"logs/logged_in_accounts_{server_id}.log")  # Manages usernames and uuids that are logged in
        self.logged_in_lock = threading.Lock()

        # Map of recipient username to list of (sender, message) for that recipient
        self.undelivered_msg = undelivered_messages.UndeliveredMessages(f"logs/undelivered_messages_{server_id}.log") # Manages undelivered messag
        self.undelivered_msg_lock = threading.Lock()
        
        self.message_delivery_thread = None
        self.heartbeat_thread = None

        self.protocol = protocol
        
        self.separator = '\r'

    def disconnect(self):
        self.socket.close()

    def handle_connection(self, client_socket, socket_lock):
        """Function to handle a connection on a single thread, which continuously reads the socket and processes the messages

        Args:
            client (socket.socket): The socket to read from.
            socket_lock (threading.Lock): Lock to prevent concurrent socket read
        """
        self.handle_client(client_socket, socket_lock)


    def handle_client(self, client, socket_lock):
        """Function to handle a client on a single thread, which continuously reads the socket and processes the messages

        Args:
            client (socket.socket): The socket to read from.
            socket_lock (threading.Lock): Lock to prevent concurrent socket read
        """
        value = self.protocol.read_packets(
            client, self.process_operation_curried(socket_lock))
        if value is None:
            client.close()
        self.clients_lock.acquire()
        self.logged_in_lock.acquire()
        uuid = self.clients[(client, socket_lock)]
        self.clients.pop((client, socket_lock))
        username = self.logged_in.get_username(uuid)
        if username is not None:
            self.logged_in.logoff(username)
        self.logged_in_lock.release()
        self.clients_lock.release()
        print("Closing client.")
    
    def handle_replica(self, client, socket_lock):
        """Function to listen for and handle messages from replica servers."""
        value = self.protocol.read_packets(
            client, self.process_operation_curried(socket_lock))
        if value is None:
            client.close()
        print("Closing replica.")
    

    def atomicIsLoggedIn(self, client_socket, socket_lock):
        """Atomically checks if the client is logged in 

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        ret = True
        self.clients_lock.acquire()
        self.logged_in_lock.acquire()
        uuid = self.clients[(client_socket, socket_lock)]
        if not self.logged_in.is_logged_in(uuid):
            ret = False
        self.logged_in_lock.release()
        self.clients_lock.release()
        return ret

    def atomicLogIn(self, client_socket, socket_lock, account_name):
        """Atomically logs client in with the account name

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
            account_name (str): The account name to log in
        """
        self.clients_lock.acquire()
        self.logged_in_lock.acquire()
        uuid = self.clients[(client_socket, socket_lock)]
        self.wait_for_update_login_ack("True", account_name, uuid)
        self.logged_in.login(account_name, uuid)
        self.logged_in_lock.release()
        self.clients_lock.release()

    def atomicIsAccountCreated(self, recipient):
        """Atomically checks if an account is created

        Args:
            recipient (str): The account name to check
        """
        ret = True
        self.account_list_lock.acquire()
        ret = self.account_list.contains(recipient)
        self.account_list_lock.release()
        return ret

    def process_create_account(self, args, client_socket, socket_lock):
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
            self.account_list_lock.acquire()
            if self.account_list.contains(account_name):
                self.account_list_lock.release()
                response = {
                    'status': 'Error: Account already exists.', 'username': account_name}
            else:
                # Communicate update to replicas
                self.wait_for_update_accounts_ack("True", account_name)
                
                self.account_list.create_account(account_name)
                self.atomicLogIn(client_socket, socket_lock,
                                 account_name)  # accountLock > login
                # if we release the lock earlier, someone else can create the same acccount and try to log in while we wait for the log in lock
                self.account_list_lock.release()
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
            pattern = re.compile(
                fr"{args['query']}", flags=re.IGNORECASE)
            self.account_list_lock.acquire()
            result = self.account_list.search_accounts(pattern)
            self.account_list_lock.release()
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
        self.clients_lock.acquire()
        self.logged_in_lock.acquire()
        uuid = self.clients[(client_socket, socket_lock)]
        if not self.logged_in.is_logged_in(uuid):
            self.logged_in_lock.release()
            self.clients_lock.release()
            response = {
                'status': 'Error: Need to be logged in to send a message.'}
        else:
            username = self.logged_in.get_username(uuid)
            self.logged_in_lock.release()
            self.clients_lock.release()
            recipient = args["recipient"]
            message = args["message"]
            print("sending message", recipient, message)
            self.account_list_lock.acquire()
            if not self.account_list.contains(recipient):
                self.account_list_lock.release()
                response = {
                    'status': 'Error: The recipient of the message does not exist.'}
            else:
                self.undelivered_msg_lock.acquire()
                # Notify replicas of update
                self.wait_for_update_message_ack("True", recipient, username, message)
                
                self.undelivered_msg.add_message(recipient, username, message)
                self.undelivered_msg_lock.release()
                self.account_list_lock.release()
                response = {'status': 'Success'}
        return response

    def process_delete_account(self, client_socket, socket_lock):
        """Processes a delete account request. We require that the requester is 
        logged in.

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        self.clients_lock.acquire()
        self.logged_in_lock.acquire()
        uuid = self.clients[(client_socket, socket_lock)]
        if self.logged_in.is_logged_in(uuid):
            username = self.logged_in.get_username(uuid)
            # Notify replicas of update
            self.wait_for_update_login_ack("False", username, uuid)
            self.logged_in.logoff(username)
            self.logged_in_lock.release()
            self.clients_lock.release()
            self.account_list_lock.acquire()
            self.wait_for_update_accounts_ack("False", username)
            self.account_list.remove(username)
            self.account_list_lock.release()
            response = {'status': 'Success'}
        else:
            self.logged_in_lock.release()
            self.clients_lock.release()
            response = {
                'status': 'Error: Need to be logged in to delete your account.'}
        return response

    def process_login(self, args, client_socket, socket_lock):
        """Processes a login request. We require that the requester is 
        not logged in, the account exists, and no one else is logged into the account.

        Args:
            args (dict): The args object for sending a message
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        self.clients_lock.acquire()
        self.logged_in_lock.acquire()
        uuid = self.clients[(client_socket, socket_lock)]
        if self.logged_in.is_logged_in(uuid):
            self.logged_in_lock.release()
            self.clients_lock.release()
            response = {
                'status': 'Error: Already logged into an account, please log off first.', 'username': ''}
        else:
            account_name = args['username']
            if (not self.atomicIsAccountCreated(account_name)):
                self.logged_in_lock.release()
                self.clients_lock.release()
                response = {
                    'status': 'Error: Account does not exist.', 'username': account_name}
            elif self.logged_in.username_is_logged_in(account_name):
                self.logged_in_lock.release()
                self.clients_lock.release()
                response = {
                    'status': 'Error: Someone else is logged into that account.', 'username': account_name}
            else:
                # Notify replicas of update
                self.wait_for_update_login_ack("True", account_name, uuid)
                
                self.logged_in.login(account_name, uuid)
                self.logged_in_lock.release()
                self.clients_lock.release()
                response = {'status': 'Success', 'username': account_name}
        return response

    def process_logoff(self, client_socket, socket_lock):
        """Processes a logoff request. We require that the requester is 
        logged in.

        Args:
            client (socket.socket): The client socket
            socket_lock (threading.Lock): The socket's associated lock
        """
        self.clients_lock.acquire()
        self.logged_in_lock.acquire()
        uuid = self.clients[(client_socket, socket_lock)]
        if self.logged_in.is_logged_in(uuid):
            username = self.logged_in.get_username(uuid)
            # Notify replicas of update
            self.wait_for_update_login_ack("False", username, uuid)
            
            self.logged_in.logoff(username)
            self.logged_in_lock.release()
            self.clients_lock.release()
            response = {'status': 'Success'}
        else:
            self.logged_in_lock.release()
            self.clients_lock.release()
            response = {
                'status': 'Error: Need to be logged in to log out of your account.'}
        return response

    def process_new_client(self, args, client_socket, socket_lock):
        """Processes a new client request for replication."""
        uuid = args['uuid']
        self.clients_lock.acquire()
        self.clients[(client_socket, socket_lock)] = uuid
        self.clients_lock.release()
        return None
    
    def process_update_accounts(self, args):
        """Processes an update to the account list for replication
        
        Args:
            args (dict): The args object for sending a message. Should contain 'add_flag' and 'username'.
                'add_flag' should be a string representation of a boolean, 'True' means we are adding an account,
                and 'False' means we are removing an account. 'username' should be the username of the account.
        """
        add = args['add_flag']
        username = args['username']
        self.account_list_lock.acquire()
        if (add == 'True'):
            self.account_list.create_account(username)
        else :
            self.account_list.remove(username)
        self.account_list_lock.release()

    def process_update_login(self, args):
        """Processes an update to the logged in list for replication.
        
        Args:
            args (dict): The args object for sending a message. Should contain 'add_flag', 'username', and 'uuid'.
                'add_flag' should be a string representation of a boolean, 'True' means we are adding an entry to the logged in list,
                and 'False' means we are removing an entry from the logged in list. 
        """
        add = args['add_flag']
        username = args['username']
        uuid = args['uuid']
        self.logged_in_lock.acquire()
        if (add == 'True'):
            self.logged_in.login(username, uuid)
        else:
            self.logged_in.logoff(username)
        self.logged_in_lock.release()
    
    def process_update_message_state(self, args):
        """Processes an update to undelivered messages for replication.
        
        Args:
            args (dict): The args object for sending a message. Should contain 'add_one', 'recipient', 'sender', and 'message'.
                'add_one' should be a string representation of a boolean, 
                'True' means we are adding one message to the receipient's list of undelivered messages,
                and 'False' means we are replacing the receipient's list of undelivered messages.
                'recipient' should be the username of the recipient. 
                'sender' should be the username of the sender or a concatenation of the usernames of the senders separated by '\r'.
                'message' should be the message or a concatenation of the messages separated by '\r'.
        """
        add = args['add_one']
        recipient = args['recipient']
        sender = args['sender']
        message = args['message']
        self.undelivered_msg_lock.acquire()
        if (add == "True"): # Append one message for a recipient
            self.undelivered_msg.add_message(recipient, sender, message)
        else: # In this case we are trying to replace the list of messages for a recipient
            sender_list = sender.split(self.separator)
            message_list = message.split(self.separator)
            tupleList = list(zip(sender_list, message_list))
            self.undelivered_msg.update_messages(recipient, tupleList)
        self.undelivered_msg_lock.release()
        
    def wait_for_update_accounts_ack(self, add_flag: str, username: str):
        """Sends message to replicas notifying of an update to accounts,
        and waits for acknowledgement from all replicas that they have updated their account lists.
        
        args:
            add_flag (str): A string representation of a boolean, 'True' means we are adding an account,
                and 'False' means we are removing an account. 
            username (str): The username of the account.
        """
        print(f"waiting for ack lock for accounts {self.server_id} ")
        print(self.primary_id)
        self.acknowledgement_lock.acquire()
        print("acquired ack lock for accounts")
        print("waiting for other lock for accounts")
        self.other_server_lock.acquire()
        print("acquired other lock for accounts")
        for (replica, socket_lock) in self.other_server_sockets_connected.values():
            response = self.protocol.encode('UPDATE_ACCOUNT_STATE', self.msg_counter, {'add_flag': add_flag, 'username': username})
            self.protocol.send(replica, response, socket_lock)
            self.msg_counter = self.msg_counter + 1
            ack = self.protocol.read_small_packets(replica)
            if ack is None:
                #TODO say replica died
                self.replica_died(replica)
        self.other_server_lock.release()
        self.acknowledgement_lock.release()
    
    def wait_for_update_login_ack(self, add_flag: str, username: str, uuid: str):
        """Sends message to replicas notifying of an update to logged in accounts,
        and waits for acknowledgement from all replicas that they have updated their logged in lists.
        
        args:
            add_flag (str): A string representation of a boolean, 'True' means we are adding a logged in account,
                and 'False' means we are removing a logged in account. 
            username (str): The username of the account.
            uuid (str): The uuid of the account.
        """
        print(f"waiting for ack lock for login {self.server_id} ")
        print(self.primary_id)
        self.acknowledgement_lock.acquire()
        print("acquired ack lock for login")
        print("waiting for other lock for login")
        self.other_server_lock.acquire()
        print("acquired other lock for login")
        for (replica, socket_lock) in self.other_server_sockets_connected.values():
            response = self.protocol.encode('UPDATE_LOGIN_STATE', self.msg_counter, {'add_flag': add_flag, 'username': username, 'uuid': uuid})
            self.protocol.send(replica, response, socket_lock)
            self.msg_counter = self.msg_counter + 1
            ack = self.protocol.read_small_packets(replica)
            if ack is None:
                #TODO say replica died
                self.replica_died(replica)
        self.other_server_lock.release()
        self.acknowledgement_lock.release()

    def wait_for_update_message_ack(self, add_flag: str, recipient: str, sender: str, message: str):
        """Sends message to replicas notifying of an update to undelivered messages,
        and waits for acknowledgement from all replicas that they have updated their undelivered messages.
        
        args:
            add_flag (str): A string representation of a boolean, 'True' means we are adding one undelivered message,
                and 'False' means we are replacing all of a recipient's undelivered messages. 
            recipient (str): The recipient of the message.
            sender (str): The sender of the message or a concatenation of the usernames of the senders separated by '\r'..
            message (str): The message or a concatenation of the messages separated by '\r'.
        """
        print(f"waiting for ack lock for messages {self.server_id} ")
        print(self.primary_id)
        self.acknowledgement_lock.acquire()
        print("acquired ack lock for for msg")
        print("waiting for other lock for msg ")
        self.other_server_lock.acquire()
        print("acquired other lock for msg")
        for (replica, socket_lock) in self.other_server_sockets_connected.values():
            response = self.protocol.encode('UPDATE_MESSAGE_STATE', self.msg_counter, {'add_one': add_flag, 'recipient': recipient, 'sender': sender, 'message': message})
            self.protocol.send(replica, response, socket_lock)
            self.msg_counter = self.msg_counter + 1
            ack = self.protocol.read_small_packets(replica)
            if ack is None:
                #TODO say replica died
                self.replica_died(replica)
        self.other_server_lock.release()
        self.acknowledgement_lock.release()

    def replica_died(self, replica_socket): 
        #TODO implement
        return None        

    def process_operation_curried(self, socket_lock):
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
            print(operation_code)
            match operation_code:
                case 1:  # CREATE_ACCOUNT
                    response = self.protocol.encode(
                        'CREATE_ACCOUNT_RESPONSE', id_accum, self.process_create_account(args, client_socket, socket_lock))
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
                        'LOG_IN_RESPONSE', id_accum, self.process_login(args, client_socket, socket_lock))
                case 11:  # LOGOFF
                    response = self.protocol.encode(
                        'LOG_OFF_RESPONSE', id_accum, self.process_logoff(client_socket, socket_lock))
                case 15: 
                    response = self.protocol.encode('GET_PRIMARY_RESPONSE', id_accum, {'id': self.primary_id})
                case 16: 
                    response = self.protocol.encode('ASSIGN_PRIMARY_RESPONSE', id_accum, {'id': self.server_id})
                case 18: # UPDATE_ACCOUNT_STATE
                    self.process_update_accounts(args)
                    response = self.protocol.encode('ACK', id_accum)
                case 19: # UPDATE_LOGIN_STATE
                    self.process_update_login(args)
                    response = self.protocol.encode('ACK', id_accum)
                case 20: # UPDATE_MESSAGE_STATE
                    self.process_update_message_state(args)
                    response = self.protocol.encode('ACK', id_accum)
                case 21: # NEW_CLIENT
                    response = self.process_new_client(args, client_socket, socket_lock)
                case 23: # HEARTBEAT
                    response = self.protocol.encode('ACK', id_accum)
                case _: 
                    response = None
            if not response is None:
                self.protocol.send(client_socket, response, socket_lock)
        return process_operation

    def handle_undelivered_messages(self):
        """Sends any undelivered messages to the recipients. If the recipient is not logged in
        or sending fails, the undelivered message remains on the work queue. 
        """
        self.undelivered_msg_lock.acquire()
        for recipient, message_infos in self.undelivered_msg.get_messages():
            self.clients_lock.acquire()
            self.logged_in_lock.acquire()
            if self.logged_in.username_is_logged_in(recipient):
                uuid = self.logged_in.get_uuid_from_username(recipient)
                (client_socket, socket_lock) = [k for k, v in self.clients.items() if v == uuid][0]
                undelivered_messages = []
                for (sender, msg) in message_infos:
                    response = self.protocol.encode(
                        "RECV_MESSAGE", self.msg_counter, {"sender": sender, "message": msg})
                    status = self.protocol.send(
                        client_socket, response, socket_lock)
                    if not status:
                        undelivered_messages.append((sender, msg))
                    self.msg_counter = self.msg_counter + 1
                    
                # Notify replicas of update to undelivered messages
                senders_string = self.separator.join([msg_info[0] for msg_info in undelivered_messages])
                msgs_string = self.separator.join([msg_info[1] for msg_info in undelivered_messages])
                self.wait_for_update_message_ack("False", recipient, senders_string, msgs_string)
                self.undelivered_msg.update_messages(recipient, undelivered_messages)
            self.logged_in_lock.release()
            self.clients_lock.release()
        self.undelivered_msg_lock.release()

    def send_messages(self):
        """ Handles undelivered messages in a loop, and sleeps to provide better 
        responsiveness on the client side
        """
        while True:
            self.handle_undelivered_messages()
            sleep(0.01)
    
    def connect_to_replicas(self, server_socket, num_replicas): 
        i = 0
        while i < num_replicas:
            try:
                clientsocket, addr = server_socket.accept()
                print('Connection created with:', addr)
                clientsocket.setblocking(1)
                self.other_server_sockets_accepted.append(clientsocket)
                lock = threading.Lock()
                thread = threading.Thread(
                    target=self.handle_replica, args=(clientsocket, lock, ), daemon=True)
                thread.start()
                i += 1
            except BlockingIOError:
                pass
            
    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket = server_socket
        server_socket.setblocking(0)
        server_socket.bind((self.host, self.port))
        print("Server started.")
        server_socket.listen()
        num_replicas = int(input('Enter the number of replicas'))
        thread = threading.Thread(target=self.connect_to_replicas, args = (server_socket, num_replicas, ), daemon=True)
        thread.start()
        self.other_server_lock.acquire()
        for i in range(1, num_replicas+1):
            #host = input(f'Enter host for replica {i}: ')
            host = self.host
            port = int(input(f'Enter port for replica {i}: '))
            id = int(input(f'Enter id for replica {i}: '))
            replica_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            replica_socket.connect((host, port))
            self.other_server_sockets_connected[id] = (replica_socket, threading.Lock())
            print(f"Connected to {host}, {port}")
        print(str(self.other_server_sockets_connected))
        self.other_server_lock.release()
        time.sleep(10)
        
        # Determine primary and either start message delivery thread or heartbeat thread depending on if primary or not
        self.determine_primary_server()
        if (self.primary_id == self.server_id):
            self.become_primary()
        else:
            self.heartbeat_thread = threading.Thread(target=self.check_heartbeat, daemon=True)
            self.heartbeat_thread.start()
            
        while(True):
            try:
                clientsocket, addr = server_socket.accept()
                clientsocket.setblocking(1)
                lock = threading.Lock()
                thread = threading.Thread(
                    target=self.handle_connection, args=(clientsocket, lock, ), daemon=True)
                thread.start()
                print('Connection created with:', addr)
            except BlockingIOError:
                pass

    def determine_primary_server(self):
        # Send id to all servers and the one with the lowest id is primary
        # Check to make sure this doesn't deadlock
        alive_server_ids = [self.server_id]
        self.other_server_lock.acquire()
        for (server_socket, socket_lock) in self.other_server_sockets_connected.values():
            print("Assigning primary")
            value =self.protocol.send(server_socket, self.protocol.encode("ASSIGN_PRIMARY", self.msg_counter), socket_lock)
            self.msg_counter += 1
            ack = self.protocol.read_small_packets(server_socket)
            if ack is not None:
                (md, msg) = ack
                alive_server_ids.append(int(self.protocol.parse_data(md.operation_code, msg)['id']))
        self.other_server_lock.release()
        
        self.primary_id = min(alive_server_ids)
        print(f"primary is {self.primary_id}")
        print(str(alive_server_ids))

    
    def check_heartbeat(self):
        while True:
            self.other_server_lock.acquire()
            primary_socket, socket_lock = self.other_server_sockets_connected[self.primary_id]
            self.other_server_lock.release()
            response = self.protocol.encode("HEARTBEAT", self.msg_counter, {"id": str(self.server_id)})
            self.protocol.send(primary_socket, response, socket_lock)
            self.msg_counter += 1
            ack = self.protocol.read_small_packets(primary_socket)
            if ack is None:
                # TODO: Primary is dead, need to choose new primary. I think this is done, can remove from sockets_accepted too?
                #self.other_server_sockets_connected.pop(self.primary_id)
                self.determine_primary_server()
                if self.primary_id == self.server_id:
                    self.clients_lock.acquire()
                    for client in self.clients.keys():
                        self.protocol.send(client[0], self.protocol.encode("SWITCH_PRIMARY", self.msg_counter, {"id": self.primary_id}), client[1])
                    self.become_primary()
                    break
            
            sleep(0.5)
            
    def become_primary(self):
        # Start message delivery thread
        self.message_delivery_thread = threading.Thread(
            target=self.send_messages, daemon=True)
        self.message_delivery_thread.start()
