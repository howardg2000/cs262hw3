import os
import tempfile
import unittest
from undelivered_messages import UndeliveredMessages


class TestUndeliveredMessages(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.filename = self.temp_file.name

        self.undelivered_messages = UndeliveredMessages(self.filename)

    def tearDown(self):
        # Delete the temporary file
        os.remove(self.filename)

    def test_add_message(self):
        # Add a message for a recipient
        recipient = "Alice"
        sender = "Bob"
        message = "Hello Alice!"
        self.undelivered_messages.add_message(recipient, sender, message)

        # Check that the message was added to the undelivered messages
        expected_messages = [(sender, message)]
        actual_messages = self.undelivered_messages.undelivered_msg[recipient]
        self.assertEqual(actual_messages, expected_messages)

        # Check that the message was added to the file
        with open(self.filename, 'r') as f:
            actual_line = f.readline().strip()
        expected_line = f"{recipient} {sender} {message}"
        self.assertEqual(actual_line, expected_line)

    def test_get_messages(self):
        # Add messages for two recipients
        recipient1 = "Alice"
        sender1 = "Bob"
        message1 = "Hello Alice!"
        self.undelivered_messages.add_message(recipient1, sender1, message1)
        recipient2 = "Charlie"
        sender2 = "David"
        message2 = "Hi Charlie!"
        self.undelivered_messages.add_message(recipient2, sender2, message2)

        # Get the undelivered messages for all recipients
        expected_messages = [(recipient1, [(sender1, message1)]),
                             (recipient2, [(sender2, message2)])]
        actual_messages = list(self.undelivered_messages.get_messages())
        self.assertEqual(actual_messages, expected_messages)

    def test_update_messages(self):
        # Add messages for a recipient
        recipient = "Alice"
        sender1 = "Bob"
        message1 = "Hello Alice!"
        self.undelivered_messages.add_message(recipient, sender1, message1)
        sender2 = "Charlie"
        message2 = "Hi Alice!"
        self.undelivered_messages.add_message(recipient, sender2, message2)

        # Update the messages for the recipient
        new_messages = [(sender2, "Hey Alice!"), (sender1, "Hi Alice!")]
        self.undelivered_messages.update_messages(recipient, new_messages)

        # Check that the messages were updated in memory
        expected_messages = new_messages
        actual_messages = self.undelivered_messages.undelivered_msg[recipient]
        self.assertEqual(actual_messages, expected_messages)

        # Check that the messages were updated in the file
        with open(self.filename, 'r') as f:
            actual_lines = f.readlines()
        expected_lines = [
            f"{recipient} {sender} {message}\n" for sender, message in new_messages]
        self.assertEqual(actual_lines, expected_lines)


if __name__ == "__main__":
    unittest.main()
