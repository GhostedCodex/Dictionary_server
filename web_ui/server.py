"""
HTTP server that bridges the browser and the dictionary TCP server.

Serves index.html and exposes a small REST API:
    GET  /api/entries          → list all entries
    GET  /api/search?word=cat  → search for a word
    POST /api/add              → add a word  (JSON body: {word, definition})
    POST /api/delete           → delete a word (JSON body: {word})

Every API handler opens a fresh TCP connection to the dictionary server,
sends the appropriate command, reads the response, then closes the socket.
"""

from config import (
    BUFFER_SIZE, HOST, PORT,
    UI_HOST, UI_PORT,
    RESP_NOT_FOUND, RESP_OK, RESP_BUSY, RESP_ERROR,
)
import json
import os
import socket
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..'))


UI_DIR = os.path.dirname(os.path.abspath(__file__))

# Resolved at startup — overridable for testing
_DICT_HOST = HOST
_DICT_PORT = PORT


# TCP helper

def tcp_send(command: str) -> str:
    """Open a connection to the dictionary server, send one command, return the response."""
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


# Request handler

class UIRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[WebUI] {self.address_string()} — {format % args}")

    # Routing

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path in ('/', '/index.html'):
            self._serve_file('index.html', 'text/html')
        elif path == '/api/entries':
            self._api_entries()
        elif path == '/api/search':
            self._api_search(params)
        else:
            self._respond(404, {'error': 'not found'})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == '/api/add':
            self._api_add(body)
        elif path == '/api/delete':
            self._api_delete(body)
        else:
            self._respond(404, {'error': 'not found'})

    #  API handlers

    def _api_entries(self):
        raw = tcp_send('LIST')

        if raw.startswith(RESP_ERROR):
            self._respond(503, {'error': raw})
            return
        if raw == 'EMPTY':
            self._respond(200, {'entries': []})
            return

        words = [w.strip() for w in raw.split(',') if w.strip()]
        entries = []
        for word in words:
            defn = tcp_send(f'SEARCH:{word}')
            entries.append({'word': word, 'definition': defn})

        self._respond(200, {'entries': entries})

    def _api_search(self, params: dict):
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

    # Helpers

    def _serve_file(self, filename: str, content_type: str):
        filepath = os.path.join(UI_DIR, filename)
        if not os.path.exists(filepath):
            self._respond(404, {'error': f'{filename} not found'})
            return
        with open(filepath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
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
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)


# Entry point

def main(dict_host: str = HOST, dict_port: int = PORT,
         ui_host: str = UI_HOST, ui_port: int = UI_PORT):
    global _DICT_HOST, _DICT_PORT
    _DICT_HOST = dict_host
    _DICT_PORT = dict_port

    server = HTTPServer((ui_host, ui_port), UIRequestHandler)
    print(f"[WebUI] Serving on http://{ui_host}:{ui_port}")
    print(
        f"[WebUI] Connecting to dictionary server at {dict_host}:{dict_port}")
    print(f"[WebUI] Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WebUI] Stopped.")


if __name__ == '__main__':
    main()
