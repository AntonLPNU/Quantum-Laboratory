"""Full-state transmitter/receiver experiments on the validated TFIM core.

The transmitter is physical site 0. Receiver sites are 1..N-1 and evolve
under the existing open-boundary TFIM with site 0 excluded. Receiver-visible
quantities are computed only from partial traces. Sender operations are
nonselective CPTP maps; no outcome conditioning or postselection occurs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Integral

import numpy as np

from .multispin import apply_subsystem_kraus, partial_trace_subsystems, prepare_bell_pair_state
from .tfim import FieldSchedule, evolve_tfim, tfim_observables


def prepare_dynamic_receiver_state(
    n_spins: int,
    entangled_receiver_site: int = 1,
    spectator_states: Mapping[int, np.ndarray] | None = None,
) -> np.ndarray:
    """Prepare a singlet between sender site 0 and one selected receiver site.

    Unspecified receiver spectators are prepared in ``|0>`` by the shared
    multispin Bell-pair constructor. This is an ideal initial state, not an
    apparatus preparation model.
    """
    if isinstance(n_spins, (bool, np.bool_)) or not isinstance(n_spins, Integral) or not 3 <= n_spins <= 6:
        raise ValueError("dynamic receiver requires 3 through 6 spins")
    if isinstance(entangled_receiver_site, (bool, np.bool_)) or not isinstance(entangled_receiver_site, Integral):
        raise TypeError("entangled_receiver_site must be an integer site index")
    if not 1 <= entangled_receiver_site < n_spins:
        raise ValueError("entangled_receiver_site must be a receiver site in 1..N-1")
    return prepare_bell_pair_state(int(n_spins), [0, int(entangled_receiver_site)],
                                   bell="singlet", spectator_kets=spectator_states)


def receiver_reduced_states(full_states: Sequence[np.ndarray], receiver_sites: Sequence[int]) -> list[np.ndarray]:
    """Reduce full register states in the explicitly supplied receiver order."""
    if not isinstance(full_states, Sequence) or isinstance(full_states, (str, bytes)):
        raise TypeError("full_states must be an ordered sequence")
    if not isinstance(receiver_sites, Sequence) or isinstance(receiver_sites, (str, bytes)) or len(receiver_sites) == 0:
        raise ValueError("receiver_sites must be a nonempty ordered sequence")
    return [partial_trace_subsystems(state, receiver_sites) for state in full_states]


def trace_distance(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    """Return quantum trace distance 1/2 ||rho_a-rho_b||_1 for density states."""
    left, right = np.asarray(rho_a, dtype=complex), np.asarray(rho_b, dtype=complex)
    if left.ndim != 2 or left.shape[0] != left.shape[1] or right.shape != left.shape:
        raise ValueError("trace-distance inputs must be equal-size square matrices")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise ValueError("trace-distance inputs must be finite")
    for state in (left, right):
        if np.linalg.norm(state - state.conj().T) > 1e-10 or abs(np.trace(state) - 1) > 1e-10:
            raise ValueError("trace-distance inputs must be normalized Hermitian density matrices")
        if np.linalg.eigvalsh((state + state.conj().T) / 2).min() < -1e-10:
            raise ValueError("trace-distance inputs must be positive semidefinite")
    difference = (left - right + (left - right).conj().T) / 2
    return float(.5 * np.sum(np.abs(np.linalg.eigvalsh(difference))))


def _identity_channel() -> list[np.ndarray]:
    return [np.eye(2, dtype=complex)]


def _observable_series(states: Sequence[np.ndarray], n_receiver_spins: int) -> dict[str, np.ndarray]:
    rows = [tfim_observables(state, n_receiver_spins) for state in states]
    return {name: np.stack([np.asarray(row[name]) for row in rows]) for name in ("sigma_x", "sigma_y", "sigma_z", "nearest_neighbor_zz")}


def run_dynamic_receiver_experiment(configuration: Mapping[str, object]) -> dict:
    """Run reference, sender-operation, and positive-control evolutions.

    Required configuration keys are ``n_spins``, ``J``, ``h_schedule``, and
    ``times_s``. Optional keys are ``initial_state``,
    ``entangled_receiver_site``, ``spectator_states``,
    ``sender_kraus_operators``, ``local_controls``, and ``solver_options``.
    ``local_controls`` maps global receiver-site indices to Stage 5A field
    schedules. Every branch evolves the full state using I_A tensor H_R(t).
    """
    if not isinstance(configuration, Mapping):
        raise TypeError("configuration must be a mapping")
    required = {"n_spins", "J", "h_schedule", "times_s"}
    missing = required - configuration.keys()
    if missing:
        raise ValueError(f"missing configuration keys: {sorted(missing)}")
    n_spins = configuration["n_spins"]
    if isinstance(n_spins, (bool, np.bool_)) or not isinstance(n_spins, Integral) or not 3 <= n_spins <= 6:
        raise ValueError("dynamic receiver requires 3 through 6 spins")
    n_spins = int(n_spins)
    receiver_sites = list(range(1, n_spins))
    site = configuration.get("entangled_receiver_site", 1)
    if isinstance(site, (bool, np.bool_)) or not isinstance(site, Integral) or not 1 <= site < n_spins:
        raise ValueError("entangled_receiver_site must be an integer receiver site in 1..N-1")
    h_schedule = configuration["h_schedule"]
    if not isinstance(h_schedule, FieldSchedule):
        raise TypeError("h_schedule must be a Stage 5A FieldSchedule")
    initial = configuration.get("initial_state")
    if initial is None:
        initial = prepare_dynamic_receiver_state(n_spins, site, configuration.get("spectator_states"))
    else:
        initial = np.array(initial, dtype=complex, copy=True)
        # Let the core perform full shape, trace, positivity, and normalization validation.
        probe = evolve_tfim(initial, n_spins, configuration["J"], h_schedule, [0.0], active_sites=receiver_sites)
        if probe.status != "success":
            raise ValueError(f"initial_state is not a valid physical state: {probe.error}")
    controls = configuration.get("local_controls", {})
    if not isinstance(controls, Mapping):
        raise TypeError("local_controls must map receiver sites to FieldSchedule objects")
    if any(isinstance(key, (bool, np.bool_)) or not isinstance(key, Integral) or key not in receiver_sites for key in controls):
        raise ValueError("local_controls may target receiver sites 1..N-1 only")
    controls = dict(controls)
    sender_kraus = configuration.get("sender_kraus_operators", _identity_channel())
    sender_state = apply_subsystem_kraus(initial, sender_kraus, [0])
    raw_times = np.asarray(configuration["times_s"])
    if raw_times.dtype.kind not in "iuf" or raw_times.ndim != 1 or raw_times.size == 0:
        raise ValueError("times_s must be a nonempty finite one-dimensional sequence")
    times = raw_times.astype(float)
    if np.any(~np.isfinite(times)):
        raise ValueError("times_s must be finite")
    solver_options = configuration.get("solver_options", {})
    if not isinstance(solver_options, Mapping):
        raise TypeError("solver_options must be a mapping")
    options = dict(solver_options)
    allowed_options = {"rtol", "atol", "max_steps"}
    if set(options) - allowed_options:
        raise ValueError(f"unsupported solver options: {sorted(set(options)-allowed_options)}")

    common = {"n_spins": n_spins, "J": configuration["J"], "h_schedule": h_schedule,
              "times_s": times, "active_sites": receiver_sites,
              "save_states_at": tuple(range(len(times))), **options}
    branch_inputs = {
        "reference": (initial, {}),
        "sender_operation": (sender_state, {}),
        "positive_control": (initial, controls),
    }
    scenarios = {}
    for name, (state, local_controls) in branch_inputs.items():
        evolution = evolve_tfim(state, local_controls=local_controls, **common)
        full_states = [evolution.snapshots[index].copy() for index in sorted(evolution.snapshots)]
        reduced = receiver_reduced_states(full_states, receiver_sites) if full_states else []
        scenarios[name] = {
            "status": evolution.status,
            "error": evolution.error,
            "times_s": evolution.times_s.copy(),
            "full_states": full_states,
            "receiver_states": reduced,
            "receiver_observables": _observable_series(reduced, len(receiver_sites)) if reduced else {},
            "solver_diagnostics": dict(evolution.diagnostics),
        }

    all_success = all(branch["status"] == "success" for branch in scenarios.values())
    metrics = {}
    if all_success:
        reference_states = scenarios["reference"]["receiver_states"]
        sender_states = scenarios["sender_operation"]["receiver_states"]
        control_states = scenarios["positive_control"]["receiver_states"]
        metrics["sender_trace_distance"] = [trace_distance(a, b) for a, b in zip(reference_states, sender_states)]
        metrics["positive_control_trace_distance"] = [trace_distance(a, b) for a, b in zip(reference_states, control_states)]
        reference_z = scenarios["reference"]["receiver_observables"]["sigma_z"]
        control_z = scenarios["positive_control"]["receiver_observables"]["sigma_z"]
        changed_sites = sorted(controls)
        local_columns = [receiver_sites.index(item) for item in changed_sites]
        other_columns = [i for i in range(len(receiver_sites)) if i not in local_columns]
        local_response = float(np.max(np.abs(control_z[:, local_columns] - reference_z[:, local_columns]))) if local_columns else 0.0
        distant_response = float(np.max(np.abs(control_z[:, other_columns] - reference_z[:, other_columns]))) if other_columns else 0.0
        metrics["positive_control_response"] = {
            "local_max_abs_delta_sigma_z": local_response,
            "distant_max_abs_delta_sigma_z": distant_response,
            "distant_to_local_ratio": None if local_response <= 1e-14 else distant_response / local_response,
            "ratio_status": "undefined_zero_local_response" if local_response <= 1e-14 else "descriptive_only",
        }
    else:
        metrics["status"] = "unavailable_due_to_failed_evolution"

    serialized_controls = {int(key): schedule.to_dict() for key, schedule in controls.items()}
    serialized_h = h_schedule.to_dict()
    saved_configuration = {
        "n_spins": n_spins, "sender_site": 0, "receiver_sites": receiver_sites,
        "entangled_receiver_site": int(site) if initial is not None else None,
        "J": float(configuration["J"]), "units": {"J": "s^-1", "h": "s^-1", "time": "s"},
        "hamiltonian": "H_AR/hbar = I_A tensor H_R/hbar; open OBC TFIM; Pauli normalization",
        "h_schedule": serialized_h, "times_s": times.tolist(),
        "local_controls": serialized_controls,
        "sender_operation": "nonselective local CPTP map on A (identity Kraus family if omitted)",
        "sender_kraus_operators": [np.asarray(item, complex).copy() for item in sender_kraus],
        "initial_state": np.asarray(initial, complex).copy(), "solver_options": options,
    }
    return {"status": "success" if all_success else "failed",
            "error": None if all_success else "one_or_more_evolution_branches_failed",
            "configuration": saved_configuration, "scenarios": scenarios, "metrics": metrics}
