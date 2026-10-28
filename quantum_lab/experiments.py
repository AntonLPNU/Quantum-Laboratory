"""Reproducible protocols. Receiver-side calculations never consume sender outcomes."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .metrics import chsh_value, concurrence, correlator, maximal_chsh_value, von_neumann_entropy
from .noise import apply_local_phase_damping, phase_damping
from .operations import apply_local_unitary, joint_measurement_probabilities, local_rotation, measurement_probabilities
from .states import bell_state, partial_trace, validate_density_matrix


def run_chsh_experiment(state_name: str = "singlet", shots_per_setting: int = 2000, seed: int = 42, dephasing_a: float = 0.0, dephasing_b: float = 0.0, rotations=None) -> dict:
    """Sample fixed-axis CHSH (SRC-001, SRC-006) after optional local phase damping."""
    if shots_per_setting < 1:
        raise ValueError("shots_per_setting must be positive")
    if seed is None or seed < 0:
        raise ValueError("seed must be a non-negative integer for reproducibility")
    rho = bell_state(state_name)
    operations = rotations or {}
    for subsystem, key in ((0, "a"), (1, "b")):
        operation = operations.get(key, {"axis": [0, 0, 1], "angle_rad": 0.0})
        rho = apply_local_unitary(rho, local_rotation(operation["axis"], operation["angle_rad"]), subsystem)
    rho = apply_local_phase_damping(rho, dephasing_a, 0)
    rho = apply_local_phase_damping(rho, dephasing_b, 1)
    a = np.array([1.0, 0.0, 0.0])
    a_prime = np.array([0.0, 1.0, 0.0])
    b = np.array([1.0, 1.0, 0.0]) / np.sqrt(2)
    b_prime = np.array([1.0, -1.0, 0.0]) / np.sqrt(2)
    axes = {"ab": (a, b), "ab_prime": (a, b_prime), "a_prime_b": (a_prime, b), "a_prime_b_prime": (a_prime, b_prime)}
    rng = np.random.default_rng(seed)
    settings = {}
    for name, (axis_a, axis_b) in axes.items():
        probabilities = joint_measurement_probabilities(rho, axis_a, axis_b)
        outcomes = list(probabilities)
        selected = rng.choice(len(outcomes), size=shots_per_setting, p=[probabilities[pair] for pair in outcomes])
        samples = np.array([outcomes[index] for index in selected])
        settings[name] = {
            "axis_a": axis_a.tolist(), "axis_b": axis_b.tolist(),
            "theoretical_correlation": correlator(rho, axis_a, axis_b),
            "sampled_correlation": float(np.mean(samples[:, 0] * samples[:, 1])),
            "standard_error": float(np.sqrt(max(0.0, 1.0 - np.mean(samples[:, 0] * samples[:, 1]) ** 2) / max(1, shots_per_setting - 1))),
            "shots": shots_per_setting,
        }
    sampled = abs(settings["ab"]["sampled_correlation"] + settings["ab_prime"]["sampled_correlation"] + settings["a_prime_b"]["sampled_correlation"] - settings["a_prime_b_prime"]["sampled_correlation"])
    sampled_standard_error = float(np.sqrt(sum(setting["standard_error"] ** 2 for setting in settings.values())))
    theoretical_fixed = chsh_value(rho, a, a_prime, b, b_prime)
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "two_spin_projective_with_local_phase_damping" if dephasing_a or dephasing_b else "ideal_two_spin_projective",
        "state_name": state_name, "initial_state": state_name, "shots_per_setting": shots_per_setting, "seed": seed,
        "dephasing_fractions": {"a": float(dephasing_a), "b": float(dephasing_b)},
        "rotations": operations,
        "fixed_axes": {name: {"a": axes[name][0].tolist(), "b": axes[name][1].tolist()} for name in axes},
        "settings": settings,
        "theoretical_chsh": theoretical_fixed,
        "chsh_fixed": theoretical_fixed,
        "chsh_maximal": maximal_chsh_value(rho),
        "sampled_chsh": sampled,
        "sampled_chsh_standard_error": sampled_standard_error,
        "classical_chsh_bound": 2.0, "quantum_chsh_bound": 2 * np.sqrt(2),
        "assumptions": ["ideal singlet or Bell state", "independent setting groups", "ideal projective readout", "no detector loss or loophole modeling", "dimensionless phenomenological phase damping; not apparatus-calibrated"],
    }


def run_rotation_sweep(times, state_name: str = "singlet", axis=(0, 1, 0), angular_frequency_rad_s: float = 1.0, measurement_axis_a=(0, 0, 1), measurement_axis_b=(0, 0, 1)) -> dict:
    """Use U=exp(−iωt n·σ/2) on A (SRC-002, SRC-006); t in seconds iff ω is rad/s; no decoherence."""
    values = np.asarray(times, dtype=float)
    if values.ndim != 1 or values.size < 1 or not np.all(np.isfinite(values)):
        raise ValueError("times must be a non-empty sequence of finite values")
    if not np.isfinite(angular_frequency_rad_s):
        raise ValueError("angular_frequency_rad_s must be finite")
    initial = bell_state(state_name)
    probabilities, correlations, expectations = [], [], []
    for time in values:
        state = apply_local_unitary(initial, local_rotation(axis, angular_frequency_rad_s * time), 0)
        bob = partial_trace(state, 1)
        probabilities.append(measurement_probabilities(bob, measurement_axis_b))
        correlations.append(correlator(state, measurement_axis_a, measurement_axis_b))
        pa = partial_trace(state, 0)
        expectations.append(measurement_probabilities(pa, measurement_axis_a)[1] - measurement_probabilities(pa, measurement_axis_a)[-1])
    return {"times": values.tolist(), "angular_frequency_rad_s": angular_frequency_rad_s,
            "receiver_probabilities": probabilities, "correlations": correlations, "local_expectation_a": expectations,
            "model": "ideal_static_rotation", "units_note": "time in seconds only when angular frequency is supplied in rad/s; otherwise parameters are dimensionless"}


def run_state_experiment(state_name: str = "singlet", rotations=None, axis_a=(0, 0, 1), axis_b=(0, 0, 1), shots: int = 2000, seed: int = 42, dephasing_a: float = 0.0, dephasing_b: float = 0.0) -> dict:
    """Prepare a Bell state, apply rotations and optional local dephasing, then Born-rule measurements (SRC-006)."""
    if shots < 1:
        raise ValueError("shots must be positive")
    if seed is None or seed < 0:
        raise ValueError("seed must be a non-negative integer for reproducibility")
    rho = bell_state(state_name)
    operations = rotations or {}
    for subsystem, key in ((0, "a"), (1, "b")):
        operation = operations.get(key, {"axis": [0, 0, 1], "angle_rad": 0.0})
        rho = apply_local_unitary(rho, local_rotation(operation["axis"], operation["angle_rad"]), subsystem)
    rho = apply_local_phase_damping(rho, dephasing_a, 0)
    rho = apply_local_phase_damping(rho, dephasing_b, 1)
    probs = joint_measurement_probabilities(rho, axis_a, axis_b)
    keys = list(probs)
    rng = np.random.default_rng(seed)
    sampled = rng.choice(len(keys), size=shots, p=[probs[key] for key in keys])
    counts = {f"{a},{b}": int(np.count_nonzero(sampled == index)) for index, (a, b) in enumerate(keys)}
    reduced_a, reduced_b = partial_trace(rho, 0), partial_trace(rho, 1)
    fixed_chsh_axes = ([1, 0, 0], [0, 1, 0], [1, 1, 0], [1, -1, 0])
    normalized_fixed_chsh_axes = (fixed_chsh_axes[0], fixed_chsh_axes[1], np.array([1, 1, 0]) / np.sqrt(2), np.array([1, -1, 0]) / np.sqrt(2))
    diagnostics = {
        "trace": float(np.trace(rho).real),
        "hermitian": bool(np.allclose(rho, rho.conj().T, atol=1e-10)),
        "minimum_eigenvalue": float(np.linalg.eigvalsh(rho).min()),
        "valid_density_matrix": validate_density_matrix(rho),
    }
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "two_spin_projective_with_local_phase_damping" if dephasing_a or dephasing_b else "ideal_two_spin_projective",
        "state_name": state_name,
        "initial_state": state_name,
        "rotations": operations,
        "dephasing_fractions": {"a": float(dephasing_a), "b": float(dephasing_b)},
        "measurement_axes": {"a": list(axis_a), "b": list(axis_b)},
        "shots": shots,
        "seed": seed,
        "density_matrix": rho,
        "reduced_density_matrices": {"a": reduced_a, "b": reduced_b},
        "local_probabilities": {"a": measurement_probabilities(reduced_a, axis_a), "b": measurement_probabilities(reduced_b, axis_b)},
        "joint_probabilities": {f"{a},{b}": p for (a, b), p in probs.items()},
        "joint_counts": counts,
        "correlator": correlator(rho, axis_a, axis_b),
        "chsh_maximal_axes_value": chsh_value(rho, *normalized_fixed_chsh_axes),
        "chsh_fixed": chsh_value(rho, *normalized_fixed_chsh_axes),
        "chsh_maximal": maximal_chsh_value(rho),
        "concurrence": concurrence(rho),
        "global_entropy_bits": von_neumann_entropy(rho),
        "diagnostics": diagnostics,
        "assumptions": ["finite two-spin Hilbert space", "ideal normalized state preparation", "ideal projective measurements", "no detector noise or loss"] + (["dimensionless phenomenological local phase damping; not calibrated to an apparatus"] if dephasing_a or dephasing_b else ["no environmental coupling"]),
    }


def run_phase_damping_sweep(
    state_name: str = "singlet",
    values_a=None,
    values_b=None,
    axis_a=(0, 0, 1),
    axis_b=(0, 0, 1),
    seed: int = 42,
    rotations=None,
) -> dict:
    """Evaluate deterministic observables over independent λ_A/λ_B grids.

    Every joint metric is calculated from the complete post-channel ρ_AB;
    local Born probabilities use its reduced states. The seed is recorded for
    reproducibility with experiment records; this exact sweep itself samples
    no finite-shot outcomes.
    """
    if seed is None or int(seed) < 0:
        raise ValueError("seed must be a non-negative integer for reproducibility")
    lambdas_a = np.linspace(0.0, 1.0, 21) if values_a is None else np.asarray(values_a, dtype=float)
    lambdas_b = np.linspace(0.0, 1.0, 21) if values_b is None else np.asarray(values_b, dtype=float)
    if lambdas_a.ndim != 1 or lambdas_b.ndim != 1 or not lambdas_a.size or not lambdas_b.size:
        raise ValueError("values_a and values_b must be non-empty one-dimensional arrays")
    if not np.all(np.isfinite(lambdas_a)) or np.any((lambdas_a < 0.0) | (lambdas_a > 1.0)):
        raise ValueError("values_a must contain finite values in [0, 1]")
    if not np.all(np.isfinite(lambdas_b)) or np.any((lambdas_b < 0.0) | (lambdas_b > 1.0)):
        raise ValueError("values_b must contain finite values in [0, 1]")

    x, y, z = np.eye(3)
    b_plus, b_minus = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0), np.array([1.0, -1.0, 0.0]) / np.sqrt(2.0)
    fixed_axes = (x, y, b_plus, b_minus)
    joint_axes = {
        "xx": (x, x), "xy": (x, y), "xz": (x, z),
        "yx": (y, x), "yy": (y, y), "yz": (y, z),
        "zx": (z, x), "zy": (z, y), "zz": (z, z),
    }
    shape = (lambdas_a.size, lambdas_b.size)
    concurrence_grid = np.empty(shape)
    chsh_maximal_grid = np.empty(shape)
    chsh_fixed_grid = np.empty(shape)
    joint_correlations = {name: np.empty(shape) for name in joint_axes}
    local_expectations_a, local_expectations_b = np.empty(shape), np.empty(shape)
    local_probabilities_a = [[None for _ in lambdas_b] for _ in lambdas_a]
    local_probabilities_b = [[None for _ in lambdas_b] for _ in lambdas_a]
    joint_probabilities = {name: [[None for _ in lambdas_b] for _ in lambdas_a] for name in joint_axes}
    density_matrices = [[None for _ in lambdas_b] for _ in lambdas_a]
    operations = rotations or {}

    for i, lambda_a in enumerate(lambdas_a):
        for j, lambda_b in enumerate(lambdas_b):
            rho = bell_state(state_name)
            for subsystem, key in ((0, "a"), (1, "b")):
                operation = operations.get(key, {"axis": [0, 0, 1], "angle_rad": 0.0})
                rho = apply_local_unitary(rho, local_rotation(operation["axis"], operation["angle_rad"]), subsystem)
            rho = apply_local_phase_damping(rho, float(lambda_a), 0)
            rho = apply_local_phase_damping(rho, float(lambda_b), 1)
            reduced_a, reduced_b = partial_trace(rho, 0), partial_trace(rho, 1)
            concurrence_grid[i, j] = concurrence(rho)
            chsh_maximal_grid[i, j] = maximal_chsh_value(rho)
            chsh_fixed_grid[i, j] = chsh_value(rho, *fixed_axes)
            local_probabilities_a[i][j] = measurement_probabilities(reduced_a, axis_a)
            local_probabilities_b[i][j] = measurement_probabilities(reduced_b, axis_b)
            local_expectations_a[i, j] = sum(outcome * probability for outcome, probability in local_probabilities_a[i][j].items())
            local_expectations_b[i, j] = sum(outcome * probability for outcome, probability in local_probabilities_b[i][j].items())
            density_matrices[i][j] = rho
            for name, (joint_a, joint_b) in joint_axes.items():
                joint_correlations[name][i, j] = correlator(rho, joint_a, joint_b)
                probabilities = joint_measurement_probabilities(rho, joint_a, joint_b)
                joint_probabilities[name][i][j] = {f"{a},{b}": value for (a, b), value in probabilities.items()}

    q = (1.0 - lambdas_a[:, None]) * (1.0 - lambdas_b[None, :])
    unrotated_input = all(abs(float(operation.get("angle_rad", 0.0))) <= 1e-12 for operation in operations.values())
    singlet_reference_applies = state_name == "singlet" and unrotated_input
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": "phase_damping_sweep",
        "model": "local_phase_damping_on_full_two_spin_density_matrix",
        "state_name": state_name,
        "rotations": operations,
        "seed": int(seed),
        "lambdas_a": lambdas_a,
        "lambdas_b": lambdas_b,
        "analytic_q": q if singlet_reference_applies else None,
        "analytic_singlet_concurrence": q if singlet_reference_applies else None,
        "analytic_singlet_chsh_maximal": 2.0 * np.sqrt(1.0 + q**2) if singlet_reference_applies else None,
        "analytic_reference_applies": singlet_reference_applies,
        "concurrence": concurrence_grid,
        "chsh_maximal": chsh_maximal_grid,
        "chsh_fixed": chsh_fixed_grid,
        "fixed_chsh_axes": [axis.tolist() for axis in fixed_axes],
        "joint_correlations": joint_correlations,
        "joint_probabilities": joint_probabilities,
        "measurement_axes": {"a": list(axis_a), "b": list(axis_b)},
        "local_expectations": {"a": local_expectations_a, "b": local_expectations_b},
        "local_probabilities_a": local_probabilities_a,
        "local_probabilities_b": local_probabilities_b,
        "density_matrices": density_matrices,
    }


def run_signaling_experiment(shots: int = 1000, seed: int = 42, receiver_axis=(0, 0, 1), sender_dephasing: float = 0.0, receiver_dephasing: float = 0.0) -> dict:
    """Test local marginals for two sender choices using receiver-only samples.

    Each sender choice is a unitary on A; Bob samples only his reduced state.
    This protocol models ideal projective measurements with no detector noise.
    Model: local unitary channel and partial trace (SRC-002, SRC-003, SRC-006);
    all outcomes are dimensionless ±1 and no conditional A result is supplied to B.
    The complete state remains internal; only B's reduced state supplies the
    receiver probabilities. Sender-setting labels are analysis metadata only.
    """
    if shots < 2:
        raise ValueError("shots must be at least 2")
    if seed is None or seed < 0:
        raise ValueError("seed must be a non-negative integer for reproducibility")
    rng = np.random.default_rng(seed)
    initial = bell_state("singlet")
    choices = {"0": local_rotation([1, 0, 0], 0.0), "1": local_rotation([0, 1, 0], np.pi)}
    by_bit: dict[str, dict[str, int]] = {}
    per_bit_correct = []
    local_distributions = {}
    for bit, operation in choices.items():
        state = apply_local_unitary(initial, operation, subsystem=0)
        state = apply_local_phase_damping(state, sender_dephasing, subsystem=0)
        bob_state = partial_trace(state, keep=1)
        bob_state = phase_damping(bob_state, receiver_dephasing)
        probs = measurement_probabilities(bob_state, receiver_axis)
        outcomes = rng.choice(np.array([-1, 1]), size=shots, p=[probs[-1], probs[1]])
        counts = {"-1": int(np.count_nonzero(outcomes == -1)), "+1": int(np.count_nonzero(outcomes == 1))}
        by_bit[bit] = counts
        per_bit_correct.append(counts["+1"] if bit == "1" else counts["-1"])
        local_distributions[bit] = {"-1": probs[-1], "+1": probs[1]}
    total = shots * 2
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "ideal_two_spin_projective" if sender_dephasing == 0 and receiver_dephasing == 0 else "two_spin_projective_with_local_phase_damping",
        "initial_state": "singlet",
        "sender_dephasing_fraction": float(sender_dephasing),
        "receiver_dephasing_fraction": float(receiver_dephasing),
        "apparatus_calibration_status": "NOT_CALIBRATED",
        "shots_per_sender_choice": shots,
        "seed": seed,
        "receiver_axis": list(receiver_axis),
        "receiver_counts": by_bit,
        "receiver_local_distribution": local_distributions,
        "decoding_accuracy": sum(per_bit_correct) / total,
        "decoding_standard_error": float(np.sqrt(0.25 / total)),
        "sender_outcomes_exposed_to_receiver": False,
        "sender_setting_labels_are_analysis_only": True,
        "assumptions": ["ideal singlet state", "local unitary choices at A", "parameterized local phase-damping channel", "ideal projective readout at B", "no detector noise or loss"],
    }



def run_tfim_experiment(n_spins, J, h_schedule, initial_state, times_s,
                        seed=None, solver_options=None) -> dict:
    """Run a reproducible ideal closed-system TFIM experiment via tfim.

    Return {'configuration': ..., 'results': ...}; configuration is directly
    JSON serializable. Initial complex128 amplitudes/matrix entries are stored
    as separate real/imag arrays, preserving the exact input representation.
    State and local-control inputs are detached and serialized before solver
    callbacks can mutate caller-owned objects.
    No random draws occur; seed is optional recorded provenance.

    solver_options supports rtol (1e-9), atol (1e-12), max_steps (100000),
    save_states_at (unique time-grid indexes, default empty), local_controls
    (integer sites mapped to FieldSchedule), and cancel_check (a runtime
    callable, default None). Unknown keys are rejected. The callback itself
    is not serialized: cancellation_enabled records its presence and results
    retain the actual cancellation status/reason and completed samples.

    The snapshot budget is 256 MiB, checked before entering evolve_tfim.
    Invalid inputs raise TypeError/ValueError; numerical failures/cancellation
    retain their partial trajectory and never set completed=True.
    """
    from collections.abc import Mapping
    from numbers import Integral
    from . import tfim

    if seed is not None and (isinstance(seed, (bool, np.bool_))
                             or not isinstance(seed, Integral) or seed < 0):
        raise ValueError('seed must be None or a nonnegative integer')
    if solver_options is not None and not isinstance(solver_options, Mapping):
        raise TypeError('solver_options must be a mapping')
    options = dict(rtol=1e-9, atol=1e-12, max_steps=100000,
                   save_states_at=(), local_controls=None, cancel_check=None)
    supplied = {} if solver_options is None else dict(solver_options)
    unknown = supplied.keys()-options.keys()
    if unknown:
        raise ValueError('unsupported solver_options keys: '+', '.join(sorted(map(str, unknown))))
    options.update(supplied)
    n_spins = tfim._spin_count(n_spins)
    state, actual_spins = tfim._state(initial_state, physical=True)
    if actual_spins != n_spins:
        raise ValueError('n_spins must match the state dimension')
    requested = tfim._sequence(times_s, 'times_s')
    indexes = tfim._indices(options['save_states_at'], len(requested), 'save_states_at')
    options['save_states_at'] = indexes
    state_kind = 'ket' if state.ndim == 1 else 'density'
    snapshot_estimate = tfim._guard_tfim_snapshots(n_spins, len(indexes), state_kind)
    if not isinstance(h_schedule, tfim.FieldSchedule):
        raise TypeError('h_schedule must be a FieldSchedule')
    raw_controls = options['local_controls']
    if raw_controls is None:
        raw_controls = {}
    if not isinstance(raw_controls, Mapping):
        raise TypeError('local_controls must map sites to schedules')
    controls = {}
    for site, schedule in raw_controls.items():
        selected_site = tfim._indices([site], n_spins, 'local control site')[0]
        if not isinstance(schedule, tfim.FieldSchedule):
            raise TypeError('local controls must be FieldSchedule objects')
        controls[selected_site] = schedule
    # FieldSchedule is frozen with immutable numeric tuples. Detach the mutable
    # state/mapping, then capture provenance before any runtime callback runs.
    state = state.copy()
    options['local_controls'] = controls
    initial_record = {'kind': state_kind, 'dtype': 'complex128',
                      'real': state.real.tolist(), 'imag': state.imag.tolist()}
    schedule_record = h_schedule.to_dict()
    controls_record = {str(site): schedule.to_dict() for site, schedule in controls.items()}
    evolution = tfim.evolve_tfim(state, n_spins, J, h_schedule, requested, **options)
    # Estimate trajectory storage using the complete requested grid, while
    # charging snapshots only for the selected indexes.
    memory = tfim.estimate_tfim_memory(n_spins, len(requested), state_kind, False)
    memory['snapshot_bytes'] = snapshot_estimate['snapshot_bytes']
    memory['total_bytes'] += snapshot_estimate['snapshot_bytes']
    configuration = {
        'protocol': 'tfim', 'model': 'homogeneous_open_boundary_tfim_with_local_x_controls',
        'n_spins': n_spins, 'J': float(J), 'h_schedule': schedule_record,
        'local_controls': controls_record,
        'generator': 'H/hbar = -J sum Z_i Z_(i+1) - h(t) sum X_i - sum delta_h_i(t) X_i',
        'units': {'time': 's', 'J': 's^-1', 'h': 's^-1', 'local_controls': 's^-1',
                  'generator': 's^-1', 'energy_over_hbar': 's^-1', 'pauli_expectations': 'dimensionless'},
        'boundary_conditions': 'OBC', 'bonds': [[i, i+1] for i in range(n_spins-1)],
        'basis_order': '|q0 ... q(N-1)>; spin 0 leftmost tensor factor; big-endian',
        'operator_convention': 'Pauli eigenvalues +/-1; physical spin S = hbar sigma/2',
        'initial_state': initial_record,
        'times_s': [float(t) for t in requested],
        'observables': list(evolution.observables), 'observable_sites': list(range(n_spins)),
        'solver_options': {'rtol': float(options['rtol']), 'atol': float(options['atol']),
                           'max_steps': int(options['max_steps']), 'save_states_at': indexes,
                           'cancellation_enabled': options['cancel_check'] is not None},
        'state_validation_atol': tfim._ATOL,
        'seed': None if seed is None else int(seed),
        'sources': list(tfim.TFIM_SOURCE_IDS), 'memory_estimate': memory,
        'assumptions': ['ideal closed finite spin chain', 'unitary evolution from t=0',
                        'homogeneous nearest-neighbor coupling', 'no apparatus calibration'],
    }
    results = {
        'model': configuration['model'], 'status': evolution.status,
        'completed': evolution.status == 'success', 'error': evolution.error,
        'times_s': evolution.times_s, 'observables': evolution.observables,
        'snapshots': evolution.snapshots, 'final_state': evolution.final_state,
        'diagnostics': evolution.diagnostics,
    }
    return {'configuration': configuration, 'results': results}
