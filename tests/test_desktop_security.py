"""Desktop transport checks; no scientific model changes are involved."""
import http.client
import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from quantum_lab.http_api import create_server


class DesktopSecurityTests(unittest.TestCase):
    def test_private_server_requires_token_for_static_and_scientific_routes(self):
        token = "t" * 64
        test_tmp = Path(__file__).resolve().parents[1] / ".test-tmp"
        test_tmp.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=test_tmp) as folder:
            static_dir = Path(folder) / "static"
            static_dir.mkdir()
            (static_dir / "index.html").write_text("<html>offline</html>", encoding="utf-8")
            server = create_server(port=0, auth_token=token, records_dir=Path(folder) / "records",
                                   static_dir=static_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                for method, route in (("GET", "/"), ("GET", "/api/health"), ("POST", "/api/state")):
                    self.assertEqual(self._get(port, method, route, {})[0], 403)
                headers = {"X-Quantum-Lab-Token": token}
                self.assertEqual(self._get(port, "GET", "/", headers)[0], 200)
                status, body = self._get(port, "GET", "/api/health", headers)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["status"], "ok")
                self.assertEqual(self._get(port, "GET", "/api/health", {
                    **headers, "Origin": "https://example.invalid"})[0], 403)
                status, body = self._get(port, "POST", "/api/state", headers,
                                         json.dumps({"n_spins": 2, "pair": [0, 1]}))
                self.assertEqual(status, 200, body)
                self.assertTrue((Path(folder) / "records").exists() is False)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    @staticmethod
    def _get(port, method, path, headers, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()

    def test_short_token_is_rejected(self):
        with self.assertRaises(ValueError):
            create_server(port=0, auth_token="short")


if __name__ == "__main__":
    unittest.main()
