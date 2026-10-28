"""Exercise the bundled backend without Python/Node from the target installation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


def main(executable: Path) -> None:
    """Run the frozen backend through representative authenticated API requests."""
    temp_root = Path(__file__).resolve().parents[1] / ".test-tmp"
    temp_root.mkdir(exist_ok=True)
    token = "a" * 64
    with tempfile.TemporaryDirectory(dir=temp_root) as folder:
        env = dict(os.environ, QUANTUM_LAB_DESKTOP_TOKEN=token,
                   QUANTUM_LAB_DESKTOP_RECORDS=str(Path(folder) / "experiments"))
        process = subprocess.Popen([str(executable)], cwd=executable.parent, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8")
        try:
            ready = process.stdout.readline().strip()
            if not ready.startswith("QL_READY "):
                raise AssertionError(f"backend did not start: {ready}; {process.stderr.read(1024)}")
            port = json.loads(ready.removeprefix("QL_READY "))["port"]
            base = f"http://127.0.0.1:{port}"

            def request(route: str, data: dict | None = None, *, authorized: bool = True):
                headers = {"X-Quantum-Lab-Token": token} if authorized else {}
                if data is not None:
                    headers["Content-Type"] = "application/json"
                req = urllib.request.Request(base + route,
                                             data=json.dumps(data).encode() if data is not None else None,
                                             headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        raw = response.read()
                        return response.status, (json.loads(raw) if route.startswith("/api/") else raw)
                except urllib.error.HTTPError as error:
                    return error.code, json.loads(error.read())

            assert request("/api/health", authorized=False)[0] == 403
            assert request("/")[0] == 200
            assert request("/api/health")[1]["status"] == "ok"
            state = request("/api/state", {"n_spins": 3, "pair": [0, 2], "bell": "singlet"})
            assert state[0] == 200, state
            phase = request("/api/run/phase-damping", {"values_a": [0, 0.5], "values_b": [0, 0.5]})
            assert phase[0] == 200, phase
            chsh = request("/api/run/chsh", {"state_name": "singlet", "shots_per_setting": 64, "seed": 7,
                                                    "dephasing_a": 0.2, "dephasing_b": 0.1})
            assert chsh[0] == 200, chsh
            tfim = request("/api/run/tfim", {
                "n_spins": 2, "J": 1.0, "h_schedule": {"kind": "constant", "parameters": [0.0], "edges_s": [], "values": []},
                "initial_state": [1, 0, 0, 0], "times_s": [0, 0.1], "solver_options": {"save_states_at": [0, 1]},
            })
            assert tfim[0] == 200 and tfim[1]["result"]["results"]["completed"], tfim
            receiver = request("/api/run/stage5b", {
                "n_spins": 3, "J": 100000,
                "h_schedule": {"kind": "constant", "parameters": [200000], "edges_s": [], "values": []},
                "times_s": [0, 0.25e-6, 0.5e-6],
                "local_controls": {"1": {"kind": "constant", "parameters": [6000], "edges_s": [], "values": []}},
                "primary_observable": {"site": 1, "pauli": "sigma_z"},
                "sources": [f"SRC-{i:03d}" for i in range(20, 27)],
            })
            assert receiver[0] == 200, receiver
            spectrum = request("/api/analyze/spectrum", {"times_s": [0, 1e-6, 2e-6, 3e-6, 4e-6, 5e-6],
                                                           "values": [0, 1, 0, -1, 0, 1], "window": "hann"})
            assert spectrum[0] == 200, spectrum
            for route in ("/api/run/hensen-2015", "/api/run/hensen-2016"):
                result = request(route, {})
                assert result[0] == 200, (route, result)
            locked = request("/api/stage5b/locked-result")
            assert locked[0] == 200 and locked[1]["result"]["status"] == "success", locked
            saved = request("/api/experiments/save", {"configuration": {"protocol": "state_measurement"},
                                                        "results": state[1]["result"]})
            assert saved[0] == 200, saved
            name = saved[1]["files"]["json"]
            assert request("/api/experiments/" + name)[0] == 200
            assert request("/api/experiments/csv/" + saved[1]["files"]["csv"])[0] == 200
            assert (Path(folder) / "experiments" / name).is_file()
            print(json.dumps({"status": "PASS", "port": port, "tested": [
                "auth", "offline_ui", "state", "phase_damping", "chsh", "tfim", "dynamic_receiver",
                "deviation_analyzer", "hensen_2015", "hensen_2016", "stage5b_locked",
                "save", "reload", "csv_export"]}))
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            assert process.returncode == 0, f"backend exit code {process.returncode}"


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
