import os

# NETWORK
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", 8080))
# max bytes read per recv() call
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", 4096))

# STORAGE
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_FILE = os.path.join(BASE_DIR, "data", "dictionary.json")

# PROTOCOL

# commands the server understands
CMD_SEARCH = "SEARCH"   # search for a word's definition
CMD_ADD = "ADD"         # add a new word and its definition
CMD_DELETE = "DELETE"   # delete a word from the dictionary
CMD_LIST = "LIST"       # list all words in the dictionary

# Responses sent back to clients
RESP_OK = "OK"             # command succeeded
RESP_NOT_FOUND = "NOT_FOUND"  # word not found in dictionary
RESP_ERROR = "ERROR"       # generic error response
RESP_UNKNOWN = 'UNKNOWN_COMMAND'  # command not recognized
RESP_BUSY = 'SERVER_BUSY'     # server is too busy to handle the request

# server behaviour
MAX_CONNECTIONS = 10  # max clients queued waiting to connect
THREAD_POOL_SIZE = 20  # max concurrent client handlers; extras are rejected

# Web UI
UI_HOST = os.getenv("UI_HOST", "localhost")
UI_PORT = int(os.getenv("UI_PORT", 8000))

# Timestamp field names ( keys in each dictionary entry )
TS_ADDED = "added_at"
TS_UPDATED = "updated_at"
TS_SEARCHED = "last_searched_at"
