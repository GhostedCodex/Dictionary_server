from config import HOST, PORT
from server.server import DictionaryServer
import sys
import os
import socket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_local_ip() -> str:
    """Return the machine's LAN IP — the address other devices use to connect."""
    try:
        # Connect to an external address (doesn't send data) to find the
        # outbound interface IP. Works correctly even with multiple NICs.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "unknown — check your network settings"


def main():
    local_ip = get_local_ip()

    print("=" * 52)
    print("  Dictionary Server")
    print("=" * 52)
    print(f"  Listening on     : {HOST}:{PORT}")
    print(f"  Your LAN IP      : {local_ip}")
    print()
    print("  Other devices connect using:")
    print(f"    TCP client  →  {local_ip}:{PORT}")
    print(f"    Web browser →  http://{local_ip}:8080")
    print()
    print("  Make sure port 5000 and 8080 are allowed")
    print("  through your firewall / Windows Defender.")
    print("=" * 52)
    print()

    server = DictionaryServer(host=HOST, port=PORT)
    try:
        server.start()
    except Exception as e:
        print(f"[Main] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
