
import unittest
import threading
from server import Server
from protocol import protocol_instance
from unittest.mock import MagicMock

TEST_HOST = "127.0.0.1"
TEST_PROTOCOL = protocol_instance
TEST_CONFIG = [{"host": TEST_HOST, "port": 6000, "id": 1}]
KEVIN_UUID = str(1)
HOWIE_UUID = str(2)
JOSEPH_UUID = str(3)


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server = Server(TEST_CONFIG, 1, TEST_PROTOCOL)
        self.server.account_list.create_account("kevin")
        self.server.account_list.create_account("howie")
        self.mock_kevin_socket = MagicMock()
        self.mock_howie_socket = threading.Lock()
        self.mock_kevin_lock = MagicMock()
        self.mock_howie_lock = threading.Lock()
        self.server.process_new_client({'uuid': str(KEVIN_UUID)}, self.mock_kevin_socket, self.mock_kevin_lock )
        self.server.process_new_client({'uuid': str(HOWIE_UUID)}, self.mock_howie_socket, self.mock_howie_lock )
        self.server.logged_in.login("kevin",KEVIN_UUID)
        self.server.logged_in.login("howie", HOWIE_UUID)
        self.msgId = 0
    
    def tearDown(self):
        self.server.account_list.clear()
        self.server.undelivered_msg.clear()

    def test_create_account_success(self):
        args = {"username": "joseph"}
        joseph_socket = MagicMock()
        joseph_lock = threading.Lock()
        self.server.process_new_client({'uuid': str(3)}, joseph_socket, joseph_lock)
        response = self.server.process_create_account(
            args, joseph_socket, joseph_lock)
        self.assertEqual(response['status'], 'Success')
        self.assertTrue(("joseph" in self.server.account_list.account_list))
        self.assertTrue(("joseph" in self.server.logged_in.logged_in.keys()))

    def test_create_account_fail_exists(self):
        args = {"username": "kevin"}
        joseph_socket = MagicMock()
        joseph_lock = threading.Lock()
        self.server.process_new_client({'uuid': str(3)}, joseph_socket, joseph_lock)
        response = self.server.process_create_account(
            args, joseph_socket, joseph_lock)
        self.assertEqual(response['status'], 'Error: Account already exists.')

    def test_create_account_fail_logged_in(self):
        args = {"username": "joseph"}
        uuid = self.server.logged_in.logged_in["kevin"]
        (client_socket, socket_lock) = [
                    k for k, v in self.server.clients.items() if v == uuid][0]
        response = self.server.process_create_account(
            args, client_socket, socket_lock)
        self.assertEqual(
            response['status'], 'Error: User can\'t create an account while logged in.')

    def test_login_success(self):
        args = {"username": "kevin"}
        uuid = self.server.logged_in.logged_in["kevin"]
        (client_socket, socket_lock) = [k for k, v in self.server.clients.items() if v == uuid][0]
        self.server.logged_in.logoff("kevin")
        response = self.server.process_login(
            args, client_socket, socket_lock)
        self.assertEqual(response['status'], 'Success')
        self.assertTrue("kevin" in self.server.logged_in.logged_in.keys())

    def test_login_fail_doesnt_exist(self):
        args = {"username": "joseph"}
        joseph_socket = MagicMock()
        joseph_lock = threading.Lock()
        self.server.process_new_client({'uuid': str(3)}, joseph_socket, joseph_lock)
        response = self.server.process_login(
            args, joseph_socket, joseph_lock)
        self.assertEqual(response['status'], 'Error: Account does not exist.')

    def test_login_fail_someone_logged_in(self):
        args = {"username": "kevin"}      
        joseph_socket = MagicMock()
        joseph_lock = threading.Lock()
        self.server.process_new_client({'uuid': str(3)}, joseph_socket, joseph_lock)
        response = self.server.process_login(
            args, joseph_socket, joseph_lock)
        self.assertEqual(
            response['status'], 'Error: Someone else is logged into that account.')

    def test_list_account_success(self):
        args = {'query': "kevin"}
        response = self.server.process_list_accounts(args)
        self.assertEqual(response['status'], 'Success')
        self.assertEqual(response['accounts'], 'kevin')

    def test_list_account_regex_bad(self):
        args = {'query': "["}
        response = self.server.process_list_accounts(args)
        self.assertEqual(response['status'], 'Error: regex is malformed.')

    def test_send_msg_success(self):
        args = {'recipient': 'kevin', 'message': 'hello'}
        uuid = self.server.logged_in.logged_in["kevin"]
        (client_socket, socket_lock) = [k for k, v in self.server.clients.items() if v == uuid][0]
        response = self.server.process_send_msg(args, client_socket, socket_lock)
        self.assertEqual(response['status'], 'Success')
        self.assertTrue("kevin" in self.server.undelivered_msg.undelivered_msg.keys())

    def test_send_msg_failure_no_recipient(self):
        args = {'recipient': 'joseph', 'message': 'hello'}
        uuid = self.server.logged_in.logged_in["kevin"]
        (client_socket, socket_lock) = [k for k, v in self.server.clients.items() if v == uuid][0]
        response = self.server.process_send_msg(args, client_socket, socket_lock)
        self.assertEqual(
            response['status'], 'Error: The recipient of the message does not exist.')

    def test_delete_account_success(self):
        uuid = self.server.logged_in.logged_in["kevin"]
        (client_socket, socket_lock) = [
                    k for k, v in self.server.clients.items() if v == uuid][0]
        response = self.server.process_delete_account(
            client_socket, socket_lock)
        self.assertEqual(response['status'], 'Success')
        self.assertFalse('kevin' in self.server.account_list.account_list)

    def test_delete_account_fail(self):
        joseph_socket = MagicMock()
        joseph_lock = threading.Lock()
        self.server.process_new_client({'uuid': str(3)}, joseph_socket, joseph_lock)
        response = self.server.process_delete_account(
            joseph_socket, joseph_lock)
        self.assertEqual(
            response['status'], 'Error: Need to be logged in to delete your account.')

    def test_logoff_success(self):
        uuid = self.server.logged_in.logged_in["kevin"]
        (client_socket, socket_lock) = [k for k, v in self.server.clients.items() if v == uuid][0]
        response = self.server.process_logoff(client_socket, socket_lock)
        self.assertEqual(response['status'], 'Success')
        self.assertFalse('kevin' in self.server.logged_in.logged_in.keys())

    def test_logoff_fail(self):
        joseph_socket = MagicMock()
        joseph_lock = threading.Lock()
        self.server.process_new_client({'uuid': str(3)}, joseph_socket, joseph_lock)
        response = self.server.process_logoff(joseph_socket, joseph_lock)
        self.assertEqual(
            response['status'], 'Error: Need to be logged in to log out of your account.')
    
    def test_update_add_account_list(self):
        args = {'add_flag': 'True', 'username': 'joseph'}
        response = self.server.process_update_accounts(args)
        self.assertTrue('joseph' in self.server.account_list.account_list)
        
    def test_update_remove_account_list(self):
        args = {'add_flag': 'False', 'username': 'kevin'}
        response = self.server.process_update_accounts(args)
        self.assertFalse('kevin' in self.server.account_list.account_list)
    
    def test_update_add_login(self):
        args = {'add_flag': 'True', 'username': 'joseph', 'uuid':str(3)}
        response = self.server.process_update_login(args)
        self.assertTrue('joseph' in self.server.logged_in.logged_in.keys())
        
    def test_update_remove_login(self):
        args = {'add_flag': 'False', 'username': 'kevin', 'uuid':KEVIN_UUID}
        response = self.server.process_update_login(args)
        self.assertFalse('kevin' in self.server.logged_in.logged_in.keys())
    
    def test_update_add_messages(self):
        args = {'add_one': 'True', 'recipient': 'kevin', 'sender': 'howie', 'message': 'Hello world!'}
        response = self.server.process_update_message_state(args)
        self.assertTrue(len(self.server.undelivered_msg.undelivered_msg['kevin']) >0)
        
    def test_update_addall_messages(self):
        args = {'add_one': 'False', 'recipient': 'kevin', 'sender': 'howie\rjoseph', 'message': 'Hello world!\rsup'}
        response = self.server.process_update_message_state(args)
        self.assertTrue(len(self.server.undelivered_msg.undelivered_msg['kevin']) >1)

    


if __name__ == '__main__':
    unittest.main()
