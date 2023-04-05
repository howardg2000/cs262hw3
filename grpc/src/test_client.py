
import unittest
from io import StringIO
import chat_service_pb2
from client import Client
from unittest.mock import MagicMock, PropertyMock, patch

TEST_HOST = "127.0.0.1"
TEST_PORT = 6000


def message_generator(messages):
    for message in messages:
        yield message


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.stub = MagicMock()
        messages = [chat_service_pb2.ChatMessage(sender="kevin", message="Hello"), chat_service_pb2.
                    ChatMessage(sender="joseph", message="Hello2")]
        self.stub.GetMessages.return_value = message_generator(messages)
        self.client = Client(self.stub)

    def test_listen_for_messages_success(self):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._fetch_and_print_messages()
            self.assertEqual(fake_out.getvalue(),
                             "\nMessage from kevin: Hello\n\nMessage from joseph: Hello2\n> Enter command (type 'help' for list of commands): \n")

    def test_create_account_success(self):
        username = "howie"
        self.stub.CreateAccount.return_value = chat_service_pb2.CreateAccountResponse(
            status="Success", username=username)
        with patch('builtins.input', return_value=username), patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._create_account_or_log_in("CREATE_ACCOUNT")
            self.assertEqual(fake_out.getvalue().strip(),
                             f'Success! Logged in as {username}')
            self.assertEqual(self.client.username, username)

    def test_create_account_fail(self):
        username = "howie"
        self.stub.CreateAccount.return_value = chat_service_pb2.CreateAccountResponse(
            status="Error", username=username)
        with patch('builtins.input', return_value=username), patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._create_account_or_log_in("CREATE_ACCOUNT")
            self.assertEqual(fake_out.getvalue().strip(),
                             f'Error')
            self.assertIsNone(self.client.username)

    def test_invalid_username(self):
        usernames = ['a', 'ab', 'abc', 'abcde!',
                     'abcdeabcdeabcdeabcdeabcdeabcde', 'ab201.?']
        for username in usernames:
            with patch('builtins.input', return_value=username), patch('sys.stdout', new=StringIO()) as fake_out:
                self.client._create_account_or_log_in("CREATE_ACCOUNT")
                self.assertEqual(fake_out.getvalue().strip(),
                                 'Invalid username. Username must be between 5 and 20 characters and only contain letters and numbers.')
                self.assertIsNone(self.client.username)

    def test_log_in_success(self):
        username = "howie"
        self.stub.LogIn.return_value = chat_service_pb2.LogInResponse(
            status="Success", username=username)
        with patch('builtins.input', return_value=username), patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._create_account_or_log_in("LOG_IN")
            self.assertEqual(fake_out.getvalue().strip(),
                             f'Success! Logged in as {username}')
            self.assertEqual(self.client.username, username)

    def test_list_accounts_success(self):
        query = ".*"
        self.stub.ListAccounts.return_value = chat_service_pb2.ListAccountsResponse(
            status="Success", accounts=['howie', 'howie2'])
        with patch('builtins.input', return_value=query), patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._list_accounts()
            self.assertEqual(fake_out.getvalue().strip(),
                             f'Account search results:\nhowie\nhowie2')

    def test_list_accounts_fail(self):
        query = "["
        self.stub.ListAccounts.return_value = chat_service_pb2.ListAccountsResponse(
            status="Error", accounts=[])
        with patch('builtins.input', return_value=query), patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._list_accounts()
            self.assertEqual(fake_out.getvalue().strip(),
                             f'Error')

    def test_send_message_success(self):
        input = "user_input"
        self.stub.SendMessage.return_value = chat_service_pb2.SendMessageResponse(
            status="Success")
        with patch('builtins.input', return_value=input), patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._send_message()
            self.assertEqual(fake_out.getvalue().strip(),
                             f'Message sent successfully.')

    def test_logoff_success(self):
        self.stub.LogOff.return_value = chat_service_pb2.LogOffResponse(
            status="Success")
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._logoff()
            self.assertEqual(fake_out.getvalue().strip(),
                             f'You are now logged out.')
            self.assertIsNone(self.client.username)

    def test_delete_account_success(self):
        self.stub.DeleteAccount.return_value = chat_service_pb2.DeleteAccountResponse(
            status="Success")
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.client._delete_account()
            self.assertEqual(fake_out.getvalue().strip(),
                             f'Deleting account successful; you are now logged out.')
            self.assertIsNone(self.client.username)


if __name__ == '__main__':
    unittest.main()
