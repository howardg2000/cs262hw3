
import unittest
import threading
import chat_service_pb2
from server import ChatServiceServicer
from unittest.mock import MagicMock

TEST_HOST = "127.0.0.1"
TEST_PORT = 6000


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server = ChatServiceServicer()
        self.server.account_list.append("kevin")
        self.server.account_list.append("howie")
        kevin_socket = "kevin_socket"
        howie_socket = "howie_socket"
        self.server.logged_in["kevin"] = kevin_socket
        self.server.logged_in["howie"] = howie_socket

    def test_create_account_success(self):
        username = "joseph"
        joseph_socket = "joseph_socket"
        context = MagicMock()
        context.peer.return_value = joseph_socket

        response = self.server.CreateAccount(
            chat_service_pb2.CreateAccountRequest(username=username), context)
        self.assertEqual(response.status, 'Success')
        self.assertTrue(("joseph" in self.server.account_list))
        self.assertTrue(("joseph" in self.server.logged_in))

    def test_create_account_fail_exists(self):
        username = "kevin"
        joseph_socket = "joseph_socket"
        context = MagicMock()
        context.peer.return_value = joseph_socket

        response = self.server.CreateAccount(
            chat_service_pb2.CreateAccountRequest(username=username), context)
        self.assertEqual(response.status, 'Error: Account already exists.')

    def test_create_account_fail_logged_in(self):
        username = "joseph"
        joseph_socket = self.server.logged_in["kevin"]
        context = MagicMock()
        context.peer.return_value = joseph_socket

        response = self.server.CreateAccount(
            chat_service_pb2.CreateAccountRequest(username=username), context)
        self.assertEqual(
            response.status, 'Error: User can\'t create an account while logged in.')

    def test_login_success(self):
        username = "kevin"
        self.server.logged_in.pop("kevin")
        kevin_socket = "kevin_socket"
        context = MagicMock()
        context.peer.return_value = kevin_socket

        response = self.server.LogIn(
            chat_service_pb2.LogInRequest(username=username), context)
        self.assertEqual(response.status, 'Success')
        self.assertTrue("kevin" in self.server.logged_in.keys())

    def test_login_fail_doesnt_exist(self):
        username = "joseph"
        joseph_socket = "joseph_socket"
        context = MagicMock()
        context.peer.return_value = joseph_socket

        response = self.server.LogIn(
            chat_service_pb2.LogInRequest(username=username), context)
        self.assertEqual(response.status, 'Error: Account does not exist.')

    def test_login_fail_someone_logged_in(self):
        username = "kevin"
        kevin2_socket = "kevin2_socket"
        context = MagicMock()
        context.peer.return_value = kevin2_socket

        response = self.server.LogIn(
            chat_service_pb2.LogInRequest(username=username), context)
        self.assertEqual(
            response.status, 'Error: Someone else is logged into that account.')

    def test_list_account_success(self):
        query = "kevin"
        context = MagicMock()
        response = self.server.ListAccounts(
            chat_service_pb2.ListAccountsRequest(query=query), context)
        self.assertEqual(response.status, 'Success')
        self.assertEqual(response.accounts, ['kevin'])

    def test_list_account_regex_bad(self):
        query = '['
        context = MagicMock()
        response = self.server.ListAccounts(
            chat_service_pb2.ListAccountsRequest(query=query), context)
        self.assertEqual(response.status, 'Error: regex is malformed.')

    def test_send_msg_success(self):
        recipient = 'kevin'
        message = 'hello'
        context = MagicMock()
        context.peer.return_value = 'howie_socket'
        response = self.server.SendMessage(
            chat_service_pb2.SendMessageRequest(recipient=recipient, message=message), context)
        self.assertEqual(response.status, 'Success')
        self.assertTrue("kevin" in self.server.undelivered_msg.keys())

    def test_send_msg_failure_no_recipient(self):
        recipient = 'joseph'
        message = 'hello'
        context = MagicMock()
        context.peer.return_value = 'kevin_socket'
        response = self.server.SendMessage(
            chat_service_pb2.SendMessageRequest(recipient=recipient, message=message), context)
        self.assertEqual(
            response.status, 'Error: The recipient of the message does not exist.')

    def test_delete_account_success(self):
        context = MagicMock()
        context.peer.return_value = 'kevin_socket'
        response = self.server.DeleteAccount(
            chat_service_pb2.DeleteAccountRequest(), context)
        self.assertEqual(response.status, 'Success')
        self.assertFalse('kevin' in self.server.account_list)

    def test_delete_account_fail(self):
        context = MagicMock()
        context.peer.return_value = 'joseph_socket'
        response = self.server.DeleteAccount(
            chat_service_pb2.DeleteAccountRequest(), context)
        self.assertEqual(
            response.status, 'Error: Need to be logged in to delete your account.')

    def test_logoff_success(self):
        context = MagicMock()
        context.peer.return_value = 'kevin_socket'
        response = self.server.LogOff(
            chat_service_pb2.LogOffRequest(), context)
        self.assertEqual(response.status, 'Success')
        self.assertFalse('kevin' in self.server.logged_in.keys())

    def test_logoff_fail(self):
        context = MagicMock()
        context.peer.return_value = 'joseph_socket'
        response = self.server.LogOff(
            chat_service_pb2.LogOffRequest(), context)
        self.assertEqual(
            response.status, 'Error: Need to be logged in to log out of your account.')

    def test_get_msg_success(self):
        messages = [('howie', 'first hello'),
                    ('howie', 'second hello'), ('joseph', 'third hello')]
        self.server.undelivered_msg['kevin'] = messages[:]
        context = MagicMock()
        context.peer.return_value = 'kevin_socket'

        for i, msg_info in enumerate(self.server.GetMessages(
                chat_service_pb2.GetMessagesRequest(), context)):
            self.assertEqual((msg_info.sender, msg_info.message), messages[i])


if __name__ == '__main__':
    unittest.main()
