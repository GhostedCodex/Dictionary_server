import os

# ── Network ──────────────────────────────────────────────────────────────────
HOST = '127.0.0.1'   # loopback; change to '0.0.0.0' to accept external clients
PORT = 5000
BUFFER_SIZE = 4096   # max bytes read per recv() call

# ── Storage ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_FILE = os.path.join(BASE_DIR, 'data', 'dictionary.json')

# ── Protocol ──────────────────────────────────────────────────────────────────
# Commands the server understands.
CMD_SEARCH = 'SEARCH'   # SEARCH:<word>
CMD_ADD = 'ADD'      # ADD:<word>=<definition>
CMD_DELETE = 'DELETE'   # DELETE:<word>
CMD_LIST = 'LIST'     # LIST  (no argument — returns all words)

# Responses sent back to the client.
RESP_OK = 'OK'
RESP_NOT_FOUND = 'NOT_FOUND'
RESP_ERROR = 'ERROR'
RESP_UNKNOWN = 'UNKNOWN_COMMAND'
RESP_BUSY = 'SERVER_BUSY'   # sent when the thread pool is at capacity

# ── Server behaviour ──────────────────────────────────────────────────────────
MAX_CONNECTIONS = 10   # max clients queued waiting to connect
THREAD_POOL_SIZE = 20   # max concurrent client handlers; extras are rejected

# ── Web UI ────────────────────────────────────────────────────────────────────
UI_HOST = '0.0.0.0'
UI_PORT = 8080

# ── Timestamp field names (keys inside each dictionary entry) ─────────────────
TS_ADDED = 'added_at'
TS_UPDATED = 'updated_at'
TS_SEARCHED = 'last_searched_at'
