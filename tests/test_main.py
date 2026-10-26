import os
import signal
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipIf(sys.platform == "win32", "SIGTERM handling needs a Unix event loop")
class MainTests(unittest.TestCase):
    def test_sigterm_stops_with_open_connection(self):
        port = free_port()
        env = dict(
            os.environ,
            BITCOIN_SOURCE="mock",
            BLOCKCLOCK_HOST="127.0.0.1",
            BLOCKCLOCK_PORT=str(port),
            HEALTH_PORT="0",
            BITCOIN_PRICE_USD="60000",
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "blockclock_backend"],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    client = socket.create_connection(("127.0.0.1", port), timeout=1)
                    break
                except OSError:
                    if time.monotonic() > deadline or process.poll() is not None:
                        raise
                    time.sleep(0.1)
            with client:
                self.assertTrue(client.recv(1))
                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
