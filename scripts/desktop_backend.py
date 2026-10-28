"""Private loopback backend launched and owned by Quantum Laboratory Desktop."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quantum_lab.http_api import ROOT, create_server


def main() -> int:
    """Serve the bundled UI and science API until the owning desktop process exits."""
    token = os.environ.get("QUANTUM_LAB_DESKTOP_TOKEN", "")
    records = os.environ.get("QUANTUM_LAB_DESKTOP_RECORDS", "")
    if len(token) < 32 or not records:
        print("QL_ERROR desktop authentication or data directory is missing", flush=True)
        return 2
    records_dir = Path(records).resolve()
    records_dir.mkdir(parents=True, exist_ok=True)
    server = create_server(port=0, auth_token=token, records_dir=records_dir,
                           static_dir=ROOT / "frontend" / "dist")

    def stop_on_parent_exit() -> None:
        # Electron owns the write end. EOF also handles an unexpected parent exit.
        sys.stdin.buffer.read()
        server.shutdown()

    threading.Thread(target=stop_on_parent_exit, name="parent-watch", daemon=True).start()
    print("QL_READY " + json.dumps({"port": server.server_address[1]}), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
