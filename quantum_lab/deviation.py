"""Exact predictions and finite-shot summaries for declared observables.

This module analyzes states supplied by the quantum core. It does not build
Hamiltonians or propagate states. Sequential measurements apply the Lüders
state update for the first projective result before the second measurement.
"""

from __future__ import annotations

from numbers import Integral
from typing import Mapping, Sequence

import numpy as np


def _density_matrix(state: np.ndarray) -> np.ndarray:
    value = np.asarray(state, dtype=complex)
    if value.ndim == 1:
        if value.size < 2 or value.size > 64 or value.size & (value.size - 1):
            raise ValueError("state ket dimension must be 2**N for N=1..6")
        if not np.all(np.isfinite(value)) or not np.isclose(np.vdot(value, value), 1, atol=1e-10, rtol=0):
            raise ValueError("state ket must be finite and normalized")
        return np.outer(value, value.conj())
    if value.ndim != 2 or value.shape[0] != value.shape[1] or value.shape[0] < 2 or value.shape[0] > 64 or value.shape[0] & (value.shape[0] - 1):
        raise ValueError("state density dimension must be 2**N for N=1..6")
    if not np.all(np.isfinite(value)) or np.linalg.norm(value - value.conj().T) > 1e-10:
        raise ValueError("state density must be finite and Hermitian")
    if abs(np.trace(value) - 1) > 1e-10:
        raise ValueError("state density must have unit trace")
    if np.linalg.eigvalsh((value + value.conj().T) / 2).min() < -1e-10:
        raise ValueError("state density must be positive semidefinite")
    return value


def _observable(observable: np.ndarray, dimension: int) -> np.ndarray:
    value = np.asarray(observable, dtype=complex)
    if value.shape != (dimension, dimension) or not np.all(np.isfinite(value)):
        raise ValueError("observable must be finite and match the state dimension")
    if np.linalg.norm(value - value.conj().T) > 1e-10:
        raise ValueError("observable must be Hermitian")
    return (value + value.conj().T) / 2


def _projectors(observable: np.ndarray) -> list[tuple[float, np.ndarray]]:
    values, vectors = np.linalg.eigh(observable)
    result: list[tuple[float, np.ndarray]] = []
    index = 0
    while index < len(values):
        stop = index + 1
        while stop < len(values) and abs(values[stop] - values[index]) <= 1e-10:
            stop += 1
        block = vectors[:, index:stop]
        result.append((float(np.mean(values[index:stop])), block @ block.conj().T))
        index = stop
    return result


def _distribution(rho: np.ndarray, observable: np.ndarray) -> dict[float, float]:
    distribution = {}
    for value, projector in _projectors(observable):
        probability = float(np.trace(rho @ projector).real)
        if probability < -1e-10:
            raise ValueError("observable produced a negative Born probability")
        distribution[value] = max(0.0, probability)
    if abs(sum(distribution.values()) - 1) > 1e-10:
        raise ValueError("Born probabilities do not sum to one")
    return distribution


def exact_observable_summary(state: np.ndarray, observable: np.ndarray) -> dict:
    """Return exact spectral probabilities, mean, and variance for ``O``."""
    rho = _density_matrix(state)
    operator = _observable(observable, rho.shape[0])
    distribution = _distribution(rho, operator)
    mean = float(np.trace(rho @ operator).real)
    second_moment = float(np.trace(rho @ operator @ operator).real)
    return {"kind": "exact", "mean": mean, "second_moment": second_moment,
            "variance": max(0.0, second_moment - mean * mean),
            "distribution": distribution}


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    proportion = successes / trials
    denominator = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / denominator
    half = z * np.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)) / denominator
    return float(max(0.0, center - half)), float(min(1.0, center + half))


def sample_observable(state: np.ndarray, observable: np.ndarray, shots: int,
                      rng: np.random.Generator) -> dict:
    """Draw independent Born outcomes for independent preparations."""
    if isinstance(shots, (bool, np.bool_)) or not isinstance(shots, Integral) or shots < 1:
        raise ValueError("shots must be a positive integer")
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a NumPy Generator supplied by the caller")
    exact = exact_observable_summary(state, observable)
    outcomes = np.array(list(exact["distribution"]), dtype=float)
    probabilities = np.array(list(exact["distribution"].values()), dtype=float)
    samples = rng.choice(outcomes, size=int(shots), p=probabilities)
    counts = {float(value): int(np.count_nonzero(samples == value)) for value in outcomes}
    intervals = {value: _wilson_interval(count, int(shots)) for value, count in counts.items()}
    return {"kind": "sample", "independent_preparations": int(shots),
            "outcomes": samples, "counts": counts, "born_distribution": exact["distribution"],
            "sample_mean": float(np.mean(samples)),
            "sample_variance": float(np.var(samples, ddof=1)) if shots > 1 else None,
            "probability_95_percent_wilson_intervals": intervals}


def fit_explicit_model(times_s: Sequence[float], values: Sequence[float], model: str,
                       initial_parameters: Mapping[str, float]) -> dict:
    """Fit an explicitly requested sinusoid at a fixed angular frequency.

    The frequency is supplied as ``omega_rad_s``; this linear least-squares
    fit estimates the sine/cosine coefficients and derives amplitude/phase.
    No automatic model or frequency search is performed.
    """
    if model != "sinusoid":
        raise ValueError("supported explicit fit model is 'sinusoid'")
    if not isinstance(initial_parameters, Mapping) or "omega_rad_s" not in initial_parameters:
        raise ValueError("sinusoid fit requires a declared omega_rad_s")
    omega = float(initial_parameters["omega_rad_s"])
    if not np.isfinite(omega) or omega <= 0:
        raise ValueError("omega_rad_s must be finite and positive")
    times, observations = np.asarray(times_s, dtype=float), np.asarray(values, dtype=float)
    if times.ndim != 1 or observations.shape != times.shape or len(times) < 4:
        raise ValueError("fit requires at least four paired one-dimensional samples")
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(observations)) or np.any(np.diff(times) <= 0):
        raise ValueError("fit samples must be finite with strictly increasing times")
    design = np.column_stack((np.sin(omega * times), np.cos(omega * times), np.ones_like(times)))
    if np.linalg.matrix_rank(design) < 3:
        raise ValueError("fit design is rank deficient at the declared frequency")
    coefficients, _, _, _ = np.linalg.lstsq(design, observations, rcond=None)
    residuals = observations - design @ coefficients
    dof = len(times) - 3
    covariance = (float(residuals @ residuals) / dof) * np.linalg.inv(design.T @ design)
    sine, cosine, offset = map(float, coefficients)
    amplitude = float(np.hypot(sine, cosine))
    phase = float(np.arctan2(cosine, sine))
    if amplitude > np.finfo(float).eps:
        grad_amp = np.array([sine / amplitude, cosine / amplitude, 0.0])
        grad_phase = np.array([-cosine / amplitude**2, sine / amplitude**2, 0.0])
        amp_error = float(np.sqrt(max(0.0, grad_amp @ covariance @ grad_amp)))
        phase_error = float(np.sqrt(max(0.0, grad_phase @ covariance @ grad_phase)))
    else:
        amp_error = phase_error = float("nan")
    return {"model": model, "fixed_omega_rad_s": omega,
            "parameters": {"amplitude": amplitude, "phase_rad": phase, "offset": offset},
            "standard_errors": {"amplitude": amp_error, "phase_rad": phase_error,
                                "offset": float(np.sqrt(max(0.0, covariance[2, 2])))},
            "residuals": residuals, "residual_sum_squares": float(residuals @ residuals),
            "degrees_of_freedom": dof, "covariance_coefficients_sine_cosine_offset": covariance}


def spectrum_uniform_grid(times_s: Sequence[float], values: Sequence[float], window: str) -> dict:
    """Return a one-sided amplitude spectrum for a uniform time grid."""
    times, signal = np.asarray(times_s, dtype=float), np.asarray(values, dtype=float)
    if times.ndim != 1 or signal.shape != times.shape or len(times) < 2:
        raise ValueError("spectrum requires at least two paired one-dimensional samples")
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(signal)):
        raise ValueError("spectrum inputs must be finite")
    steps = np.diff(times)
    dt = float(steps[0])
    if dt <= 0 or np.any(np.abs(steps - dt) > max(1e-12, abs(dt) * 1e-9)):
        raise ValueError("spectrum requires a strictly increasing uniform time grid")
    if window == "rectangular":
        weights = np.ones(len(signal))
    elif window == "hann":
        weights = np.hanning(len(signal))
    else:
        raise ValueError("window must be 'rectangular' or 'hann'")
    centered = signal - np.mean(signal)
    transform = np.fft.rfft(centered * weights)
    denominator = float(np.sum(weights))
    if denominator <= 0:
        raise ValueError("selected window has zero normalization")
    amplitudes = np.abs(transform) / denominator
    if len(signal) % 2 == 0:
        amplitudes[1:-1] *= 2
    else:
        amplitudes[1:] *= 2
    frequencies = np.fft.rfftfreq(len(signal), dt)
    peak_index = int(np.argmax(amplitudes[1:]) + 1) if len(amplitudes) > 1 else 0
    return {"frequencies_hz": frequencies, "amplitudes": amplitudes,
            "phases_rad": np.angle(transform), "peak_index": peak_index,
            "peak_frequency_hz": float(frequencies[peak_index]), "dt_s": dt,
            "frequency_resolution_hz": float(1 / (len(signal) * dt)),
            "window": window, "detrending": "subtract_sample_mean",
            "normalization": "one-sided peak amplitude divided by sum(window); DC and Nyquist undoubled"}


def sequential_measurement_distribution(state_at_t1: np.ndarray, observable_1: np.ndarray,
                                        propagator_t1_t2: np.ndarray, observable_2: np.ndarray) -> dict:
    """Compute exact sequential projective outcomes with Lüders back-action."""
    rho = _density_matrix(state_at_t1)
    first = _observable(observable_1, rho.shape[0])
    second = _observable(observable_2, rho.shape[0])
    unitary = np.asarray(propagator_t1_t2, dtype=complex)
    if unitary.shape != rho.shape or not np.all(np.isfinite(unitary)):
        raise ValueError("propagator must be finite and match the state dimension")
    if np.linalg.norm(unitary.conj().T @ unitary - np.eye(len(rho))) > 1e-10:
        raise ValueError("propagator must be unitary")
    first_marginal = []
    second_sums: dict[float, float] = {}
    joint = []
    for first_value, projector in _projectors(first):
        probability_1 = float(np.trace(rho @ projector).real)
        if probability_1 <= 1e-15:
            continue
        updated = projector @ rho @ projector / probability_1
        at_t2 = unitary @ updated @ unitary.conj().T
        first_marginal.append({"outcome": first_value, "probability": probability_1})
        for second_value, probability_2 in _distribution(at_t2, second).items():
            probability = probability_1 * probability_2
            joint.append({"first": first_value, "second": second_value, "probability": probability})
            second_sums[second_value] = second_sums.get(second_value, 0.0) + probability
    return {"kind": "exact_sequential", "joint_outcomes": joint,
            "first_marginal": first_marginal,
            "second_marginal": [{"outcome": key, "probability": value} for key, value in sorted(second_sums.items())],
            "state_update": "Luders_projector_update_after_first_measurement",
            "independent_preparations_per_sequence": 1}


def sample_sequential_measurements(state_at_t1: np.ndarray, observable_1: np.ndarray,
                                   propagator_t1_t2: np.ndarray, observable_2: np.ndarray,
                                   shots: int, rng: np.random.Generator) -> dict:
    """Sample paired two-time sequences; each pair comes from one preparation."""
    if isinstance(shots, (bool, np.bool_)) or not isinstance(shots, Integral) or shots < 1:
        raise ValueError("shots must be a positive integer")
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a NumPy Generator supplied by the caller")
    exact = sequential_measurement_distribution(state_at_t1, observable_1, propagator_t1_t2, observable_2)
    probabilities = np.array([row["probability"] for row in exact["joint_outcomes"]], dtype=float)
    outcomes = np.array([[row["first"], row["second"]] for row in exact["joint_outcomes"]], dtype=float)
    selections = rng.choice(len(outcomes), size=int(shots), p=probabilities)
    samples = outcomes[selections]
    joint_counts = []
    for row in exact["joint_outcomes"]:
        count = int(np.count_nonzero((samples[:, 0] == row["first"]) & (samples[:, 1] == row["second"])))
        joint_counts.append({"first": row["first"], "second": row["second"], "count": count})
    return {"kind": "sampled_sequential", "outcomes": samples, "joint_counts": joint_counts,
            "independent_preparations": int(shots), "state_update": exact["state_update"],
            "theoretical_joint_distribution": exact["joint_outcomes"]}
