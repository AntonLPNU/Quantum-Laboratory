"""Loopback-only HTTP adapter for the existing Quantum Laboratory core."""
from __future__ import annotations

import json
import math
import mimetypes
import os
import sys
import hmac
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from typing import Any
from urllib.parse import unquote

import numpy as np

from . import __version__
from .experiments import (run_chsh_experiment, run_phase_damping_sweep,
                          run_signaling_experiment, run_state_experiment,
                          run_tfim_experiment)
from .multispin import (apply_subsystem_unitary, embed_operator, expectation_value,
                        density_matrix_from_ket, partial_trace_subsystems,
                        prepare_bell_pair_state)
from .operations import local_rotation
from .stage5b_experiments import run_stage5b_experiment, save_stage5b_experiment
from .storage import save_experiment
from .tfim import FieldSchedule

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DEFAULT_RECORDS = ROOT / "results" / "ui_experiments"
HENSEN_2015 = ROOT / "data" / "references" / "hensen_2015" / "original_files" / "bell_open_data.txt"
HENSEN_2016 = ROOT / "data" / "references" / "hensen_2016" / "original_files"
# Exact, replayable multispin results can include dense saved-state trajectories.
# Keep a bounded request size while leaving room for those full experiment records.
MAX_REQUEST_BYTES = 64 * 1024 * 1024
# This is a local, single-user application. Serializing POST work keeps the
# bounded TFIM snapshot/JSON allocations from multiplying across concurrent
# browser tabs or repeated API calls.
_POST_REQUEST_SLOTS = BoundedSemaphore(1)

FEATURES = {
    "registers": {"available": True, "kind": "state_preparation", "detail": "2–6 спінів; Беллівська пара й локальні операції з core API"},
    "density_matrices": {"available": True, "kind": "exact_prediction", "detail": "матриці густини, редукції та Bloch-вектори з Python core"},
    "measurements": {"available": True, "kind": "sampled_measurement_and_exact_prediction", "detail": "two-spin projective measurements; seed and shots are recorded"},
    "chsh": {"available": True, "kind": "sampled_measurement_and_exact_prediction", "detail": "fixed axes and optimized CHSH are reported separately"},
    "phase_damping": {"available": True, "kind": "exact_prediction", "detail": "independent λA/λB grids from complete ρAB"},
    "tfim": {"available": True, "kind": "numerical_evolution", "detail": "2–6 spins; seconds and angular frequencies in s⁻¹"},
    "dynamic_receiver": {"available": True, "kind": "exact_prediction", "detail": "Stage 5B A⊗R evolution and receiver-local summaries"},
    "quantum_domino": {"available": True, "kind": "exact_prediction", "detail": "Stage 5B reference, sender operation, positive control; sampling requires the registered protocol"},
    "deviation_analyzer": {"available": True, "kind": "analysis", "detail": "exact summaries and registered sampling are exposed through Stage 5B"},
    "no_signaling": {"available": True, "kind": "conditional_statistical_test", "detail": "receiver-only output; finite-sample interpretation and criteria remain in core"},
    "hensen_2015": {"available": HENSEN_2015.is_file(), "kind": "published_data_reanalysis", "detail": "requires separately obtained hash-checked 2015 source data; not apparatus simulation"},
    "hensen_2016": {"available": all((HENSEN_2016 / name).is_file() for name in ("bell_open_data_2_old_detector.txt", "bell_open_data_2_new_detector.txt")), "kind": "published_data_reanalysis", "detail": "requires separate old/new detector source files and hash checks"},
    "hensen_comparison": {"available": HENSEN_2015.is_file() and all((HENSEN_2016 / name).is_file() for name in ("bell_open_data_2_old_detector.txt", "bell_open_data_2_new_detector.txt")), "kind": "separate_published_data_reanalyses", "detail": "keeps 2015 and 2016 separate and uses the existing documented weighted summary"},
    "experiment_records": {"available": True, "kind": "reproducible_record", "detail": "JSON/CSV records in the application results directory"},
    "experiment_comparison": {"available": True, "kind": "descriptive_record_comparison", "detail": "compares saved configuration metadata and shared finite scalar result paths; no physics is rerun and no statistical test is inferred"},
}


class ApiError(ValueError):
    """Структурована помилка API з кодом і HTTP-статусом для клієнта."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist())
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, FieldSchedule):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")


def _complex(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"real", "imag"}:
        return complex(float(value["real"]), float(value["imag"]))
    if isinstance(value, list):
        return [_complex(item) for item in value]
    return value


def _schedule(value: Any) -> FieldSchedule:
    if not isinstance(value, dict):
        raise ApiError("invalid_schedule", "h_schedule must be a schedule object")
    try:
        return FieldSchedule.from_dict(value)
    except (TypeError, ValueError, KeyError) as exc:
        raise ApiError("invalid_schedule", str(exc)) from exc


def _records_dir(value: str | Path | None) -> Path:
    folder = Path(value) if value is not None else DEFAULT_RECORDS
    return folder.resolve()


def _record_path(name: str, records_dir: Path) -> Path:
    basename = unquote(name)
    if not basename or basename in {".", ".."} or Path(basename).name != basename or "/" in basename or "\\" in basename:
        raise ApiError("invalid_record_name", "record must be identified by a file basename")
    path = (records_dir / basename).resolve()
    if path.parent != records_dir or path.suffix not in {".json", ".csv"}:
        raise ApiError("invalid_record_name", "record path is outside the experiment directory")
    return path


def _numeric_result_leaves(value: Any, prefix: str = "results") -> dict[str, float]:
    """Collect finite scalar values only; arrays and complex encodings are not metrics."""
    leaves: dict[str, float] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            leaves.update(_numeric_result_leaves(item, f"{prefix}.{key}"))
    elif isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_)):
        numeric = float(value)
        if math.isfinite(numeric):
            leaves[prefix] = numeric
    return leaves


def _load_saved_record(name: str, records_dir: Path) -> dict[str, Any]:
    record_path = _record_path(name, records_dir)
    if record_path.suffix != ".json" or not record_path.is_file():
        raise ApiError("record_not_found", "experiment JSON record was not found", 404)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ApiError("invalid_record", "experiment JSON record must contain an object", 422)
    return record


def _result(result: Any, kind: str, route: str, configuration: dict | None = None) -> dict:
    return {"kind": kind, "route": route, "provenance": {"engine": "quantum_lab Python scientific core", "application_version": __version__},
            "configuration": _json_value(configuration or {}), "result": _json_value(result)}


def _spin_observables(rho: np.ndarray) -> list[dict[str, Any]]:
    paulis = {
        "x": np.array([[0, 1], [1, 0]], dtype=complex),
        "y": np.array([[0, -1j], [1j, 0]], dtype=complex),
        "z": np.array([[1, 0], [0, -1]], dtype=complex),
    }
    return [{"site": site, "bloch": {axis: float(expectation_value(rho, operator, [site]).real)
                                        for axis, operator in paulis.items()}}
            for site in range(int(round(np.log2(rho.shape[0]))))]


def dispatch(method: str, path: str, payload: dict | None = None, *, records_dir: str | Path | None = None) -> tuple[int, dict]:
    """Dispatch a JSON API request. Separated from HTTP transport for tests."""
    data = payload or {}
    if not isinstance(data, dict):
        return 400, {"error": {"code": "invalid_json_object", "message": "request body must be a JSON object"}}
    records = _records_dir(records_dir)
    try:
        if method == "GET" and path == "/api/health":
            return 200, {"status": "ok", "application": "Quantum Laboratory", "version": __version__}
        if method == "GET" and path == "/api/capabilities":
            return 200, {"features": FEATURES, "api_version": 1}
        if path.startswith("/api/run/") and method != "POST":
            return 405, {"error": {"code": "method_not_allowed", "message": "scientific run routes require POST"}}
        if path.startswith("/api/") and method not in {"GET", "POST"}:
            return 405, {"error": {"code": "method_not_allowed", "message": "method is not supported"}}

        if method == "POST" and path == "/api/state":
            n = data.get("n_spins", 2)
            pair = data.get("pair", [0, 1])
            state = prepare_bell_pair_state(n, pair, data.get("bell", "singlet"), data.get("spectator_kets"))
            rho = density_matrix_from_ket(state) if state.ndim == 1 else state
            return 200, _result({"density_matrix": rho, "n_spins": n, "pair": pair,
                                 "spin_observables": _spin_observables(rho)}, "exact_state", path, data)
        if method == "POST" and path == "/api/state/operation":
            rho = np.asarray(_complex(data.get("density_matrix")), dtype=complex)
            site = data.get("site")
            axis = data.get("axis", [0, 0, 1])
            angle = float(data.get("angle_rad", 0.0))
            unitary = local_rotation(axis, angle)
            result = apply_subsystem_unitary(rho, unitary, [site])
            return 200, _result({"density_matrix": result}, "exact_state", path, data)
        if method == "POST" and path == "/api/state/reduce":
            rho = np.asarray(_complex(data.get("density_matrix")), dtype=complex)
            keep = data.get("keep", [])
            reduced = partial_trace_subsystems(rho, keep)
            return 200, _result({"reduced_density_matrix": reduced, "keep_order": keep}, "exact_reduced_state", path, data)
        if method == "POST" and path == "/api/state/inspect":
            rho = np.asarray(_complex(data.get("density_matrix")), dtype=complex)
            return 200, _result({"n_spins": int(round(np.log2(rho.shape[0]))),
                                 "spin_observables": _spin_observables(rho)}, "exact_state_summary", path, data)
        if method == "POST" and path == "/api/analyze/observable":
            from .deviation import exact_observable_summary, sample_observable
            from .tfim import local_pauli
            rho = np.asarray(_complex(data.get("density_matrix")), dtype=complex)
            n_spins = int(round(np.log2(rho.shape[0])))
            site = data.get("site", 0)
            pauli = data.get("pauli", "sigma_z")
            if pauli not in {"sigma_x", "sigma_y", "sigma_z"}:
                raise ApiError("invalid_observable", "pauli must be sigma_x, sigma_y, or sigma_z")
            operator = local_pauli(n_spins, site, pauli[-1])
            result = {"exact": exact_observable_summary(rho, operator)}
            if "shots" in data:
                result["sample"] = sample_observable(rho, operator, data["shots"], np.random.default_rng(data.get("seed", 42)))
                result["seed"] = data.get("seed", 42)
            return 200, _result(result, "exact_prediction_and_optional_independent_sample", path, data)
        if method == "POST" and path == "/api/analyze/spectrum":
            from .deviation import spectrum_uniform_grid
            result = spectrum_uniform_grid(data.get("times_s", []), data.get("values", []), data.get("window", "hann"))
            return 200, _result(result, "time_series_analysis", path, data)
        if method == "POST" and path == "/api/analyze/sinusoid":
            from .deviation import fit_explicit_model
            result = fit_explicit_model(data.get("times_s", []), data.get("values", []), data.get("model", "sinusoid"), data.get("initial_parameters", {}))
            return 200, _result(result, "explicit_model_fit", path, data)
        if method == "POST" and path == "/api/analyze/sequential":
            from .deviation import sequential_measurement_distribution, sample_sequential_measurements
            from .tfim import local_pauli, open_tfim_hamiltonian, unitary_from_hermitian
            rho = np.asarray(_complex(data.get("state_at_t1")), dtype=complex)
            n_spins = int(round(np.log2(rho.shape[0])))
            site_1, site_2 = data.get("site_1", 0), data.get("site_2", 0)
            axis_1, axis_2 = data.get("pauli_1", "sigma_z"), data.get("pauli_2", "sigma_z")
            op1 = local_pauli(n_spins, site_1, axis_1[-1])
            op2 = local_pauli(n_spins, site_2, axis_2[-1])
            if data.get("propagator_t1_t2") is not None:
                propagator = np.asarray(_complex(data["propagator_t1_t2"]), dtype=complex)
                propagator_model = "provided_unitary"
            else:
                elapsed_s = data.get("delta_time_s")
                if elapsed_s is None:
                    raise ValueError("provide propagator_t1_t2 or delta_time_s with static TFIM parameters")
                propagator = unitary_from_hermitian(
                    open_tfim_hamiltonian(n_spins, data.get("J"), data.get("h")), elapsed_s)
                propagator_model = "static_open_tfim"
            exact = sequential_measurement_distribution(rho, op1, propagator, op2)
            result = {"exact": exact, "back_action": "Lüders projection after first measurement", "observations_are_paired": True,
                      "propagator_model": propagator_model}
            if "shots" in data:
                result["sample"] = sample_sequential_measurements(rho, op1, propagator, op2, data["shots"], np.random.default_rng(data.get("seed", 42)))
                result["seed"] = data.get("seed", 42)
            return 200, _result(result, "sequential_measurements_with_back_action", path, data)
        if method == "GET" and path == "/api/stage5b/locked-result":
            report_dir = ROOT / "results" / "stage5b" / "experiment"
            records = sorted(report_dir.glob("*.json")) if report_dir.is_dir() else []
            if not records:
                raise ApiError("record_not_found", "No saved Stage 5B confirmatory report is available", 404)
            record = json.loads(records[-1].read_text(encoding="utf-8"))
            saved_results = record.get("results", {})
            sampling = saved_results.get("sampling", {})
            result = {
                "record_name": records[-1].name,
                "status": saved_results.get("status"),
                "metrics": saved_results.get("metrics"),
                "sampling_status": sampling.get("status"),
                "sampling_analysis": sampling.get("analysis"),
                "statistical_criteria": sampling.get("statistical_criteria"),
                "power_preflight": sampling.get("power_preflight"),
                "positive_control_preflight": sampling.get("positive_control_preflight"),
                "preregistration_hash": sampling.get("preregistration_hash", record.get("configuration", {}).get("preregistration_hash")),
                "interpretation": "Previously saved preregistered sample; this read-only view does not rerun sampling.",
            }
            return 200, _result(result, "saved_stage5b_confirmatory_analysis", path, record.get("configuration", {}))
        if method == "POST" and path == "/api/run/state":
            result = run_state_experiment(state_name=data.get("state_name", "singlet"), rotations=data.get("rotations"),
                                          axis_a=data.get("axis_a", [0, 0, 1]), axis_b=data.get("axis_b", [0, 0, 1]),
                                          shots=data.get("shots", 2000), seed=data.get("seed", 42),
                                          dephasing_a=data.get("dephasing_a", 0), dephasing_b=data.get("dephasing_b", 0))
            return 200, _result(result, "sampled_measurement_and_exact_prediction", path, data)
        if method == "POST" and path == "/api/run/chsh":
            result = run_chsh_experiment(state_name=data.get("state_name", "singlet"), shots_per_setting=data.get("shots_per_setting", 2000),
                                         seed=data.get("seed", 42), dephasing_a=data.get("dephasing_a", 0),
                                         dephasing_b=data.get("dephasing_b", 0), rotations=data.get("rotations"))
            return 200, _result(result, "sampled_measurement_and_exact_prediction", path, data)
        if method == "POST" and path == "/api/run/signaling":
            result = run_signaling_experiment(shots=data.get("shots", 1000), seed=data.get("seed", 42),
                                               receiver_axis=data.get("receiver_axis", [0, 0, 1]),
                                               sender_dephasing=data.get("sender_dephasing", 0),
                                               receiver_dephasing=data.get("receiver_dephasing", 0))
            return 200, _result(result, "receiver_only_sampled_no_signaling_test", path, data)
        if method == "POST" and path == "/api/run/phase-damping":
            result = run_phase_damping_sweep(state_name=data.get("state_name", "singlet"), values_a=data.get("values_a"),
                                             values_b=data.get("values_b"), axis_a=data.get("axis_a", [0, 0, 1]),
                                             axis_b=data.get("axis_b", [0, 0, 1]), seed=data.get("seed", 42), rotations=data.get("rotations"))
            return 200, _result(result, "exact_prediction", path, data)
        if method == "POST" and path == "/api/run/tfim":
            config = dict(data)
            config["h_schedule"] = _schedule(data.get("h_schedule"))
            config["initial_state"] = _complex(data.get("initial_state"))
            output = run_tfim_experiment(config.get("n_spins"), config.get("J"), config["h_schedule"],
                                         config.get("initial_state"), config.get("times_s"),
                                         seed=config.get("seed"), solver_options=config.get("solver_options"))
            return 200, _result(output, "numerical_evolution", path, data)
        if method == "POST" and path in {"/api/run/dynamic-receiver", "/api/run/stage5b"}:
            config = dict(data)
            config["h_schedule"] = _schedule(data.get("h_schedule"))
            if isinstance(data.get("local_controls"), dict):
                config["local_controls"] = {int(k): _schedule(v) for k, v in data["local_controls"].items()}
            if config.get("initial_state") is not None:
                config["initial_state"] = _complex(config["initial_state"])
            if path.endswith("stage5b"):
                output = run_stage5b_experiment(config)
                kind = "stage5b_analysis"
            else:
                from .dynamic_receiver import run_dynamic_receiver_experiment
                output = run_dynamic_receiver_experiment(config)
                kind = "dynamic_receiver_prediction"
            return 200, _result(output, kind, path, data)
        if method == "POST" and path == "/api/run/hensen-2015":
            if not HENSEN_2015.is_file():
                raise ApiError("source_data_missing", "Hensen 2015 source data are not included; obtain the original dataset and verify its SHA-256 using docs/source-register.md", 404)
            from .scientific_validation import analyze_hensen_2015, assess_hensen_2015_reproduction
            output = analyze_hensen_2015(HENSEN_2015)
            output["reproduction_status"] = assess_hensen_2015_reproduction(output)
            output.pop("trial_records", None)
            output.pop("trials", None)
            return 200, _result(output, "published_data_reanalysis", path, {"source": "fixed hash-checked Hensen 2015 dataset"})
        if method == "POST" and path == "/api/run/hensen-2016":
            required = (HENSEN_2016 / "bell_open_data_2_old_detector.txt", HENSEN_2016 / "bell_open_data_2_new_detector.txt")
            if not all(path.is_file() for path in required):
                raise ApiError("source_data_missing", "Hensen 2016 old/new detector files are not included; obtain the original dataset and verify its SHA-256 using docs/source-register.md", 404)
            from .scientific_validation import analyze_hensen_2016, assess_hensen_2016_reproduction
            output = analyze_hensen_2016(HENSEN_2016 / "bell_open_data_2_old_detector.txt",
                                         HENSEN_2016 / "bell_open_data_2_new_detector.txt")
            output["reproduction_status"] = assess_hensen_2016_reproduction(output)
            output.pop("trials", None)
            return 200, _result(output, "published_data_reanalysis", path,
                                {"sources": ["Hensen 2016 old detector", "Hensen 2016 new detector"]})
        if method == "POST" and path == "/api/run/hensen-compare":
            required = (HENSEN_2015, HENSEN_2016 / "bell_open_data_2_old_detector.txt", HENSEN_2016 / "bell_open_data_2_new_detector.txt")
            if not all(path.is_file() for path in required):
                raise ApiError("source_data_missing", "Hensen 2015 and 2016 source files are required for separate comparison; obtain and hash-check them using docs/source-register.md", 404)
            from .scientific_validation import (analyze_hensen_2015, analyze_hensen_2016,
                                                assess_hensen_2015_reproduction, assess_hensen_2016_reproduction,
                                                combine_hensen_results)
            result_2015 = analyze_hensen_2015(HENSEN_2015)
            result_2016 = analyze_hensen_2016(HENSEN_2016 / "bell_open_data_2_old_detector.txt",
                                              HENSEN_2016 / "bell_open_data_2_new_detector.txt")
            result_2015["reproduction_status"] = assess_hensen_2015_reproduction(result_2015)
            result_2016["reproduction_status"] = assess_hensen_2016_reproduction(result_2016)
            result_2015.pop("trials", None)
            result_2016.pop("trials", None)
            output = {"hensen_2015": result_2015, "hensen_2016": result_2016,
                      "combined_summary": combine_hensen_results(result_2015, result_2016),
                      "interpretation": "Separate year-specific source analyses; combined summary is not apparatus validation."}
            return 200, _result(output, "separate_published_data_reanalyses", path,
                                {"sources": ["Hensen 2015 source", "Hensen 2016 old detector", "Hensen 2016 new detector"]})
        if method == "POST" and path == "/api/experiments/save":
            configuration, results = data.get("configuration"), data.get("results")
            if not isinstance(configuration, dict) or not isinstance(results, dict):
                raise ApiError("invalid_record", "configuration and results must be objects")
            if configuration.get("protocol") == "stage5b_quantum_domino":
                paths = save_stage5b_experiment(results, configuration, records)
            else:
                paths = save_experiment(results, configuration, records, artifacts=data.get("artifacts"))
            return 200, {"saved": True, "files": {key: path.name for key, path in paths.items()}, "directory": records.name}
        if method == "POST" and path == "/api/experiments/compare":
            left_name, right_name = data.get("left"), data.get("right")
            if not isinstance(left_name, str) or not isinstance(right_name, str) or left_name == right_name:
                raise ApiError("invalid_comparison", "select two different saved JSON records")
            left = _load_saved_record(left_name, records)
            right = _load_saved_record(right_name, records)
            left_values = _numeric_result_leaves(left.get("results", {}))
            right_values = _numeric_result_leaves(right.get("results", {}))
            differences = [
                {"path": key, "left": left_values[key], "right": right_values[key],
                 "difference": right_values[key] - left_values[key]}
                for key in sorted(left_values.keys() & right_values.keys())
                if left_values[key] != right_values[key]
            ]
            output = {
                "left": {"name": left_name, "metadata": left.get("metadata", {}), "configuration": left.get("configuration", {})},
                "right": {"name": right_name, "metadata": right.get("metadata", {}), "configuration": right.get("configuration", {})},
                "comparison": {
                    "configurations_match": left.get("configuration") == right.get("configuration"),
                    "shared_numeric_paths": len(left_values.keys() & right_values.keys()),
                    "numeric_differences": differences,
                    "interpretation": "Descriptive differences between stored JSON scalar values only; no physical recomputation or statistical test was performed.",
                },
            }
            return 200, _result(output, "descriptive_record_comparison", path, {"left": left_name, "right": right_name})
        if method == "GET" and path == "/api/experiments":
            records.mkdir(parents=True, exist_ok=True)
            return 200, {"records": sorted(p.name for p in records.glob("*.json"))}
        if method == "GET" and path.startswith("/api/experiments/"):
            if path.startswith("/api/experiments/csv/"):
                csv_path = _record_path(path.removeprefix("/api/experiments/csv/"), records)
                if csv_path.suffix != ".csv" or not csv_path.is_file():
                    raise ApiError("record_not_found", "experiment CSV record was not found", 404)
                return 200, {"csv": csv_path.read_text(encoding="utf-8-sig")}
            name = path.removeprefix("/api/experiments/")
            return 200, _load_saved_record(name, records)
        if path.startswith("/api/"):
            return 404, {"error": {"code": "not_found", "message": "API route not found"}}
        return 404, {"error": {"code": "not_found", "message": "resource not found"}}
    except ApiError as exc:
        return exc.status, {"error": {"code": exc.code, "message": str(exc)}}
    except (TypeError, ValueError, KeyError, IndexError) as exc:
        return 400, {"error": {"code": "invalid_request", "message": str(exc)}}
    except Exception as exc:  # Keep diagnostics explicit without exposing a traceback to browsers.
        return 500, {"error": {"code": "scientific_core_error", "message": f"{type(exc).__name__}: {exc}"}}


class Handler(BaseHTTPRequestHandler):
    """Локальний HTTP-обробник JSON API та зібраного статичного frontend."""
    server_version = "QuantumLaboratoryLocal/1"
    records_dir = DEFAULT_RECORDS
    static_dir = ROOT / "frontend" / "dist"
    auth_token: str | None = None

    def _authorized(self) -> bool:
        """Protect the private desktop listener from other local web pages/processes."""
        if self.auth_token is None:
            return True
        host = f"127.0.0.1:{self.server.server_address[1]}"
        origin = f"http://{host}"
        supplied = self.headers.get("X-Quantum-Lab-Token", "")
        if (self.headers.get("Host") == host
                and self.headers.get("Origin", origin) == origin
                and hmac.compare_digest(supplied, self.auth_token)):
            return True
        self._send(403, {"error": {"code": "desktop_access_denied", "message": "Desktop session authorization failed"}})
        return False

    def _send(self, status: int, value: Any, content_type: str = "application/json; charset=utf-8") -> None:
        """Надіслати JSON-відповідь з довжиною, charset і захисними заголовками."""
        body = json.dumps(_json_value(value), ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Обробити API GET або статичний файл, не дозволяючи вихід за dist/."""
        if not self._authorized():
            return
        if self.path.startswith("/api/"):
            status, data = dispatch("GET", self.path.split("?", 1)[0], records_dir=self.records_dir)
            self._send(status, data)
            return
        request_path = unquote(self.path.split("?", 1)[0]).lstrip("/") or "index.html"
        candidate = (self.static_dir / request_path).resolve()
        if candidate != self.static_dir.resolve() and self.static_dir.resolve() not in candidate.parents:
            self._send(404, {"error": {"code": "not_found", "message": "resource not found"}})
            return
        if not candidate.is_file():
            candidate = self.static_dir / "index.html"
        if not candidate.is_file():
            self._send(503, {"error": {"code": "frontend_not_built", "message": "Frontend build is missing; run npm install and npm run build in frontend."}})
            return
        payload = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        """Перевірити та диспетчеризувати JSON POST з обмеженням розміру й паралельності."""
        if not self._authorized():
            return
        if not self.path.startswith("/api/"):
            self._send(404, {"error": {"code": "not_found", "message": "resource not found"}})
            return
        if not _POST_REQUEST_SLOTS.acquire(blocking=False):
            self._send(503, {"error": {"code": "server_busy", "message": "A Python calculation is already running. Wait for it to finish, then retry."}})
            return
        try:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > MAX_REQUEST_BYTES:
                    raise ApiError("request_too_large", "request body exceeds 64 MiB", 413)
                body = self.rfile.read(length)
                data = json.loads(body.decode("utf-8")) if body else {}
                if not isinstance(data, dict):
                    raise ApiError("invalid_json_object", "request body must be a JSON object")
            except ApiError as exc:
                self._send(exc.status, {"error": {"code": exc.code, "message": str(exc)}})
                return
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._send(400, {"error": {"code": "invalid_json", "message": str(exc)}})
                return
            status, result = dispatch("POST", self.path.split("?", 1)[0], data, records_dir=self.records_dir)
            self._send(status, result)
        finally:
            _POST_REQUEST_SLOTS.release()

    def log_message(self, fmt: str, *args: Any) -> None:
        """Записати короткий локальний рядок доступу без журналювання тіла запиту."""
        if self.auth_token is not None:
            return  # Desktop record names and request URLs stay out of process logs.
        print(f"[local-api] {self.address_string()} {fmt % args}")


def create_server(host: str = "127.0.0.1", port: int = 8501, *,
                  auth_token: str | None = None, records_dir: str | Path | None = None,
                  static_dir: str | Path | None = None) -> ThreadingHTTPServer:
    """Створити сервер API на loopback; зовнішні мережеві bind-адреси відхиляються."""
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Quantum Laboratory API may bind only to loopback")
    if auth_token is not None and len(auth_token) < 32:
        raise ValueError("desktop authorization token is too short")
    configured_handler = type("ConfiguredHandler", (Handler,), {
        "auth_token": auth_token,
        "records_dir": _records_dir(records_dir),
        "static_dir": Path(static_dir).resolve() if static_dir is not None else Handler.static_dir,
    })
    return ThreadingHTTPServer((host, port), configured_handler)


def serve(host: str = "127.0.0.1", port: int = 8501) -> None:
    """Обслуговувати локальну лабораторію до завершення процесу, закривши сокет у finally."""
    server = create_server(host, port)
    print(f"Quantum Laboratory API listening at http://{server.server_address[0]}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    serve(os.environ.get("QUANTUM_LAB_HOST", "127.0.0.1"), int(os.environ.get("QUANTUM_LAB_PORT", "8501")))
