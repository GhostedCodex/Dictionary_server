from config import BUFFER_SIZE, CMD_ADD, CMD_DELETE, CMD_LIST, CMD_SEARCH, HOST, PORT
import socket
import sys
import os

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..'))


class DictionaryClient:
    """
    TCP client for the dictionary server.

    Maintains a persistent connection for its lifetime — connect once,
    send as many commands as needed, then close.
    """

    def __init__(self, host: str = HOST, port: int = PORT):
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None

    # ── Connection management ─────────────────────────────────────────────────

    def connect(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self._host, self._port))
        print(f"[Client] Connected to {self._host}:{self._port}")

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None
            print("[Client] Connection closed.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    # ── Public API ────────────────────────────────────────────────────────────

    def search(self, word: str) -> str:
        return self._send(f"{CMD_SEARCH}:{word}")

    def add(self, word: str, definition: str) -> str:
        return self._send(f"{CMD_ADD}:{word}={definition}")

    def delete(self, word: str) -> str:
        return self._send(f"{CMD_DELETE}:{word}")

    def list_words(self) -> list[str]:
        response = self._send(CMD_LIST)
        if response in ("EMPTY", "") or response.startswith("ERROR"):
            return []
        return response.split(',')

    # ── Private ───────────────────────────────────────────────────────────────

    def _send(self, message: str) -> str:
        if not self._sock:
            raise RuntimeError("Not connected. Call connect() first.")
        self._sock.sendall((message + '\n').encode('utf-8'))
        return self._sock.recv(BUFFER_SIZE).decode('utf-8').strip()


# ── Interactive REPL ──────────────────────────────────────────────────────────

def repl(host: str = HOST, port: int = PORT) -> None:
    """
    A simple read-eval-print loop for manual testing from the terminal.

    Commands:
        search <word>
        add <word> <definition>
        delete <word>
        list
        quit
    """
    print("Dictionary Client")
    print("Commands: search <word> | add <word> <definition> | delete <word> | list | quit")
    print("-" * 60)

    try:
        with DictionaryClient(host, port) as client:
            while True:
                try:
                    line = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not line:
                    continue

                parts = line.split(maxsplit=2)
                cmd = parts[0].lower()

                if cmd == 'quit':
                    break

                elif cmd == 'search':
                    if len(parts) < 2:
                        print("Usage: search <word>")
                        continue
                    result = client.search(parts[1])
                    print(f"  {result}")

                elif cmd == 'add':
                    if len(parts) < 3:
                        print("Usage: add <word> <definition>")
                        continue
                    result = client.add(parts[1], parts[2])
                    print(f"  {result}")

                elif cmd == 'delete':
                    if len(parts) < 2:
                        print("Usage: delete <word>")
                        continue
                    result = client.delete(parts[1])
                    print(f"  {result}")

                elif cmd == 'list':
                    words = client.list_words()
                    if not words:
                        print("  (empty)")
                    else:
                        for i, w in enumerate(words, 1):
                            print(f"  {i:>3}. {w}")

                else:
                    print(f"  Unknown command: '{cmd}'")

    except ConnectionRefusedError:
        print(
            f"[Client] Could not connect to {host}:{port} — is the server running?")


if __name__ == "__main__":
    repl()
