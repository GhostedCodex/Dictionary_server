from config import HOST, PORT
from server.server import DictionaryServer
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    server = DictionaryServer(host=HOST, port=PORT)
    try:
        server.start()
    except Exception as e:
        print(f"[Main] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
