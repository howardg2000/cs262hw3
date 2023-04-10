import os

class AccountList:
    def __init__(self, filename):
        self.filename = filename
        
        self.account_list = []
        if os.path.exists(filename):
            # Read in file to populate account list
            with open(self.filename, 'r') as f:
                lines = f.readlines()
            self.account_list = [line.strip() for line in lines]

    def create_account(self, username):
        self.account_list.append(username)
        with open(self.filename, 'a') as f:
            f.write(f"{username}\n")

    def remove(self, username):
        self.account_list.remove(username)
        with open(self.filename, 'r') as f:
            lines = f.readlines()
        with open(self.filename, 'w') as f:
            f.writelines(filter(lambda line: line.strip() and line.strip().split()[0] != username, lines))

    def contains(self, username):
        return username in self.account_list

    def search_accounts(self, pattern):
        result = []
        for account in self.account_list:
            if pattern.match(account):
                result.append(account)
        return result
    