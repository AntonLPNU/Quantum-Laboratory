"""Start the loopback API on a free port, verify it, then open the browser."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum_lab.http_api import create_server  # noqa: E402


def _log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, flush=True)
    log_path = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "QuantumLaboratory" / "startup.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
    except OSError:
        print("Startup log could not be written; continuing with console diagnostics.", flush=True)


def _wait_until_ready(base_url: str) -> None:
    last_error: Exception | None = None
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=1.5) as response:
                health = json.loads(response.read().decode("utf-8"))
                if response.status != 200 or health.get("status") != "ok":
                    raise RuntimeError("Python API health check returned an invalid response")
            with urllib.request.urlopen(base_url, timeout=1.5) as response:
                page = response.read(512).decode("utf-8", errors="replace")
                if response.status != 200 or "<html" not in page.lower():
                    raise RuntimeError("Orbital Lab frontend did not return an HTML page")
            return
        except (OSError, ValueError, urllib.error.URLError, RuntimeError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Local API/frontend did not become ready: {last_error}")


def main(open_browser: bool = True) -> int:
    """Запустити локальний API на вільному loopback-порту, перевірити готовність і відкрити UI."""
    index = ROOT / "frontend" / "dist" / "index.html"
    if not index.is_file():
        _log(f"ERROR frontend build is missing: {index}; run start_windows.bat again")
        return 1

    server = create_server(port=0)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/"
    thread = threading.Thread(target=server.serve_forever, name="quantum-laboratory-api", daemon=True)
    thread.start()
    try:
        _wait_until_ready(url)
        _log(f"Ready: {url}; the port was selected by the operating system and no existing listener was stopped.")
        opened = webbrowser.open(url, new=2) if open_browser else False
        if not opened and open_browser:
            _log(f"The default browser did not open automatically. Open this URL manually: {url}")
        elif not open_browser:
            _log(f"Browser opening disabled for this run. Open this URL manually: {url}")
        thread.join()
        return 0
    except KeyboardInterrupt:
        _log("Stopping the Quantum Laboratory server.")
        return 0
    except Exception as exc:
        _log(f"ERROR {type(exc).__name__}: {exc}")
        return 1
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="keep the server running without opening a browser")
    arguments = parser.parse_args()
    raise SystemExit(main(open_browser=not arguments.no_browser))
