import os
import unittest
import tempfile
from logged_in_accounts import LoggedInAccounts


class TestLoggedInAccounts(unittest.TestCase):
    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile(delete=False)
        self.test_filename = self.test_file.name
        self.accounts = LoggedInAccounts(self.test_filename)

    def tearDown(self):
        os.remove(self.test_filename)

    def test_login(self):
        username = 'testuser'
        uuid = '1234'
        self.accounts.login(username, uuid)
        self.assertTrue(username in self.accounts.logged_in.keys())
        self.assertTrue(uuid in self.accounts.logged_in.values())
        with open(self.test_filename, 'r') as f:
            contents = f.read()
            self.assertTrue(f"{username} {uuid}\n" in contents)

    def test_is_logged_in(self):
        uuid = '1234'
        self.assertFalse(self.accounts.is_logged_in(uuid))
        self.accounts.login('testuser', uuid)
        self.assertTrue(self.accounts.is_logged_in(uuid))

    def test_username_is_logged_in(self):
        username = 'testuser'
        self.assertFalse(self.accounts.username_is_logged_in(username))
        self.accounts.login(username, '1234')
        self.assertTrue(self.accounts.username_is_logged_in(username))

    def test_logoff(self):
        username = 'testuser'
        uuid = '1234'
        self.accounts.login(username, uuid)
        self.assertTrue(self.accounts.logoff(username))
        self.assertFalse(username in self.accounts.logged_in.keys())
        self.assertFalse(uuid in self.accounts.logged_in.values())
        with open(self.test_filename, 'r') as f:
            contents = f.read()
            self.assertFalse(f"{username} {uuid}\n" in contents)

    def test_get_username(self):
        uuid = '1234'
        username = 'testuser'
        self.assertIsNone(self.accounts.get_username(uuid))
        self.accounts.login(username, uuid)
        self.assertEqual(self.accounts.get_username(uuid), username)

    def test_get_uuid_from_username(self):
        uuid = '1234'
        username = 'testuser'
        self.assertRaises(
            KeyError, self.accounts.get_uuid_from_username, username)
        self.accounts.login(username, uuid)
        self.assertEqual(self.accounts.get_uuid_from_username(username), uuid)


if __name__ == '__main__':
    unittest.main()
