import socket

from config import (
    BUFFER_SIZE,
    CMD_ADD, CMD_DELETE, CMD_LIST, CMD_SEARCH,
    RESP_ERROR, RESP_NOT_FOUND, RESP_OK, RESP_UNKNOWN,
)
from server.dictionary import Dictionary


class ClientHandler:
    """
    Manages the full lifecycle of one connected client.

    Reads newline-terminated command strings from the socket, dispatches
    them to the Dictionary, and writes responses back — all in a loop
    until the client disconnects or sends an invalid message.

    Intended to run inside its own thread (one per connected client).
    """

    def __init__(self, conn: socket.socket, addr: tuple, dictionary: Dictionary):
        self._conn = conn
        self._addr = addr
        self._dict = dictionary

    # ENTRY POINT

    def handle(self) -> None:
        """Read-dispatch-respond loop. Returns when the client disconnects."""
        print(f"[Handler] Client connected: {self._addr}")
        try:
            while True:
                raw = self._recv()
                if raw is None:           # client closed connection
                    break
                response = self._dispatch(raw)
                self._send(response)
        except OSError as e:
            print(f"[Handler] Socket error for {self._addr}: {e}")
        finally:
            self._conn.close()
            print(f"[Handler] Client disconnected: {self._addr}")

        # PRIVATE NETWORK I/0

    def _recv(self) -> str | None:
        """
        Read up to BUFFER_SIZE bytes and decode to a string.
        Returns None on an empty read (client disconnected).
        """
        try:
            data = self._conn.recv(BUFFER_SIZE)
            if not data:
                return None
            return data.decode('utf-8').strip()
        except OSError:
            return None

    def _send(self, message: str) -> None:
        """Encode and send a response, appending a newline as a delimiter."""
        try:
            self._conn.sendall((message + '\n').encode('utf-8'))
        except OSError as e:
            print(f"[Handler] Failed to send to {self._addr}: {e}")

    # -PRIVATE: command dispatch

    def _dispatch(self, raw: str) -> str:
        """ 
        Parse a raw command string and return the appropriate response.

        Expected formats:
            SEARCH:<word>
            ADD:<word>=<definition>
            DELETE:<word>
            LIST
        """
        if ':' in raw:
            command, _, body = raw.partition(':')
        else:
            command, body = raw, ''

        command = command.upper().strip()

        if command == CMD_SEARCH:
            return self._handle_search(body)
        elif command == CMD_ADD:
            return self._handle_add(body)
        elif command == CMD_DELETE:
            return self._handle_delete(body)
        elif command == CMD_LIST:
            return self._handle_list()
        else:
            print(f"[Handler] Unknown command from {self._addr}: '{command}'")
            return RESP_UNKNOWN

    # - Private: individual command handlers

    def _handle_search(self, body: str) -> str:
        word = body.strip()
        if not word:
            return f"{RESP_ERROR}: SEARCH requires a word"

        definition = self._dict.search(word)
        if definition is None:
            return RESP_NOT_FOUND

        print(f"[Handler] SEARCH '{word}' -> found")
        return definition

    def _handle_add(self, body: str) -> str:
        if '=' not in body:
            return f"{RESP_ERROR}: ADD format is ADD:<word>=<definition>"

        word, _, definition = body.partition('=')
        word = word.strip()
        definition = definition.strip()

        if not word or not definition:
            return f"{RESP_ERROR}: word and definition cannot be blank"

        success = self._dict.add(word, definition)
        if not success:
            return f"{RESP_ERROR}: could not add entry"

        print(f"[Handler] ADD '{word}' -> ok")
        return RESP_OK

    def _handle_delete(self, body: str) -> str:
        word = body.strip()
        if not word:
            return f"{RESP_ERROR}: DELETE requires a word"

        found = self._dict.delete(word)
        if not found:
            return RESP_NOT_FOUND

        print(f"[Handler] DELETE '{word}' -> ok")
        return RESP_OK

    def _handle_list(self) -> str:
        words = self._dict.list_words()
        if not words:
            return "EMPTY"

        print(f"[Handler] LIST -> {len(words)} words")
        return ','.join(words)
