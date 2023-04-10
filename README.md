# Design Exercise 3

## Overview
This is a simple chat messaging service. It supports multiple clients connecting to the server. We support several operations:
- Creating an account
- Logging into an existing account
- List exist accounts
- Sending a message to another user
- Logging out of an existing account
- Deleting an account

This functionality is implemented using our own wire protocol. It is persistent and 2-fault tolerant.

## Prerequisites
- MacOS
- Python 3.10
  - To install/upgrade using brew
    ```sh
    brew install python
    ```
  - To install/upgrade using conda (creates new environment)
    ```sh
    conda create -n py310 python=3.10 anaconda
    ```


## Setting up the Custom Wire Protocol Server
To run the server, first ensure that the machine that will be running the server has turned off their firewall. Then, from the project root, run 
```sh
python3 run_server.py <config.json> <id>
```
Here `config.json` is contains the host, port, and id of all servers we will be running. The id argument is the id of the server we want to start running. The config json should be of the form 
```json
{
    "servers": [
        {
            "id": 1,
            "host": "127.0.0.1",
            "port": 6000
        },
        ...
    ]
}
```

If ```Server started``` is printed, then the server is ready to accept connections. There is a 10 second buffer time to allow for all servers to be started before servers begin connecting to each other. Make sure to begin running all the servers in this time frame.

To find the IP address which the server is being hosted at, go to 
```System Preferences -> Network -> Advanced -> TCP/IP```. The IP address the server is being hosted at should be listed there. 

## Setting up the Custom Wire Protocol Client
To run the client, first ensure that the machine that will be running the server has turned off their firewall. Then, from the project root, run 
```sh
python3 run_client.py <config.json>
```
The config file should be the same as the one used to start the individual servers. It contains information about each of the servers so the client can connect to each, but it only sends request to the primary server. If the connection is successful, you will see ```Connected to Server```. If not, check that the host and port are correct. 


## Sending Messages
The client will prompt for a command. Typing ```help``` will provide the user with various operations.
- 1: Create account 
- 2: Login 
- 3: List accounts 
- 4: Send message 
- 5: Logoff 
- 6: Delete account

To start a remote procedure call, when prompted for a command, enter the number corresponding to the operation you would like to call. You will then be prompted for more information based on the operation requested.

## Client Error Messages
As you're sending messages, you might come across various errors. Each operation has several errors it can throw:
- Create account
  - If the account exists, the server will respond with an error
  - If the user is already logged in, the server will respond with an error
- Login 
  - If the user is already logged in, the server will respond with an error
  - If the supplied account is already logged into by another user, the server will respond with an error
  - If the supplied account doesn't exist, the server will respond with an error
- List accounts 
  - If the regex is malformed, the server will respond with an error
- Send message 
  - If the user is not logged in, the server will respond with an error
  - If the intended recipient of the message does not exist, the 
- Logoff 
  - If the user is not logged in, the server will respond with an error
- Delete account
  - If the user is not logged in, the server will respond with an error

## Stopping the Client/Server
To stop the client or server, simply press ```ctrl-C``` to exit the client or server. To make this a 2-fault tolerant system, you will need to start at least 3 servers, and as long as one server is running, the clients will be able to have full functionality.

<br>

# Observation Notebook

Our design notebook can be found [here.](https://docs.google.com/document/d/1-7ufVaAF7j0-TS5VsafrtoBH0hl9ARip3XTBgWznrYU/edit?usp=sharing)
