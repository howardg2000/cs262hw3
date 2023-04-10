
import unittest
import threading
from server import Server
from protocol import protocol_instance
from unittest.mock import MagicMock

TEST_HOST = "127.0.0.1"
TEST_PROTOCOL = protocol_instance
TEST_CONFIG = [{"host": TEST_HOST, "port": 6000, "id": 1},
               {"host": TEST_HOST, "port": 6001, "id": 2},
               {"host": TEST_HOST, "port": 6002, "id": 3}]


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server = Server(TEST_CONFIG, 1, TEST_PROTOCOL)
        self.server.account_list.append("kevin")
        self.server.account_list.append("howie")
        mock_kevin_socket = MagicMock()
        mock_howie_socket = threading.Lock()
        mock_kevin_lock = MagicMock()
        mock_howie_lock = threading.Lock()
        self.server.logged_in["kevin"] = (mock_kevin_socket, mock_kevin_lock)
        self.server.logged_in["howie"] = (mock_howie_socket, mock_howie_lock)
        self.msgId = 0

    def test_create_account_success(self):
        args = {"username": "joseph"}
        joseph_socket = MagicMock()
        response = self.server.process_create_account(
            args, joseph_socket, threading.Lock())
        self.assertEqual(response['status'], 'Success')
        self.assertTrue(("joseph" in self.server.account_list))
        self.assertTrue(("joseph" in self.server.logged_in.keys()))

    def test_create_account_fail_exists(self):
        args = {"username": "kevin"}
        joseph_socket = MagicMock()
        response = self.server.process_create_account(
            args, joseph_socket, threading.Lock())
        self.assertEqual(response['status'], 'Error: Account already exists.')

    def test_create_account_fail_logged_in(self):
        args = {"username": "joseph"}
        (joseph_socket, lock) = self.server.logged_in["kevin"]
        response = self.server.process_create_account(
            args, joseph_socket, lock)
        self.assertEqual(
            response['status'], 'Error: User can\'t create an account while logged in.')

    def test_login_success(self):
        args = {"username": "kevin"}
        self.server.logged_in.pop("kevin")
        mock_kevin_lock = MagicMock()
        mock_kevin_socket = MagicMock()
        response = self.server.process_login(
            args, mock_kevin_socket, mock_kevin_lock)
        self.assertEqual(response['status'], 'Success')
        self.assertTrue("kevin" in self.server.logged_in.keys())

    def test_login_fail_doesnt_exist(self):
        args = {"username": "joseph"}
        joseph_socket = MagicMock()
        response = self.server.process_login(
            args, joseph_socket, threading.Lock())
        self.assertEqual(response['status'], 'Error: Account does not exist.')

    def test_login_fail_someone_logged_in(self):
        args = {"username": "kevin"}
        mock_kevin_lock = threading.Lock()
        mock_kevin_socket = MagicMock()
        response = self.server.process_login(
            args, mock_kevin_socket, mock_kevin_lock)
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
        response = self.server.process_send_msg(
            args, self.server.logged_in['kevin'][0], self.server.logged_in['kevin'][1])
        self.assertEqual(response['status'], 'Success')
        self.assertTrue("kevin" in self.server.undelivered_msg.keys())

    def test_send_msg_failure_no_recipient(self):
        args = {'recipient': 'joseph', 'message': 'hello'}
        response = self.server.process_send_msg(
            args, self.server.logged_in['kevin'][0], self.server.logged_in['kevin'][1])
        self.assertEqual(
            response['status'], 'Error: The recipient of the message does not exist.')

    def test_delete_account_success(self):
        response = self.server.process_delete_account(
            self.server.logged_in['kevin'][0], self.server.logged_in['kevin'][1])
        self.assertEqual(response['status'], 'Success')
        self.assertFalse('kevin' in self.server.account_list)

    def test_delete_account_fail(self):
        joseph_socket = MagicMock()
        response = self.server.process_delete_account(
            joseph_socket, threading.Lock())
        self.assertEqual(
            response['status'], 'Error: Need to be logged in to delete your account.')

    def test_logoff_success(self):
        response = self.server.process_logoff(
            self.server.logged_in['kevin'][0], self.server.logged_in['kevin'][1])
        self.assertEqual(response['status'], 'Success')
        self.assertFalse('kevin' in self.server.logged_in.keys())

    def test_logoff_fail(self):
        joseph_socket = MagicMock()
        response = self.server.process_logoff(joseph_socket, threading.Lock())
        self.assertEqual(
            response['status'], 'Error: Need to be logged in to log out of your account.')


if __name__ == '__main__':
    unittest.main()
