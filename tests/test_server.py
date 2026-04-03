from server.server import DictionaryServer
from server.handler import ClientHandler
from server.dictionary import Dictionary
import os
import sys
import json
import socket
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..'))


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_dictionary(entries: dict = None) -> tuple[Dictionary, str]:
    """Create a Dictionary backed by a temp file, optionally pre-populated."""
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(entries or {}, tmp)
    tmp.close()
    return Dictionary(filepath=tmp.name), tmp.name


def handler_exchange(command: str, dictionary: Dictionary) -> str:
    """
    Send one command through a real ClientHandler via socketpair.
    Returns the stripped response string.
    """
    server_sock, client_sock = socket.socketpair()
    handler = ClientHandler(server_sock, ('test', 0), dictionary)
    t = threading.Thread(target=handler.handle, daemon=True)
    t.start()
    client_sock.sendall((command + '\n').encode())
    response = client_sock.recv(4096).decode().strip()
    client_sock.close()
    t.join(timeout=2)
    return response


# ── Handler tests ─────────────────────────────────────────────────────────────

class TestClientHandlerSearch(unittest.TestCase):

    def setUp(self):
        self.d, self.path = make_dictionary({"cat": "a feline animal"})

    def tearDown(self):
        os.unlink(self.path)

    def test_search_found(self):
        self.assertIn("feline", handler_exchange("SEARCH:cat", self.d))

    def test_search_not_found(self):
        self.assertEqual(handler_exchange("SEARCH:dog", self.d), "NOT_FOUND")

    def test_search_case_insensitive_command(self):
        self.assertIn("feline", handler_exchange("search:cat", self.d))

    def test_search_no_argument(self):
        self.assertIn("ERROR", handler_exchange("SEARCH:", self.d))

    def test_search_case_insensitive_word(self):
        self.assertIn("feline", handler_exchange("SEARCH:CAT", self.d))


class TestClientHandlerAdd(unittest.TestCase):

    def setUp(self):
        self.d, self.path = make_dictionary()

    def tearDown(self):
        os.unlink(self.path)

    def test_add_valid(self):
        self.assertEqual(handler_exchange(
            "ADD:dog=a loyal animal", self.d), "OK")

    def test_add_then_search(self):
        handler_exchange("ADD:dog=a loyal animal", self.d)
        self.assertIn("loyal", handler_exchange("SEARCH:dog", self.d))

    def test_add_missing_equals(self):
        self.assertIn("ERROR", handler_exchange("ADD:badformat", self.d))

    def test_add_blank_word(self):
        self.assertIn("ERROR", handler_exchange(
            "ADD:=some definition", self.d))

    def test_add_blank_definition(self):
        self.assertIn("ERROR", handler_exchange("ADD:word=", self.d))


class TestClientHandlerDelete(unittest.TestCase):

    def setUp(self):
        self.d, self.path = make_dictionary({"cat": "a feline animal"})

    def tearDown(self):
        os.unlink(self.path)

    def test_delete_existing(self):
        self.assertEqual(handler_exchange("DELETE:cat", self.d), "OK")

    def test_delete_missing(self):
        self.assertEqual(handler_exchange("DELETE:dog", self.d), "NOT_FOUND")

    def test_delete_no_argument(self):
        self.assertIn("ERROR", handler_exchange("DELETE:", self.d))

    def test_delete_then_search(self):
        handler_exchange("DELETE:cat", self.d)
        self.assertEqual(handler_exchange("SEARCH:cat", self.d), "NOT_FOUND")


class TestClientHandlerList(unittest.TestCase):

    def setUp(self):
        self.d, self.path = make_dictionary({"cat": "feline", "dog": "canine"})

    def tearDown(self):
        os.unlink(self.path)

    def test_list_returns_words(self):
        response = handler_exchange("LIST", self.d)
        self.assertIn("cat", response)
        self.assertIn("dog", response)

    def test_list_empty_dictionary(self):
        d, path = make_dictionary()
        try:
            self.assertEqual(handler_exchange("LIST", d), "EMPTY")
        finally:
            os.unlink(path)

    def test_unknown_command(self):
        self.assertEqual(handler_exchange(
            "JUMP:something", self.d), "UNKNOWN_COMMAND")


# ── Server integration tests ──────────────────────────────────────────────────

class TestDictionaryServerIntegration(unittest.TestCase):
    """
    Spin up a real server on a free port, connect real clients,
    verify end-to-end behaviour.
    """

    PORT = 15100

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False)
        json.dump({"hello": "a greeting"}, self.tmp)
        self.tmp.close()

        self.server = DictionaryServer(host='127.0.0.1', port=self.PORT)
        self.server._dictionary = Dictionary(filepath=self.tmp.name)

        self.server_thread = threading.Thread(
            target=self.server.start, daemon=True)
        self.server_thread.start()
        time.sleep(0.2)

    def tearDown(self):
        self.server.stop()
        os.unlink(self.tmp.name)
        TestDictionaryServerIntegration.PORT += 1   # avoid port reuse issues

    def _client_send(self, command: str) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.PORT))
        s.sendall((command + '\n').encode())
        response = s.recv(4096).decode().strip()
        s.close()
        return response

    def test_search_via_network(self):
        self.assertIn("greeting", self._client_send("SEARCH:hello"))

    def test_add_then_search_via_network(self):
        self.assertEqual(self._client_send(
            "ADD:bird=a feathered creature"), "OK")
        self.assertIn("feathered", self._client_send("SEARCH:bird"))

    def test_multiple_concurrent_clients(self):
        results = {}
        lock = threading.Lock()

        def session(name, cmd):
            response = self._client_send(cmd)
            with lock:
                results[name] = response

        threads = [
            threading.Thread(target=session, args=(f"c{i}", "SEARCH:hello"))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 10)
        for name, resp in results.items():
            self.assertIn("greeting", resp,
                          f"{name} got unexpected response: {resp}")

    def test_server_handles_client_disconnect_gracefully(self):
        """Abruptly closing a client socket should not crash the server."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.PORT))
        s.close()   # disconnect immediately without sending anything
        time.sleep(0.1)

        # Server should still respond to a new client
        self.assertIn("greeting", self._client_send("SEARCH:hello"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
