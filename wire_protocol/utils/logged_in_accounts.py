import os

class LoggedInAccounts:
    def __init__(self, filename):
        self.filename = filename
        
        self.logged_in = {}  # Map of username to uuid
        open(self.filename, 'w').close()  # Clear the file

    def login(self, username, uuid):
        self.logged_in[username] = uuid
        with open(self.filename, "a") as f:
            f.write(f"{username} {uuid}\n")

    def is_logged_in(self, uuid):
        is_logged_in = uuid in self.logged_in.values()
        return is_logged_in

    def username_is_logged_in(self, username):
        is_logged_in = username in self.logged_in.keys()
        return is_logged_in
    
    def logoff(self, username):
        if username in self.logged_in.keys():
            self.logged_in.pop(username)

            # Remove the username entry from the file
            with open(self.filename, 'r') as f:
                lines = f.readlines()
            with open(self.filename, 'w') as f:
                f.writelines(filter(lambda line: line.strip() and line.strip().split()[0] != username, lines))
                    
            return True
        return False

    def get_username(self, uuid):
        usernameArr = [k for k, v in self.logged_in.items() if v == uuid]
        if (len(usernameArr) > 0):
            return usernameArr[0]
        return None
    
    def get_uuid_from_username(self, username):
        return self.logged_in[username]