import os
from collections import defaultdict

class UndeliveredMessages:
    """Class to store undelivered messages. The messages are stored in memory and in a file."""
    def __init__(self, filename: str):
        self.filename = filename
        
        self.undelivered_msg = defaultdict(list) # Map of recipient username to list of (sender, message) for that recipient
        if os.path.exists(filename):
            # Read the file and store the messages in a dictionary by recipient
            with open(self.filename, 'r') as f:
                lines = f.readlines()
            for line in lines:
                if line.strip():
                    recipient, sender, message = line.strip().split(' ', 2)
                    self.undelivered_msg[recipient].append((sender, message))

    def add_message(self, recipient: str, sender: str, message: str):
        """Add a message to the list of undelivered messages for a recipient."""
        self.undelivered_msg[recipient] += [
            (sender, message)]
        with open(self.filename, 'a') as f:
            f.write(f"{recipient} {sender} {message}\n")
            f.flush()

    def get_messages(self):
        """Return a list of (recipient, [(sender, message)]) for all recipients with undelivered messages."""
        return self.undelivered_msg.items()
    
    def update_messages(self, recipient, message_infos):
        """Update the messages for a recipient. Replaces the message list for that recipient with the given messages."""
        self.undelivered_msg[recipient] = message_infos
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        with open(self.filename, 'w') as f:
            f.writelines(filter(lambda line: line.strip() and line.strip().split()[0] != recipient, lines))
            f.flush()
            for sender, message in message_infos:
                if (not (sender == "" or message == "")):
                    f.write(f"{recipient} {sender} {message}\n")
                    f.flush()

