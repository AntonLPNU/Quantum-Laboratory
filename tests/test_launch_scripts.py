import unittest
from pathlib import Path


class LaunchScriptTests(unittest.TestCase):
    def test_windows_launcher_builds_frontend_and_starts_local_python_api(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "start_windows.bat").read_text(encoding="utf-8")
        self.assertIn("npm run build", script)
        self.assertIn("scripts\\launch_local.py", script)
        self.assertNotIn("http://127.0.0.1:8501/", script)

    def test_python_launcher_checks_health_and_frontend_before_opening_browser(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "scripts" / "launch_local.py").read_text(encoding="utf-8")
        self.assertIn("create_server(port=0)", script)
        self.assertIn("/api/health", script)
        self.assertIn("webbrowser.open", script)


if __name__ == "__main__":
    unittest.main()
