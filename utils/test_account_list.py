import os
import tempfile
import unittest
import re
from account_list import AccountList


class TestAccountList(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False)

        self.account_list = AccountList(self.tmpfile.name)

    def tearDown(self):
        # Remove the temporary file after testing
        os.remove(self.tmpfile.name)

    def test_create_account(self):
        self.account_list.create_account("user1")
        self.account_list.create_account("user2")
        self.assertTrue(self.account_list.contains("user1"))
        self.assertTrue(self.account_list.contains("user2"))
        self.assertFalse(self.account_list.contains("user3"))

    def test_remove_account(self):
        self.account_list.create_account("user1")
        self.account_list.create_account("user2")
        self.account_list.remove("user1")
        self.assertFalse(self.account_list.contains("user1"))
        self.assertTrue(self.account_list.contains("user2"))

    def test_contains(self):
        self.account_list.create_account("user1")
        self.assertTrue(self.account_list.contains("user1"))
        self.assertFalse(self.account_list.contains("user2"))

    def test_create_account_writes_file(self):
        # Create an account list and add an account
        self.account_list.create_account("user1")

        # Read the contents of the file and check that it matches the account list
        with open(self.tmpfile.name, 'r') as f:
            lines = f.readlines()
        expected_lines = ["user1\n"]
        self.assertEqual(lines, expected_lines)

    def test_remove_account_updates_file(self):
        # Create an account list and add two accounts
        self.account_list.create_account("user1")
        self.account_list.create_account("user2")

        # Remove an account and check that it was removed from the file
        self.account_list.remove("user1")
        with open(self.tmpfile.name, 'r') as f:
            lines = f.readlines()
        expected_lines = ["user2\n"]
        self.assertEqual(lines, expected_lines)

    def test_search_accounts(self):
        self.account_list.create_account("user1")
        self.account_list.create_account("user2")
        self.account_list.create_account("user3")
        self.account_list.create_account("testuser")
        self.assertListEqual(self.account_list.search_accounts(
            re.compile("user\d")), ["user1", "user2", "user3"])
        self.assertListEqual(self.account_list.search_accounts(
            re.compile("test")), ["testuser"])
        self.assertListEqual(self.account_list.search_accounts(
            re.compile("something.*")), [])


if __name__ == '__main__':
    unittest.main()
