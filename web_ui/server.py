"""
HTTP server — dictionary web UI with authentication.
 
Public endpoints (no token needed):
    POST /api/signup     create account (first user becomes admin)
    POST /api/login      verify credentials, return session token + role
 
Protected endpoints (require Authorization: Bearer <token> header):
    GET  /api/me         return current user's username and role
    GET  /api/entries    list all entries with timestamps
    GET  /api/search     search for a word
    POST /api/add        add/update a word  [admin only]
    POST /api/delete     delete a word      [admin only]
    GET  /api/info       server LAN IP and ports
 
Static files:
    GET  /               index.html
    GET  /index.html     index.html
    GET  /style.css      stylesheet
    GET  /app.js         JavaScript
"""

from config import (
    BUFFER_SIZE, HOST, PORT,
    UI_HOST, UI_PORT,
    DICT_FILE,
    RESP_NOT_FOUND, RESP_OK, RESP_BUSY, RESP_ERROR,
)
import hashlib
import json
import os
import secrets
import socket
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..'))


UI_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(UI_DIR, 'users.json')
STATIC_FILES = {
    '/': ('index.html', 'text/html'),
    '/index.html': ('index.html', 'text/html'),
    '/style.css': ('style.css', 'text/css'),
    '/app.js': ('app.js', 'application/javascript'),
}

_DICT_HOST = HOST
_DICT_PORT = PORT

# ── In-memory session store: token -> {username, role} ────────────────────────
_sessions: dict[str, dict] = {}


# ── User store helpers ─────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_users(users: dict) -> None:
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)


# ── TCP helper ─────────────────────────────────────────────────────────────────

def tcp_send(command: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        try:
            s.connect((_DICT_HOST, _DICT_PORT))
            s.sendall((command + '\n').encode('utf-8'))
            return s.recv(BUFFER_SIZE).decode('utf-8').strip()
        except ConnectionRefusedError:
            return f"{RESP_ERROR}:dictionary server is not running"
        except socket.timeout:
            return f"{RESP_ERROR}:request timed out"
        except OSError as e:
            return f"{RESP_ERROR}:{e}"


# ── Request handler ────────────────────────────────────────────────────────────

class UIRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[WebUI] {self.address_string()} — {format % args}")

    # ── Auth helpers ───────────────────────────────────────────────────────────

    def _get_token(self) -> str | None:
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            return auth[7:]
        return None

    def _current_user(self) -> dict | None:
        token = self._get_token()
        if not token:
            return None
        return _sessions.get(token)

    def _require_auth(self) -> dict | None:
        user = self._current_user()
        if not user:
            self._respond(401, {'error': 'not authenticated'})
        return user

    def _require_admin(self) -> dict | None:
        user = self._require_auth()
        if user and user.get('role') != 'admin':
            self._respond(403, {'error': 'admin access required'})
            return None
        return user

    # ── Routing ────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path in STATIC_FILES:
            fname, ctype = STATIC_FILES[path]
            self._serve_file(fname, ctype)
            return

        if path == '/api/entries':
            self._api_entries()
        elif path == '/api/search':
            self._api_search(params)
        elif path == '/api/me':
            self._api_me()
        elif path == '/api/info':
            self._api_info()
        else:
            self._respond(404, {'error': 'not found'})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == '/api/signup':
            self._api_signup(body)
        elif path == '/api/login':
            self._api_login(body)
        elif path == '/api/add':
            self._api_add(body)
        elif path == '/api/delete':
            self._api_delete(body)
        else:
            self._respond(404, {'error': 'not found'})

    # ── Auth endpoints ─────────────────────────────────────────────────────────

    def _api_signup(self, body: dict):
        username = body.get('username', '').strip().lower()
        password = body.get('password', '').strip()

        if not username or not password:
            self._respond(400, {'error': 'username and password are required'})
            return
        if len(username) < 3:
            self._respond(
                400, {'error': 'username must be at least 3 characters'})
            return
        if len(password) < 6:
            self._respond(
                400, {'error': 'password must be at least 6 characters'})
            return

        users = _load_users()
        if username in users:
            self._respond(409, {'error': 'username already taken'})
            return

        # First user ever becomes admin; all subsequent users are regular users
        role = 'admin' if len(users) == 0 else 'user'
        users[username] = {'password': _hash_password(password), 'role': role}
        _save_users(users)

        token = secrets.token_hex(32)
        _sessions[token] = {'username': username, 'role': role}
        print(f"[Auth] New account: {username} ({role})")
        self._respond(
            200, {'token': token, 'role': role, 'username': username})

    def _api_login(self, body: dict):
        username = body.get('username', '').strip().lower()
        password = body.get('password', '').strip()

        if not username or not password:
            self._respond(400, {'error': 'username and password are required'})
            return

        users = _load_users()
        user = users.get(username)
        if not user or user['password'] != _hash_password(password):
            self._respond(401, {'error': 'incorrect username or password'})
            return

        token = secrets.token_hex(32)
        _sessions[token] = {'username': username, 'role': user['role']}
        print(f"[Auth] Login: {username} ({user['role']})")
        self._respond(
            200, {'token': token, 'role': user['role'], 'username': username})

    def _api_me(self):
        user = self._require_auth()
        if user:
            self._respond(
                200, {'username': user['username'], 'role': user['role']})

    # ── Dictionary endpoints ───────────────────────────────────────────────────

    def _api_info(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except OSError:
            ip = "unknown"
        self._respond(200, {
            'server_ip': ip,
            'dict_port': _DICT_PORT,
            'ui_port':   self.server.server_address[1],
        })

    def _api_entries(self):
        if not self._require_auth():
            return
        try:
            if not os.path.exists(DICT_FILE):
                self._respond(200, {'entries': []})
                return
            with open(DICT_FILE, 'r') as f:
                data = json.load(f)
            entries = []
            for word, entry in sorted(data.items()):
                if isinstance(entry, dict):
                    entries.append({
                        'word':             word,
                        'definition':       entry.get('definition', ''),
                        'added_at':         entry.get('added_at'),
                        'updated_at':       entry.get('updated_at'),
                        'last_searched_at': entry.get('last_searched_at'),
                    })
                else:
                    entries.append({'word': word, 'definition': entry,
                                    'added_at': None, 'updated_at': None,
                                    'last_searched_at': None})
            self._respond(200, {'entries': entries})
        except (json.JSONDecodeError, OSError) as e:
            self._respond(503, {'error': str(e)})

    def _api_search(self, params: dict):
        if not self._require_auth():
            return
        word = params.get('word', [''])[0].strip()
        if not word:
            self._respond(400, {'error': 'word parameter required'})
            return
        result = tcp_send(f'SEARCH:{word}')
        if result.startswith(RESP_ERROR):
            self._respond(503, {'error': result})
        elif result == RESP_NOT_FOUND:
            self._respond(404, {'found': False, 'word': word})
        elif result == RESP_BUSY:
            self._respond(503, {'error': 'server busy'})
        else:
            self._respond(
                200, {'found': True, 'word': word, 'definition': result})

    def _api_add(self, body: dict):
        if not self._require_admin():
            return
        word = body.get('word', '').strip()
        definition = body.get('definition', '').strip()
        if not word or not definition:
            self._respond(400, {'error': 'word and definition are required'})
            return
        result = tcp_send(f'ADD:{word}={definition}')
        if result == RESP_OK:
            self._respond(200, {'success': True})
        elif result == RESP_BUSY:
            self._respond(503, {'error': 'server busy'})
        else:
            self._respond(500, {'error': result})

    def _api_delete(self, body: dict):
        if not self._require_admin():
            return
        word = body.get('word', '').strip()
        if not word:
            self._respond(400, {'error': 'word is required'})
            return
        result = tcp_send(f'DELETE:{word}')
        if result == RESP_OK:
            self._respond(200, {'success': True})
        elif result == RESP_NOT_FOUND:
            self._respond(404, {'error': f"'{word}' not found"})
        elif result == RESP_BUSY:
            self._respond(503, {'error': 'server busy'})
        else:
            self._respond(500, {'error': result})

    # ── Static / helpers ───────────────────────────────────────────────────────

    def _serve_file(self, filename: str, content_type: str):
        filepath = os.path.join(UI_DIR, filename)
        if not os.path.exists(filepath):
            self._respond(404, {'error': f'{filename} not found'})
            return
        with open(filepath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _respond(self, status: int, payload: dict):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)


# ── Entry point ────────────────────────────────────────────────────────────────

def main(dict_host: str = HOST, dict_port: int = PORT,
         ui_host: str = UI_HOST, ui_port: int = UI_PORT):
    global _DICT_HOST, _DICT_PORT
    _DICT_HOST = dict_host
    _DICT_PORT = dict_port
    server = HTTPServer((ui_host, ui_port), UIRequestHandler)
    print(f"[WebUI] Serving on http://{ui_host}:{ui_port}")
    print(
        f"[WebUI] Connecting to dictionary server at {dict_host}:{dict_port}")
    print(f"[WebUI] First user to sign up becomes admin.")
    print(f"[WebUI] Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WebUI] Stopped.")


if __name__ == '__main__':
    main()
