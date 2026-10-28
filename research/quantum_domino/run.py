"""Rerun the locked Quantum Domino protocol through the Stage 5B core."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from quantum_lab.stage5b_experiments import run_stage5b_experiment
from quantum_lab.storage import save_experiment
from quantum_lab.tfim import FieldSchedule


PREREG = Path(__file__).with_name("preregistration.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("research/outputs/quantum_domino"))
    parser.add_argument("--physics-only", action="store_true",
                        help="run exact ensemble dynamics without the preregistered finite-shot sampling")
    args = parser.parse_args()
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg.get("locked") is not True or prereg.get("protocol") != "stage5b-quantum-domino-v1":
        raise ValueError("expected the locked Stage 5B preregistration")
    c, p = prereg["configuration"], prereg["preflight"]
    sigma_x = np.array([[0, 1], [1, 0]], dtype=complex)
    configuration = {
        "n_spins": c["n_spins"], "J": c["J_s_inverse"],
        "h_schedule": FieldSchedule.constant(c["h_s_inverse"]),
        "times_s": c["time_grid_s"],
        "entangled_receiver_site": c["entangled_receiver_site"],
        "sender_kraus_operators": [sigma_x],
        "local_controls": {c["pulse_site"]: FieldSchedule.gaussian(
            p["amplitude_s_inverse"], p["center_s"], p["width_s"])},
        "solver_options": c["solver_options"],
        "primary_observable": {"site": c["primary_receiver_site"], "pauli": "sigma_z"},
    }
    if not args.physics_only:
        configuration["sampling"] = {
            "preregistration": prereg,
            "seed": prereg["seed_policy"]["confirmatory_sampling_seed"],
        }
    result = run_stage5b_experiment(configuration)
    if result["status"] != "success":
        raise RuntimeError(f"Stage 5B failed: {result['error']}")
    metrics = result["metrics"]
    summary = {
        "preregistration_sha256_file_bytes": hashlib.sha256(PREREG.read_bytes()).hexdigest(),
        "status": result["status"],
        "n_spins": int(c["n_spins"]),
        "times_count": len(c["time_grid_s"]),
        "sender_trace_distance_max": float(max(metrics["sender_trace_distance"])),
        "positive_control_trace_distance_max": float(max(metrics["positive_control_trace_distance"])),
        "positive_control_response": metrics["positive_control_response"],
        "sampling_run": not args.physics_only,
    }
    if summary["sender_trace_distance_max"] > 1e-8:
        raise AssertionError("receiver reduced state changed after a local CPTP sender operation")
    if summary["positive_control_trace_distance_max"] <= 1e-4:
        raise AssertionError("local positive control was not distinguishable in the exact calculation")
    if not args.physics_only:
        summary["sampling"] = {
            "probabilities": result["sampling"]["probabilities"],
            "analysis": result["sampling"]["analysis"],
            "statistical_criteria": result["sampling"]["statistical_criteria"],
            "power_preflight": result["sampling"]["power_preflight"],
        }
    args.output.mkdir(parents=True, exist_ok=True)
    paths = save_experiment(result, result["configuration"], args.output)
    (args.output / "checks.json").write_text(json.dumps(summary, default=str, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": {k: v for k, v in summary.items() if k != "sampling"},
                      "record": {k: str(v) for k, v in paths.items()}}, indent=2))


if __name__ == "__main__":
    main()
