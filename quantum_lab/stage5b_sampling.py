"""Frozen finite-shot protocol for the Stage 5B Quantum Domino experiment."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from numbers import Integral
from pathlib import Path

import numpy as np

from .deviation import exact_observable_summary
from .dynamic_receiver import prepare_dynamic_receiver_state, run_dynamic_receiver_experiment
from .multispin import partial_trace_subsystems
from .provenance import code_provenance
from .stage5b_statistics import estimate_joint_power, fisher_exact_two_sided, holm_adjust, newcombe_wilson_interval
from .tfim import FieldSchedule


_GROUPS = ("reference", "sender_operation", "positive_control")
_PROTOCOL = "stage5b-quantum-domino-v1"


def _canonical_hash(record: Mapping[str, object]) -> str:
    value = {key: item for key, item in record.items() if key != "preregistration_hash"}
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_preregistration(preregistration: Mapping[str, object]) -> None:
    """Reject unlocked or altered protocol records before any confirmatory draws."""
    if not isinstance(preregistration, Mapping) or preregistration.get("protocol") != _PROTOCOL:
        raise ValueError("unsupported or missing Stage 5B protocol")
    if preregistration.get("locked") is not True:
        raise ValueError("confirmatory sampling requires a locked preregistration")
    expected = preregistration.get("preregistration_hash")
    if not isinstance(expected, str) or len(expected) != 64 or _canonical_hash(preregistration) != expected:
        raise ValueError("preregistration hash does not match its frozen contents")


def _primary_counts(probabilities: Mapping[str, float], shots: int, seed: int,
                    preregistration_hash: str) -> dict:
    if not isinstance(probabilities, Mapping) or set(probabilities) != set(_GROUPS):
        raise ValueError("probabilities must map the three declared scenarios")
    probs = {key: float(probabilities[key]) for key in _GROUPS}
    if any(not np.isfinite(value) or value < 0 or value > 1 for value in probs.values()):
        raise ValueError("scenario probabilities must lie in [0,1]")
    if isinstance(shots, (bool, np.bool_)) or not isinstance(shots, Integral) or shots < 1:
        raise ValueError("shots_per_group must be a positive integer")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not isinstance(preregistration_hash, str) or not preregistration_hash:
        raise ValueError("a frozen preregistration hash is required")

    children = np.random.SeedSequence(int(seed)).spawn(5)
    allocation_rng = np.random.default_rng(children[0])
    shuffled_groups = list(np.asarray(_GROUPS, dtype=object)[allocation_rng.permutation(len(_GROUPS))])
    scenario_to_code = {scenario: f"blind-{index}" for index, scenario in enumerate(shuffled_groups)}
    code_to_scenario = {code: scenario for scenario, code in scenario_to_code.items()}
    ledger = []
    for code_index in range(len(_GROUPS)):
        code = f"blind-{code_index}"
        scenario = code_to_scenario[code]
        rng = np.random.default_rng(children[code_index + 1])
        binary = rng.binomial(1, probs[scenario], size=int(shots))
        for index, selected in enumerate(binary):
            ledger.append({"shot_id": f"shot-{code_index * int(shots) + index:08d}",
                           "blind_group": code, "outcome": 1 if selected else -1})
    shuffle_rng = np.random.default_rng(children[4])
    order = shuffle_rng.permutation(len(ledger))
    blinded_ledger = [ledger[int(index)] for index in order]
    return {"protocol": _PROTOCOL, "preregistration_hash": preregistration_hash,
            "shots_per_group": int(shots), "scenario_to_blind_group": scenario_to_code,
            "blinded_ledger": blinded_ledger,
            "rng": {"root_seed": int(seed), "allocation_spawn_key": list(children[0].spawn_key),
                    "outcome_spawn_keys": [list(child.spawn_key) for child in children[1:4]],
                    "ledger_order_spawn_key": list(children[4].spawn_key),
                    "streams_are_group_label_independent": True}}


def sample_blinded_outcomes(probabilities: Mapping[str, float], shots_per_group: int,
                            seed: int, *, preregistration_hash: str) -> dict:
    """Generate independent outcomes in neutral, shuffled groups, then unblind.

    The ledger itself contains no scenario names and is shuffled before the
    scenario-to-code map is returned. Each row represents one fresh prepared
    system and one projective receiver measurement.
    """
    sampled = _primary_counts(probabilities, shots_per_group, seed, preregistration_hash)
    scenario_to_code = sampled.pop("scenario_to_blind_group")
    sampled["ledger"] = sampled.pop("blinded_ledger")
    sampled["scenario_to_blind_group"] = scenario_to_code
    sampled["counts"] = {}
    inverse = {code: scenario for scenario, code in scenario_to_code.items()}
    for row in sampled["ledger"]:
        scenario = inverse[row["blind_group"]]
        counts = sampled["counts"].setdefault(scenario, {"plus": 0, "minus": 0})
        counts["plus" if row["outcome"] == 1 else "minus"] += 1
    return sampled


def analyze_primary_outcomes(sample: Mapping[str, object], preregistration: Mapping[str, object]) -> dict:
    """Unblind and analyze the two prespecified Fisher/Holm comparisons."""
    verify_preregistration(preregistration)
    if not isinstance(sample, Mapping) or sample.get("preregistration_hash") != preregistration["preregistration_hash"]:
        raise ValueError("sample does not belong to this locked preregistration")
    if tuple(preregistration.get("primary_contrasts", ())) != (
            "sender_operation_vs_reference", "positive_control_vs_reference"):
        raise ValueError("primary contrast family does not match the approved protocol")
    counts = sample.get("counts")
    if not isinstance(counts, Mapping) or set(counts) != set(_GROUPS):
        raise ValueError("unblinded counts must contain all three groups")
    shots = sample.get("shots_per_group")
    if isinstance(shots, bool) or not isinstance(shots, Integral) or shots < 1:
        raise ValueError("sample is missing a valid shots_per_group")
    for group in _GROUPS:
        row = counts[group]
        if not isinstance(row, Mapping) or row.get("plus", -1) + row.get("minus", -1) != shots:
            raise ValueError("every group must contain the declared number of outcomes")
    alpha = float(preregistration["criteria"]["familywise_alpha"])
    ref = int(counts["reference"]["plus"])
    pairs = {
        "sender_operation_vs_reference": (int(counts["sender_operation"]["plus"]), ref),
        "positive_control_vs_reference": (int(counts["positive_control"]["plus"]), ref),
    }
    raw = [fisher_exact_two_sided(treat, int(shots), control, int(shots)) for treat, control in pairs.values()]
    adjusted = holm_adjust(raw)
    contrasts = {}
    for (name, (treatment_plus, control_plus)), raw_p, adjusted_p in zip(pairs.items(), raw, adjusted):
        interval = newcombe_wilson_interval(treatment_plus, int(shots), control_plus, int(shots), .995)
        effect = treatment_plus / shots - control_plus / shots
        contrasts[name] = {
            "treatment_plus": treatment_plus, "treatment_minus": int(shots) - treatment_plus,
            "control_plus": control_plus, "control_minus": int(shots) - control_plus,
            "treatment_probability": treatment_plus / shots, "control_probability": control_plus / shots,
            "difference_treatment_minus_control": effect,
            "difference_99_5_percent_newcombe_wilson_interval": interval,
            "raw_p_value": raw_p, "holm_adjusted_p_value": adjusted_p,
            "familywise_alpha": alpha, "detected": bool(adjusted_p <= alpha),
            "interpretation": "difference_detected_at_preregistered_sensitivity" if adjusted_p <= alpha else "no_difference_detected_at_this_sensitivity",
        }
    return {"test": "two-sided Fisher exact with Holm adjustment across two primary contrasts",
            "shared_control_shots": int(shots), "alpha": alpha, "contrasts": contrasts,
            "non_rejection_limit": "Non-rejection does not exclude effects below the reported interval and sensitivity.",
            "preregistration_hash": preregistration["preregistration_hash"]}


def _probability_plus(full_state: np.ndarray, physical_site: int) -> float:
    rho_local = partial_trace_subsystems(full_state, [physical_site])
    z = np.diag([1.0, -1.0]).astype(complex)
    return float(exact_observable_summary(rho_local, z)["distribution"][1.0])


def _preflight_receiver(simulations: int, seed: int, shots: int) -> dict:
    n_spins, J, h, final_time = 4, 1.0e6, .8e6, 10.0e-6
    times = np.linspace(0, final_time, 101)
    initial = prepare_dynamic_receiver_state(n_spins, 1)
    identity = [np.eye(2, dtype=complex)]
    sigma_x = np.array([[0, 1], [1, 0]], dtype=complex)
    solver_options = {"rtol": 1e-10, "atol": 1e-12, "max_steps": 100000}
    common = {"n_spins": n_spins, "J": J, "h_schedule": FieldSchedule.constant(h),
              "times_s": times, "initial_state": initial, "sender_kraus_operators": identity,
              "solver_options": solver_options}
    baseline = run_dynamic_receiver_experiment({**common, "local_controls": {}})
    sender = run_dynamic_receiver_experiment({**common, "sender_kraus_operators": [sigma_x], "local_controls": {}})
    if baseline["status"] != "success" or sender["status"] != "success":
        raise RuntimeError("preflight receiver evolution failed")
    baseline_probabilities = np.array([_probability_plus(state, 3) for state in baseline["scenarios"]["reference"]["full_states"]])
    selected = None
    max_frequency = max(abs(J), abs(h))
    for ratio in (.005, .01, .02, .04, .06, .08, .10):
        amplitude = ratio * max_frequency
        pulse = FieldSchedule.gaussian(amplitude, final_time / 2, final_time / 10)
        positive = run_dynamic_receiver_experiment({**common, "local_controls": {2: pulse}})
        if positive["status"] != "success":
            raise RuntimeError(f"positive-control preflight failed: {positive['error']}")
        values = np.array([_probability_plus(state, 3) for state in positive["scenarios"]["positive_control"]["full_states"]])
        shifts = values - baseline_probabilities
        qualifying = np.flatnonzero(np.abs(shifts) >= .025)
        if qualifying.size:
            index = int(qualifying[0])
            selected = {"amplitude_ratio": ratio, "amplitude_s_inverse": amplitude,
                        "center_s": final_time / 2, "width_s": final_time / 10,
                        "time_index": index, "time_s": float(times[index]),
                        "reference_probability_plus": float(baseline_probabilities[index]),
                        "positive_control_probability_plus": float(values[index]),
                        "difference_probability_plus": float(shifts[index]),
                        "positive_control_trace_distance": positive["metrics"]["positive_control_trace_distance"][index],
                        "solver_diagnostics": positive["scenarios"]["positive_control"]["solver_diagnostics"]}
            break
    if selected is None:
        raise RuntimeError("no pulse on the frozen candidate grid met the 0.025 model probability-shift threshold")
    index = selected["time_index"]
    sender_probability = _probability_plus(sender["scenarios"]["sender_operation"]["full_states"][index], 3)
    reference_probability = selected["reference_probability_plus"]
    if abs(sender_probability - reference_probability) > 1e-8:
        raise RuntimeError("sender no-signaling preflight exceeded trace/observable tolerance")
    # Independently tighten solver tolerances and compare complete final
    # density states; local step acceptance is not a global accuracy check.
    tight_options = {"rtol": 1e-12, "atol": 1e-14, "max_steps": 200000}
    comparison_time = selected["time_s"]
    tight_baseline = run_dynamic_receiver_experiment({**common, "times_s": [comparison_time],
                                                       "solver_options": tight_options,
                                                       "local_controls": {}})
    selected_pulse = FieldSchedule.gaussian(selected["amplitude_s_inverse"],
                                             selected["center_s"], selected["width_s"])
    tight_positive = run_dynamic_receiver_experiment({**common, "times_s": [comparison_time],
                                                       "solver_options": tight_options,
                                                       "local_controls": {2: selected_pulse}})
    if tight_baseline["status"] != "success" or tight_positive["status"] != "success":
        raise RuntimeError("global-convergence refinement failed")
    convergence = {}
    for name, loose, refined in (("reference", baseline, tight_baseline),
                                 ("positive_control", run_dynamic_receiver_experiment(
                                     {**common, "local_controls": {2: selected_pulse}}), tight_positive)):
        if loose["status"] != "success":
            raise RuntimeError(f"global-convergence baseline failed for {name}")
        left = np.asarray(loose["scenarios"][name]["full_states"][index], complex)
        right = np.asarray(refined["scenarios"][name]["full_states"][0], complex)
        rho_left = np.outer(left, left.conj()) if left.ndim == 1 else left
        rho_right = np.outer(right, right.conj()) if right.ndim == 1 else right
        delta = (rho_left-rho_right + (rho_left-rho_right).conj().T)/2
        trace_error = float(.5*np.sum(np.abs(np.linalg.eigvalsh(delta))))
        local_error = float(abs(_probability_plus(left, 3)-_probability_plus(right, 3)))
        convergence[name] = {"loose_solver": loose["scenarios"][name]["solver_diagnostics"],
                             "refined_solver": refined["scenarios"][name]["solver_diagnostics"],
                             "global_full_state_trace_distance": trace_error,
                             "global_primary_probability_difference": local_error}
        if trace_error > 1e-8 or local_error > 1e-8:
            raise RuntimeError(f"global convergence threshold exceeded for {name}")
    selected["global_convergence"] = {"status": "passed", "comparison_time_s": comparison_time,
                                      "threshold": 1e-8, "branches": convergence,
                                      "independent_of_local_step_error": True}
    direction = 1 if reference_probability <= .975 else -1
    sender_design_probability = float(np.clip(reference_probability + direction * .025, 0, 1))
    power_seed = int(seed) ^ 0x5A17C9E3
    power = estimate_joint_power([reference_probability, sender_design_probability,
                                  selected["positive_control_probability_plus"]], shots,
                                 alpha=.01, simulations=simulations, seed=power_seed)
    selected_shots = int(shots)
    power_runs = [power]
    while power["joint_power_95_percent_wilson_interval"][0] < .90 and selected_shots < 100000:
        selected_shots = int(np.ceil(selected_shots * 1.10))
        power = estimate_joint_power([reference_probability, sender_design_probability,
                                      selected["positive_control_probability_plus"]], selected_shots,
                                     alpha=.01, simulations=simulations, seed=power_seed)
        power_runs.append(power)
    if power["joint_power_95_percent_wilson_interval"][0] < .90:
        raise RuntimeError("target joint power was not reached by 100000 shots per group")
    sender_diag = sender["scenarios"]["sender_operation"]["solver_diagnostics"]
    selected["sender_probability_plus"] = sender_probability
    selected["receiver_dynamics"] = {"baseline_final_sigma_z": baseline["scenarios"]["reference"]["receiver_observables"]["sigma_z"][-1].tolist(),
                                      "baseline_solver": baseline["scenarios"]["reference"]["solver_diagnostics"],
                                      "sender_solver": sender_diag}
    selected["power_design_sender_alternative_probability"] = sender_design_probability
    selected["power_seed"] = power_seed
    selected["power_runs"] = power_runs
    selected["selected_shots_per_group"] = selected_shots
    return {"configuration": {"n_spins": n_spins, "sender_site": 0, "receiver_sites": [1, 2, 3],
                               "entangled_receiver_site": 1, "J_s_inverse": J, "h_s_inverse": h,
                               "final_time_s": final_time, "time_grid_s": times.tolist(),
                               "sender_operation": "Pauli sigma_x unitary on site 0",
                               "primary_observable": "Pauli sigma_z", "primary_receiver_site": 3,
                               "pulse_site": 2, "pulse_model": "Gaussian additive transverse field; existing Stage 5A schedule",
                               "pulse_candidates_ratio_of_max_abs_J_h": [.005, .01, .02, .04, .06, .08, .10],
                               "pulse_selection_rule": "lowest amplitude ratio meeting |delta p(+1)| >= 0.025; earliest time on the fixed 101-point grid",
                               "solver_options": solver_options},
            "preflight": selected}


def lock_quantum_domino_protocol(directory: str | Path, *, simulations: int = 200000,
                                 seed: int = 20261017, shots_per_group: int = 14000) -> dict:
    """Run deterministic physics/power preflight and atomically lock protocol.

    This function draws no experimental outcomes. Statistical power uses
    independent Monte Carlo counts for the predeclared Fisher/Holm design.
    """
    if isinstance(simulations, (bool, np.bool_)) or not isinstance(simulations, Integral) or simulations < 200000:
        raise ValueError("protocol power verification requires at least 200000 Monte Carlo replicates")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if isinstance(shots_per_group, (bool, np.bool_)) or not isinstance(shots_per_group, Integral) or shots_per_group < 1:
        raise ValueError("shots_per_group must be a positive integer")
    preflight = _preflight_receiver(int(simulations), int(seed), int(shots_per_group))
    git_revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    record = {"schema_version": 1, "protocol": _PROTOCOL, "locked": True,
              "code_revision_at_lock": git_revision,
              "code_provenance_at_lock": code_provenance(Path(__file__).resolve().parents[1]),
              "python_version": platform.python_version(),
              "numpy_version": np.__version__, "configuration": preflight["configuration"],
              "preflight": preflight["preflight"],
              "primary_contrasts": ["sender_operation_vs_reference", "positive_control_vs_reference"],
              "criteria": {"familywise_alpha": .01, "test": "two-sided Fisher exact with Holm adjustment",
                           "shots_per_group": preflight["preflight"]["selected_shots_per_group"],
                           "minimum_probability_difference_for_sender_design_power": .025,
                           "target_joint_power": .90, "power_mc_simulations": int(simulations),
                           "confidence_interval": "99.5% two-sided Newcombe-Wilson per primary contrast",
                           "pulse_effect_preflight_minimum_absolute_probability_shift": .025,
                           "exclusions": "none after unblinding; only failures specified before sampling"},
              "seed_policy": {"power_seed": preflight["preflight"]["power_seed"],
                              "confirmatory_sampling_seed": int(seed) + 1,
                              "independent_replication_seed": int(seed) + 2,
                              "treatment_labels_not_used_to_derive_random_streams": True}}
    record["preregistration_hash"] = _canonical_hash(record)
    target = Path(directory) / "stage5b_quantum_domino_v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, target)
    return {"preregistration": record, "path": str(target), "status": "locked_before_confirmatory_sampling"}


def run_quantum_domino_primary_sampling(preregistration: Mapping[str, object], *, seed: int | None = None) -> dict:
    """Run the frozen 3-group primary sample and analyze only after unblinding."""
    verify_preregistration(preregistration)
    config = preregistration["configuration"]
    preflight = preregistration["preflight"]
    criteria = preregistration["criteria"]
    n = int(config["n_spins"])
    initial = prepare_dynamic_receiver_state(n, int(config["entangled_receiver_site"]))
    h_schedule = FieldSchedule.constant(float(config["h_s_inverse"]))
    times = [float(config["time_grid_s"][preflight["time_index"]])]
    sigma_x = np.array([[0, 1], [1, 0]], dtype=complex)
    pulse = FieldSchedule.gaussian(float(preflight["amplitude_s_inverse"]),
                                   float(preflight["center_s"]), float(preflight["width_s"]))
    common = {"n_spins": n, "J": float(config["J_s_inverse"]), "h_schedule": h_schedule,
              "times_s": times, "initial_state": initial, "solver_options": config["solver_options"]}
    reference = run_dynamic_receiver_experiment({**common, "local_controls": {}})
    sender = run_dynamic_receiver_experiment({**common, "sender_kraus_operators": [sigma_x], "local_controls": {}})
    positive = run_dynamic_receiver_experiment({**common, "local_controls": {int(config["pulse_site"]): pulse}})
    if any(result["status"] != "success" for result in (reference, sender, positive)):
        raise RuntimeError("confirmatory-sample physical prediction failed under the locked model")
    probabilities = {
        "reference": _probability_plus(reference["scenarios"]["reference"]["full_states"][0], int(config["primary_receiver_site"])),
        "sender_operation": _probability_plus(sender["scenarios"]["sender_operation"]["full_states"][0], int(config["primary_receiver_site"])),
        "positive_control": _probability_plus(positive["scenarios"]["positive_control"]["full_states"][0], int(config["primary_receiver_site"])),
    }
    expected_probabilities = {"reference": preflight["reference_probability_plus"],
                              "sender_operation": preflight["sender_probability_plus"],
                              "positive_control": preflight["positive_control_probability_plus"]}
    if any(abs(probabilities[key]-expected_probabilities[key]) > 1e-8 for key in probabilities):
        raise RuntimeError("confirmatory input does not reproduce every locked model prediction")
    sample_seed = int(preregistration["seed_policy"]["confirmatory_sampling_seed"] if seed is None else seed)
    sample = sample_blinded_outcomes(probabilities, int(criteria["shots_per_group"]), sample_seed,
                                     preregistration_hash=preregistration["preregistration_hash"])
    analysis = analyze_primary_outcomes(sample, preregistration)
    return {"status": "success", "preregistration_hash": preregistration["preregistration_hash"],
            "probabilities": probabilities, "sampling": sample, "analysis": analysis,
            "exact_solver_diagnostics": {"reference": reference["scenarios"]["reference"]["solver_diagnostics"],
                                         "sender_operation": sender["scenarios"]["sender_operation"]["solver_diagnostics"],
                                         "positive_control": positive["scenarios"]["positive_control"]["solver_diagnostics"]}}
