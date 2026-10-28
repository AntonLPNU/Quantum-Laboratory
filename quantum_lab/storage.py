"""Portable experiment records with reloadable configuration."""
from __future__ import annotations

import csv
import importlib.metadata
import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import __version__


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _flatten(nested, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, np.ndarray):
        # Preserve every grid cell; NumPy's default repr abbreviates large arrays.
        yield prefix, json.dumps(value.tolist(), default=_json_default)
    elif isinstance(value, (list, tuple)):
        yield prefix, json.dumps(value, default=_json_default)
    else:
        yield prefix, value


def save_experiment(results: dict, configuration: dict, directory: str | Path, artifacts: dict | None = None) -> dict[str, Path]:
    """Write a metadata-rich JSON record plus a flattened CSV results table."""
    protocol = configuration.get("protocol", "")
    if protocol == "stage5b_quantum_domino":
        if results.get("status") != "success":
            raise ValueError("failed or incomplete Stage 5B results cannot be saved as a completed experiment")
        if not isinstance(results.get("configuration"), dict) or not isinstance(results.get("scenarios"), dict):
            raise ValueError("Stage 5B results must include saved configuration and scenario results")
        if set(results["scenarios"]) != {"reference", "sender_operation", "positive_control"}:
            raise ValueError("Stage 5B result is missing a required scenario")
        if any(results["scenarios"][name].get("status") != "success" for name in results["scenarios"]):
            raise ValueError("Stage 5B scenario failure cannot be recorded as a completed experiment")
        if "sampling" in results and (not isinstance(configuration.get("preregistration_hash"), str)
                                       or len(configuration["preregistration_hash"]) != 64):
            raise ValueError("confirmatory Stage 5B records require their frozen preregistration hash")
        if not isinstance(configuration.get("sources"), list) or not {f"SRC-{i:03d}" for i in range(20, 27)}.issubset(configuration["sources"]):
            raise ValueError("Stage 5B record must identify source IDs SRC-020 through SRC-026")
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    experiment_id = str(uuid.uuid4())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"experiment_{stamp}_{experiment_id[:8]}"
    packages = {}
    for distribution in ("numpy", "streamlit", "plotly", "kaleido", "matplotlib"):
        try:
            packages[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            packages[distribution] = "not-installed"
    sources = ["SRC-003", "SRC-004", "SRC-006"]
    if "concurrence" in results:
        sources.append("SRC-007")
    if protocol == "chsh":
        sources.append("SRC-001")
    if protocol in ("state_measurement", "rotation_sweep", "signaling_control", "signaling") or configuration.get("angle_a_deg", 0) or configuration.get("angle_b_deg", 0):
        sources.append("SRC-002")
    if protocol == "phase_damping_sweep" or "dephasing_fractions" in results:
        sources.extend(("SRC-001", "SRC-007", "SRC-010", "SRC-013", "SRC-014"))
    method = "exact density-matrix propagation with Kraus maps and Born-rule projective measurement" if protocol == "phase_damping_sweep" or "dephasing_fractions" in results else "exact density-matrix propagation and Born-rule projective measurement"
    precision = "complex128; density-matrix validation tolerance 1e-10; finite-shot uncertainty is reported with the results"
    if protocol == "tfim":
        from .tfim import TFIM_SOURCE_IDS
        sources = list(TFIM_SOURCE_IDS)
        if configuration.get("sources") != sources:
            raise ValueError("TFIM configuration must contain the validated SRC-015..SRC-019 source IDs")
        methods = {
            "spectral": "TFIM spectral unitary propagation by Hermitian eigendecomposition",
            "piecewise_spectral": "TFIM piecewise_spectral unitary propagation with exact schedule boundaries",
            "exponential_midpoint": "TFIM adaptive exponential_midpoint unitary propagation with step doubling",
        }
        selected_method = results.get("diagnostics", {}).get("method")
        if selected_method not in methods:
            raise ValueError("TFIM results must identify a supported propagation method")
        method = methods[selected_method]
        precision = "complex128; state validation atol=1e-10; local solver tolerances and invariant errors are recorded in diagnostics; no independent global convergence comparison"
    if protocol == "stage5b_quantum_domino":
        sources = list(configuration["sources"])
        method = "stage5b dynamic receiver on full A tensor R state; existing Stage 5A adaptive TFIM propagator; exact Born predictions and preregistered independent finite shots"
        precision = "complex128; exact numeric JSON round-trip; local and global solver diagnostics, statistical intervals, random streams, and raw outcomes are recorded"
    record = {
        "schema_version": 1,
        "metadata": {
            "experiment_id": experiment_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "application_version": __version__,
            "code_version": __version__,
            "python_version": platform.python_version(),
            "dependency_versions": packages,
            "method": method,
            "model": results.get("model", "unspecified"),
            "numerical_precision": precision,
            **({"status": results["status"], "error": results.get("error"),
                "preregistration_hash": configuration.get("preregistration_hash"),
                "code_revision": configuration.get("code_provenance", {}).get("git_revision", "unknown"),
                "code_provenance": configuration.get("code_provenance")}
               if protocol == "stage5b_quantum_domino" else {}),
        },
        "configuration": configuration,
        "results": results,
        "artifacts": artifacts or {},
        "sources": sources,
    }
    json_path, csv_path = folder / f"{stem}.json", folder / f"{stem}.csv"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["experiment_id", "field", "value"])
        for field, value in _flatten(results):
            writer.writerow([experiment_id, field, value])
    return {"json": json_path, "csv": csv_path}


def load_configuration(path: str | Path) -> dict:
    """Load only the saved run configuration from an experiment JSON file."""
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("schema_version") != 1 or not isinstance(record.get("configuration"), dict):
        raise ValueError("unsupported experiment record or missing configuration")
    return record["configuration"]
