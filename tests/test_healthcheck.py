import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from blockclock_backend import healthcheck


class HealthzHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/healthz" else 404)
        self.end_headers()

    def log_message(self, *args):
        pass


class HealthcheckTests(unittest.TestCase):
    def probe_url(self, **env):
        with mock.patch.dict(os.environ, env, clear=True):
            return healthcheck.probe_url()

    def test_defaults_probe_loopback(self):
        self.assertEqual(self.probe_url(), "http://127.0.0.1:8080/healthz")
        self.assertEqual(self.probe_url(HEALTH_HOST=""), "http://127.0.0.1:8080/healthz")

    def test_follows_host_and_port(self):
        self.assertEqual(
            self.probe_url(HEALTH_HOST="127.0.0.1", HEALTH_PORT="18080"),
            "http://127.0.0.1:18080/healthz",
        )
        self.assertEqual(
            self.probe_url(HEALTH_HOST="192.0.2.10", HEALTH_PORT="9000"),
            "http://192.0.2.10:9000/healthz",
        )

    def test_ipv6_hosts(self):
        self.assertEqual(self.probe_url(HEALTH_HOST="::"), "http://[::1]:8080/healthz")
        self.assertEqual(self.probe_url(HEALTH_HOST="::1"), "http://[::1]:8080/healthz")

    def test_disabled_health_port(self):
        self.assertIsNone(self.probe_url(HEALTH_PORT="0"))
        self.assertIsNone(self.probe_url(HEALTH_PORT=""))
        for port in ("0", ""):
            with self.subTest(port=port), mock.patch.dict(
                os.environ, {"HEALTH_PORT": port}, clear=True
            ), mock.patch("socket.create_connection") as connect:
                self.assertEqual(healthcheck.main(), 0)
                connect.assert_not_called()

    def test_main_checks_endpoint(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), HealthzHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            with mock.patch.dict(
                os.environ, {"HEALTH_HOST": "127.0.0.1", "HEALTH_PORT": str(port)}, clear=True
            ):
                self.assertEqual(healthcheck.main(), 0)
                with mock.patch.object(
                    healthcheck, "probe_url", return_value=f"http://127.0.0.1:{port}/missing"
                ):
                    self.assertEqual(healthcheck.main(), 1)
                with mock.patch.dict(
                    os.environ, {"http_proxy": f"http://127.0.0.1:{port}", "no_proxy": ""}
                ), mock.patch("urllib.request.proxy_bypass", return_value=False), mock.patch(
                    "urllib.request._opener", None
                ):
                    self.assertEqual(healthcheck.main(), 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        with mock.patch.dict(
            os.environ, {"HEALTH_HOST": "127.0.0.1", "HEALTH_PORT": str(port)}, clear=True
        ):
            self.assertEqual(healthcheck.main(), 1)


if __name__ == "__main__":
    unittest.main()
