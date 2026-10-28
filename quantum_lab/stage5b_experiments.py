"""High-level Stage 5B orchestration over the validated scientific core."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from pathlib import Path

import numpy as np

from .deviation import exact_observable_summary
from .dynamic_receiver import run_dynamic_receiver_experiment
from .provenance import code_provenance
from .storage import save_experiment
from .tfim import FieldSchedule


_PAULI = {
    "sigma_x": np.array([[0, 1], [1, 0]], dtype=complex),
    "sigma_y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "sigma_z": np.diag([1, -1]).astype(complex),
}


def run_stage5b_experiment(configuration: Mapping[str, object]) -> dict:
    """Run receiver physics and exact analyzer summaries using the shared core.

    Optional ``primary_observable`` has keys ``site`` and ``pauli``. If
    ``sampling`` contains a locked preregistration, confirmatory sampling is
    dispatched through its frozen protocol and criteria.
    """
    if not isinstance(configuration, Mapping):
        raise TypeError("configuration must be a mapping")
    physics = run_dynamic_receiver_experiment(configuration)
    result = deepcopy(physics)
    if result["status"] != "success":
        result["analysis"] = {"status": "unavailable_due_to_failed_physics"}
        return result

    n = int(result["configuration"]["n_spins"])
    receiver_sites = list(result["configuration"]["receiver_sites"])
    primary = configuration.get("primary_observable", {"site": receiver_sites[-1], "pauli": "sigma_z"})
    if not isinstance(primary, Mapping) or primary.get("pauli") not in _PAULI:
        raise ValueError("primary_observable must identify one Pauli operator")
    site = primary.get("site")
    if isinstance(site, bool) or not isinstance(site, int) or site not in receiver_sites:
        raise ValueError("primary_observable site must be a receiver site")
    pauli_name = str(primary["pauli"])
    physical_summaries = {}
    for name, scenario in result["scenarios"].items():
        by_site = {}
        for physical_site in receiver_sites:
            local_column = receiver_sites.index(physical_site)
            rows = []
            for local_density in scenario["receiver_states"]:
                from .multispin import partial_trace_subsystems
                local_state = partial_trace_subsystems(local_density, [local_column])
                rows.append({key: value for key, value in exact_observable_summary(local_state, _PAULI["sigma_z"]).items()})
            by_site[str(physical_site)] = rows
        selected_column = receiver_sites.index(site)
        selected_rows = []
        for local_density in scenario["receiver_states"]:
            from .multispin import partial_trace_subsystems
            local_state = partial_trace_subsystems(local_density, [selected_column])
            selected_rows.append(exact_observable_summary(local_state, _PAULI[pauli_name]))
        physical_summaries[name] = {"local_sigma_z_by_receiver_site": by_site,
                                    "primary_observable": {"site": site, "pauli": pauli_name,
                                                           "exact_by_time": selected_rows}}
    result["analysis"] = {"kind": "exact_predictions", "scenarios": physical_summaries,
                          "sampling_is_separate": True,
                          "interpretation": "Expected values are predictions across independent preparations, not continuous observation of one system."}
    result["plot_data"] = {
        "time_s": result["scenarios"]["reference"]["times_s"].copy(),
        "series": {name: {str(site): scenario["receiver_observables"]["sigma_z"][:, column].copy()
                          for column, site in enumerate(receiver_sites)}
                   for name, scenario in result["scenarios"].items()},
        "axes": {"x": {"name": "time", "unit": "s"},
                 "y": {"name": "receiver Pauli expectation", "unit": "dimensionless"}},
        "style": {"chart": "line", "labels_are_scenarios_and_physical_receiver_sites": True},
    }
    result["configuration"].update({"protocol": "stage5b_quantum_domino",
                                    "sources": [f"SRC-{i:03d}" for i in range(20, 27)],
                                    "primary_observable": {"site": int(site), "pauli": pauli_name},
                                    "code_provenance": code_provenance(Path(__file__).resolve().parents[1])})
    sampling = configuration.get("sampling")
    if sampling is not None:
        from .stage5b_sampling import run_quantum_domino_primary_sampling
        if not isinstance(sampling, Mapping) or not isinstance(sampling.get("preregistration"), Mapping):
            raise ValueError("sampling requires a locked preregistration")
        result["configuration"]["preregistration_hash"] = sampling["preregistration"].get("preregistration_hash")
        result["configuration"]["preregistration"] = deepcopy(dict(sampling["preregistration"]))
        result["sampling"] = run_quantum_domino_primary_sampling(
            sampling["preregistration"], seed=sampling.get("seed"))
        prereg = sampling["preregistration"]
        result["sampling"]["statistical_criteria"] = deepcopy(prereg["criteria"])
        result["sampling"]["power_preflight"] = deepcopy(prereg["preflight"]["power_runs"][-1])
        result["sampling"]["positive_control_preflight"] = {
            key: deepcopy(prereg["preflight"][key])
            for key in ("amplitude_ratio", "amplitude_s_inverse", "time_s",
                        "reference_probability_plus", "positive_control_probability_plus",
                        "difference_probability_plus", "positive_control_trace_distance",
                        "global_convergence")}
    return result


def save_stage5b_experiment(results: Mapping[str, object], configuration: Mapping[str, object],
                            directory: str | Path, artifacts: Mapping[str, object] | None = None) -> dict:
    """Persist a complete successful run through the shared experiment store."""
    if not isinstance(results, Mapping) or not isinstance(configuration, Mapping):
        raise TypeError("results and configuration must be mappings")
    saved_config = deepcopy(dict(configuration))
    saved_config.setdefault("code_provenance", code_provenance(Path(__file__).resolve().parents[1]))
    saved_config.setdefault("sources", [f"SRC-{i:03d}" for i in range(20, 27)])
    return save_experiment(deepcopy(dict(results)), saved_config, directory,
                           artifacts=deepcopy(dict(artifacts or {})))


def _decode_complex(value):
    if isinstance(value, dict) and set(value) == {"real", "imag"}:
        return complex(value["real"], value["imag"])
    if isinstance(value, list):
        return [_decode_complex(item) for item in value]
    if isinstance(value, dict):
        return {key: _decode_complex(item) for key, item in value.items()}
    return value


def load_stage5b_configuration(path: str | Path) -> dict:
    """Restore a saved Stage 5B run configuration into directly runnable API values."""
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("schema_version") != 1 or not isinstance(record.get("configuration"), dict):
        raise ValueError("unsupported experiment record or missing configuration")
    if record.get("configuration", {}).get("protocol") != "stage5b_quantum_domino":
        raise ValueError("record is not a Stage 5B experiment")
    if record.get("results", {}).get("status") != "success":
        raise ValueError("only successful Stage 5B configurations can be replayed")
    config = dict(record["configuration"])
    schedule_fields = {"kind", "parameters", "edges_s", "values"}
    if isinstance(config.get("h_schedule"), dict) and set(config["h_schedule"]) == schedule_fields:
        config["h_schedule"] = FieldSchedule.from_dict(config["h_schedule"])
    config["local_controls"] = {
        int(site): FieldSchedule.from_dict(value) if isinstance(value, dict) and set(value) == schedule_fields else value
        for site, value in config.get("local_controls", {}).items()
    }
    if "initial_state" in config:
        config["initial_state"] = np.asarray(_decode_complex(config["initial_state"]), dtype=complex)
    if "sender_kraus_operators" in config:
        config["sender_kraus_operators"] = [np.asarray(_decode_complex(item), dtype=complex)
                                            for item in config["sender_kraus_operators"]]
    preregistration = config.pop("preregistration", None)
    if preregistration is not None:
        config["sampling"] = {"preregistration": preregistration}
    return config
