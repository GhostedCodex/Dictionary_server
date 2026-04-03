import socket
import threading
from concurrent.futures import ThreadPoolExecutor, Future

from config import (
    BUFFER_SIZE, HOST, MAX_CONNECTIONS, PORT,
    RESP_BUSY, THREAD_POOL_SIZE,
)
from server.dictionary import Dictionary
from server.handler import ClientHandler


class DictionaryServer:
    """
    Accepts TCP connections and dispatches each one to a ThreadPoolExecutor.

    When the pool is at capacity, the server immediately sends SERVER_BUSY
    and closes the connection rather than queueing the client indefinitely.

    The single Dictionary instance is shared across all handler threads —
    thread safety is handled inside Dictionary itself via a Lock.
    """

    def __init__(self, host: str = HOST, port: int = PORT,
                 pool_size: int = THREAD_POOL_SIZE):
        self._host = host
        self._port = port
        self._pool_size = pool_size
        self._dictionary = Dictionary()
        self._server_sock: socket.socket | None = None
        self._running = False
        self._pool: ThreadPoolExecutor | None = None
        self._active = 0                    # current handlers running
        self._active_lock = threading.Lock()

    # ── Public

    def start(self) -> None:
        """Bind, listen, and block — accepting clients until stopped."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._host, self._port))
        self._server_sock.listen(MAX_CONNECTIONS)
        self._running = True

        with ThreadPoolExecutor(max_workers=self._pool_size,
                                thread_name_prefix='dict-worker') as pool:
            self._pool = pool
            print(f"[Server] Listening on {self._host}:{self._port}")
            print(f"[Server] Pool size: {self._pool_size} workers")
            print(
                f"[Server] Dictionary has {self._dictionary.count()} entries loaded")
            print(f"[Server] Press Ctrl+C to stop\n")

            try:
                while self._running:
                    try:
                        conn, addr = self._server_sock.accept()
                    except OSError:
                        break   # socket was closed by stop()

                    self._dispatch(conn, addr, pool)

            except KeyboardInterrupt:
                print("\n[Server] Keyboard interrupt received.")
            finally:
                self._running = False
                self._pool = None

        self._close_server_socket()
        print(
            f"[Server] Stopped. Dictionary has {self._dictionary.count()} entries.")

    def stop(self) -> None:
        """Signal the accept loop to exit and close the server socket."""
        self._running = False
        self._close_server_socket()

    # ── Private

    def _dispatch(self, conn: socket.socket, addr: tuple,
                  pool: ThreadPoolExecutor) -> None:
        """
        Submit a client to the pool if capacity allows, reject otherwise.

        ThreadPoolExecutor has no built-in way to check if it's full, so we
        track the active handler count ourselves with _active + _active_lock.
        """
        with self._active_lock:
            if self._active >= self._pool_size:
                self._reject(conn, addr)
                return
            self._active += 1

        future: Future = pool.submit(self._handle_client, conn, addr)
        future.add_done_callback(self._on_client_done)
        print(f"[Server] Accepted {addr} "
              f"(active: {self._active}/{self._pool_size})")

    def _reject(self, conn: socket.socket, addr: tuple) -> None:
        """Send SERVER_BUSY and immediately close the connection."""
        print(f"[Server] Pool full — rejecting {addr}")
        try:
            conn.sendall((RESP_BUSY + '\n').encode('utf-8'))
        except OSError:
            pass
        finally:
            conn.close()

    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
        """Target function run inside the pool for each accepted client."""
        handler = ClientHandler(conn, addr, self._dictionary)
        handler.handle()

    def _on_client_done(self, future: Future) -> None:
        """Callback fired by the pool when a handler thread finishes."""
        with self._active_lock:
            self._active -= 1
        if future.exception():
            print(f"[Server] Worker raised an exception: {future.exception()}")

    def _close_server_socket(self) -> None:
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
