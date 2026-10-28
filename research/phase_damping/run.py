"""Reproduce the thesis phase-damping grid using the existing scientific core."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from quantum_lab.experiments import run_phase_damping_sweep
from quantum_lab.storage import save_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("research/outputs/phase_damping"))
    args = parser.parse_args()
    values = np.linspace(0.0, 1.0, 21)
    result = run_phase_damping_sweep("singlet", values_a=values, values_b=values, seed=42)
    if not result["analytic_reference_applies"]:
        raise RuntimeError("unrotated singlet analytic reference is unavailable")

    q = (1.0 - values[:, None]) * (1.0 - values[None, :])
    checks = {
        "grid_points": int(q.size),
        "max_abs_concurrence_minus_q": float(np.max(np.abs(result["concurrence"] - q))),
        "max_abs_chsh_max_minus_analytic": float(np.max(np.abs(result["chsh_maximal"] - 2 * np.sqrt(1 + q*q)))),
        "max_abs_chsh_fixed_minus_analytic": float(np.max(np.abs(result["chsh_fixed"] - 2 * np.sqrt(2) * q))),
        "max_abs_local_B_sigma_z": float(np.max(np.abs(result["local_expectations"]["b"]))),
        "lambda_0_0": {"concurrence": float(result["concurrence"][0, 0]),
                       "chsh_max": float(result["chsh_maximal"][0, 0])},
        "lambda_1_1": {"concurrence": float(result["concurrence"][-1, -1]),
                       "chsh_max": float(result["chsh_maximal"][-1, -1])},
    }
    if max(checks[key] for key in checks if key.startswith("max_abs")) > 1e-12:
        raise AssertionError("phase-damping grid differs from analytic references")
    paths = save_experiment(result, {
        "protocol": "phase_damping_sweep", "state_name": "singlet",
        "values_a": values.tolist(), "values_b": values.tolist(), "seed": 42,
        "reference": "unrotated singlet; exact ensemble quantities, no finite-shot sampling",
    }, args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": checks, "record": {k: str(v) for k, v in paths.items()}}, indent=2))


if __name__ == "__main__":
    main()
