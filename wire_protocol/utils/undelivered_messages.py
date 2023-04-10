import os
from collections import defaultdict

class UndeliveredMessages:
    def __init__(self, filename):
        self.filename = filename
        
        self.undelivered_msg = defaultdict(list) # Map of recipient username to list of (sender, message) for that recipient
        if os.path.exists(filename):
            # Read the file and store the messages in a dictionary
            with open(self.filename, 'r') as f:
                lines = f.readlines()
            for line in lines:
                if line.strip():
                    recipient, sender, message = line.strip().split(' ', 2)
                    self.undelivered_msg[recipient].append((sender, message))

    def add_message(self, recipient, sender, message):
        "Add a message to the list of undelivered messages for a recipient."
        self.undelivered_msg[recipient] += [
            (sender, message)]
        with open(self.filename, 'a') as f:
            f.write(f"{recipient} {sender} {message}\n")

    def get_messages(self):
        return self.undelivered_msg.items()
    
    def update_messages(self, recipient, message_infos):
        # Update the messages for a recipient. Update operation.
        self.undelivered_msg[recipient] = message_infos
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        print(lines)
        with open(self.filename, 'w') as f:
            f.writelines(filter(lambda line: line.strip() and line.strip().split()[0] != recipient, lines))
            for sender, message in message_infos:
                f.write(f"{recipient} {sender} {message}\n")

