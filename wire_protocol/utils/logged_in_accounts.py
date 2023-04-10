class LoggedInAccounts:
    """Class to keep track of logged in accounts. A corresponding file keeps track of usernames and uuids that are logged in."""
    def __init__(self, filename: str):
        self.filename = filename
        
        self.logged_in = {}  # Map of username to uuid
        open(self.filename, 'w').close()  # Clear the file

    def login(self, username: str, uuid: str):
        """Add a new logged in account to the file and the map."""
        self.logged_in[username] = uuid
        with open(self.filename, "a") as f:
            f.write(f"{username} {uuid}\n")
            f.flush()

    def is_logged_in(self, uuid: str):
        """Check if a uuid is logged in."""
        is_logged_in = uuid in self.logged_in.values()
        return is_logged_in

    def username_is_logged_in(self, username: str):
        """Check if a username is logged in."""
        is_logged_in = username in self.logged_in.keys()
        return is_logged_in
    
    def logoff(self, username: str):
        """Remove a logged in account from the file and the map."""
        if username in self.logged_in.keys():
            self.logged_in.pop(username)

            # Remove the username entry from the file by rewriting file with all lines except the one with the username
            with open(self.filename, 'r') as f:
                lines = f.readlines()
            with open(self.filename, 'w') as f:
                f.writelines(filter(lambda line: line.strip() and line.strip().split()[0] != username, lines))
                f.flush()
                    
            return True
        return False

    def get_username(self, uuid: str):
        # Get the username corresponding to the uuid
        usernameArr = [k for k, v in self.logged_in.items() if v == uuid]
        if (len(usernameArr) > 0):
            return usernameArr[0]
        return None
    
    def get_uuid_from_username(self, username: str):
        """Get the uuid corresponding to the username."""
        return self.logged_in[username]