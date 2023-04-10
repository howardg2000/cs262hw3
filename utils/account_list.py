import os

class AccountList:
    """A class to manage the list of existing accounts.  The list is in memory and also in a file for persistence."""
    def __init__(self, filename: str):
        self.filename = filename
        
        self.account_list = []
        if os.path.exists(filename):
            # Read in file to populate account list
            with open(self.filename, 'r') as f:
                lines = f.readlines()
            self.account_list = [line.strip() for line in lines if line.strip()]

    def create_account(self, username: str):
        """Add an account to the list and write it to the file."""
        self.account_list.append(username)
        with open(self.filename, 'a') as f:
            f.write(f"{username}\n")
            f.flush()

    def remove(self, username: str):
        """Remove an account from the list and remove it from the file."""
        self.account_list.remove(username)
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        with open(self.filename, 'w') as f:
            f.writelines(filter(lambda line: line.strip() and line.strip().split()[0] != username, lines))
            f.flush()

    def contains(self, username: str):
        """Check if an account is in the list."""
        return username in self.account_list

    def search_accounts(self, pattern):
        """
        Search for accounts that match a pattern.
        
        Args:
            pattern (re.Pattern): A compiled regular expression pattern.
        """
        result = []
        for account in self.account_list:
            if pattern.match(account):
                result.append(account)
        return result

    def clear(self):
        """
        Clears the account list for testing purposes
        """
        self.account_list = [] # Map of username to uuid
        open(self.filename, 'w').close() 
    