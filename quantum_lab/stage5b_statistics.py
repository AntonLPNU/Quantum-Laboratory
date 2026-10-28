"""Stage 5B statistics, kept independent from the published-data analyzers.

Fisher's conditional 2x2 test and Holm step-down adjustment are implemented
here for receiver experiment outcomes. No Hensen analysis function is called
or modified by this module.
"""

from __future__ import annotations

from functools import lru_cache
from math import exp, fsum, lgamma, log
from numbers import Integral
from statistics import NormalDist
from typing import Sequence

import numpy as np


def _validate_table(successes_a: int, trials_a: int, successes_b: int, trials_b: int) -> tuple[int, int, int, int]:
    values = (successes_a, trials_a, successes_b, trials_b)
    if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) for value in values):
        raise TypeError("successes and trials must be integers")
    a, na, b, nb = map(int, values)
    if na < 1 or nb < 1 or not 0 <= a <= na or not 0 <= b <= nb:
        raise ValueError("success counts must lie between zero and positive trial counts")
    return a, na, b, nb


def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)


def _log_hypergeom(k: int, population: int, successes: int, draws: int) -> float:
    return (_log_choose(successes, k) + _log_choose(population - successes, draws - k)
            - _log_choose(population, draws))


def _log_ratio_right(k: int, population: int, successes: int, draws: int) -> float:
    """log(P(k+1)/P(k)); stable even when two large log-factorials cancel."""
    return (log(successes - k) + log(draws - k) - log(k + 1)
            - log(population - successes - draws + k + 1))


def _log_ratio_left(k: int, population: int, successes: int, draws: int) -> float:
    """log(P(k-1)/P(k))."""
    return (log(k) + log(population - successes - draws + k)
            - log(successes - k + 1) - log(draws - k + 1))


def _sum_left(start: int, low: int, log_probability: float, population: int,
              successes: int, draws: int) -> float:
    if start < low:
        return 0.0
    term = exp(log_probability)
    terms = [term]
    for k in range(start, low, -1):
        ratio = (k * (population - successes - draws + k)
                 / ((successes - k + 1) * (draws - k + 1)))
        term *= ratio
        terms.append(term)
        if ratio < .5 and term < fsum(terms) * 1e-16:
            break
    return fsum(terms)


def _sum_right(start: int, high: int, log_probability: float, population: int,
               successes: int, draws: int) -> float:
    if start > high:
        return 0.0
    term = exp(log_probability)
    terms = [term]
    for k in range(start, high):
        ratio = ((successes - k) * (draws - k)
                 / ((k + 1) * (population - successes - draws + k + 1)))
        term *= ratio
        terms.append(term)
        if ratio < .5 and term < fsum(terms) * 1e-16:
            break
    return fsum(terms)


@lru_cache(maxsize=500_000)
def _fisher_cached(successes_a: int, trials_a: int, successes_b: int, trials_b: int) -> float:
    population = trials_a + trials_b
    total_successes = successes_a + successes_b
    low = max(0, trials_a - (population - total_successes))
    high = min(trials_a, total_successes)
    observed_log_p = _log_hypergeom(successes_a, population, total_successes, trials_a)
    mode = min(high, max(low, ((trials_a + 1) * (total_successes + 1)) // (population + 2)))
    mode_log_p = _log_hypergeom(mode, population, total_successes, trials_a)
    # If the observed table is modal, every possible table has probability no
    # greater than it, so probability ordering returns one.
    if successes_a == mode or (successes_a + 1 == mode and
                                abs(_log_ratio_right(successes_a, population, total_successes, trials_a)) <= 1e-12):
        return 1.0
    if successes_a < mode:
        lower_tail = _sum_left(successes_a, low, observed_log_p, population, total_successes, trials_a)
        log_ratio, cutoff = 0.0, None
        for k in range(successes_a, high):
            log_ratio += _log_ratio_right(k, population, total_successes, trials_a)
            if k + 1 >= mode and log_ratio <= 1e-12:
                cutoff = k + 1
                break
        upper_tail = 0.0 if cutoff is None else _sum_right(
            cutoff, high, _log_hypergeom(cutoff, population, total_successes, trials_a),
            population, total_successes, trials_a)
    else:
        upper_tail = _sum_right(successes_a, high, observed_log_p, population, total_successes, trials_a)
        log_ratio, cutoff = 0.0, None
        for k in range(successes_a, low, -1):
            log_ratio += _log_ratio_left(k, population, total_successes, trials_a)
            if k - 1 <= mode and log_ratio <= 1e-12:
                cutoff = k - 1
                break
        lower_tail = 0.0 if cutoff is None else _sum_left(
            cutoff, low, _log_hypergeom(cutoff, population, total_successes, trials_a),
            population, total_successes, trials_a)
    return float(min(1.0, max(0.0, lower_tail + upper_tail)))


def fisher_exact_two_sided(successes_a: int, trials_a: int, successes_b: int, trials_b: int) -> float:
    """Fisher–Irwin two-sided conditional test by probability ordering."""
    return _fisher_cached(*_validate_table(successes_a, trials_a, successes_b, trials_b))


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Return Holm step-down adjusted p-values in the caller's input order."""
    if not isinstance(p_values, Sequence) or isinstance(p_values, (str, bytes)) or len(p_values) == 0:
        raise ValueError("p_values must be a nonempty ordered sequence")
    values = [float(value) for value in p_values]
    if any(not np.isfinite(value) or value < 0 or value > 1 for value in values):
        raise ValueError("p-values must be finite and between zero and one")
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted = [0.0] * len(values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(values) - rank) * values[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def analyze_secondary_family(p_values: Mapping[str, float]) -> dict:
    """Apply a distinct Holm correction to one explicitly grouped secondary family."""
    from collections.abc import Mapping as MappingABC
    if not isinstance(p_values, MappingABC) or not p_values:
        raise ValueError("secondary p_values must be a nonempty name-to-p-value mapping")
    names = list(p_values)
    raw = [float(p_values[name]) for name in names]
    adjusted = holm_adjust(raw)
    return {"method": "Holm adjustment; exploratory family", "family_size": len(names),
            "results": {name: {"raw_p_value": p, "holm_adjusted_p_value": q}
                        for name, p, q in zip(names, raw, adjusted)}}


def _wilson(successes: int, trials: int, confidence: float) -> tuple[float, float]:
    if successes == trials:
        z = NormalDist().inv_cdf((1 + confidence) / 2)
        denominator = 1 + z * z / trials
        center = (1 + z * z / (2 * trials)) / denominator
        half = z * np.sqrt(z * z / (4 * trials * trials)) / denominator
        return float(max(0.0, center - half)), 1.0
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * np.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return float(max(0, center - half)), float(min(1, center + half))


def newcombe_wilson_interval(successes_a: int, trials_a: int, successes_b: int, trials_b: int,
                             confidence: float = .995) -> tuple[float, float]:
    """Newcombe's unpaired difference interval built from Wilson intervals."""
    a, na, b, nb = _validate_table(successes_a, trials_a, successes_b, trials_b)
    if not np.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must lie strictly between zero and one")
    pa, pb = a / na, b / nb
    la, ua = _wilson(a, na, confidence)
    lb, ub = _wilson(b, nb, confidence)
    difference = pa - pb
    lower = difference - np.sqrt((pa - la) ** 2 + (ub - pb) ** 2)
    upper = difference + np.sqrt((ua - pa) ** 2 + (pb - lb) ** 2)
    return float(max(-1, lower)), float(min(1, upper))


def _wilson_rate(successes: int, trials: int, confidence: float = .95) -> tuple[float, float]:
    return _wilson(successes, trials, confidence)


def estimate_joint_power(probabilities: Sequence[float], shots_per_group: int, *, alpha: float,
                         simulations: int, seed: int) -> dict:
    """Estimate Holm family-wise power with one shared control group.

    ``probabilities`` is ordered as (control, treatment 1, treatment 2).
    Each replicate independently draws one control count and two treatment
    counts, applies the exact Fisher test to both contrasts, then Holm.
    """
    if not isinstance(probabilities, Sequence) or len(probabilities) != 3:
        raise ValueError("probabilities must contain control and two treatment rates")
    probs = tuple(float(value) for value in probabilities)
    if any(not np.isfinite(value) or value < 0 or value > 1 for value in probs):
        raise ValueError("probabilities must be finite and between zero and one")
    if isinstance(shots_per_group, (bool, np.bool_)) or not isinstance(shots_per_group, Integral) or shots_per_group < 1:
        raise ValueError("shots_per_group must be a positive integer")
    if isinstance(simulations, (bool, np.bool_)) or not isinstance(simulations, Integral) or simulations < 1:
        raise ValueError("simulations must be a positive integer")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    shots, repetitions = int(shots_per_group), int(simulations)
    rng = np.random.default_rng(int(seed))
    control = rng.binomial(shots, probs[0], size=repetitions)
    treatment_1 = rng.binomial(shots, probs[1], size=repetitions)
    treatment_2 = rng.binomial(shots, probs[2], size=repetitions)
    rejected_1 = rejected_2 = rejected_family = rejected_joint = 0
    for c, t1, t2 in zip(control, treatment_1, treatment_2):
        p1 = fisher_exact_two_sided(int(c), shots, int(t1), shots)
        p2 = fisher_exact_two_sided(int(c), shots, int(t2), shots)
        adjusted = holm_adjust((p1, p2))
        first, second = adjusted[0] <= alpha, adjusted[1] <= alpha
        rejected_1 += first
        rejected_2 += second
        rejected_family += first or second
        rejected_joint += first and second
    ci = _wilson_rate(rejected_family, repetitions)
    joint_ci = _wilson_rate(rejected_joint, repetitions)
    joint_power = rejected_joint / repetitions
    return {"method": "Monte Carlo shared-control, two-sided Fisher exact tests, Holm FWER",
            "probabilities_control_treatment1_treatment2": probs,
            "shots_per_group": shots, "alpha": float(alpha), "simulations": repetitions,
            "seed": int(seed), "primary_power": [rejected_1 / repetitions, rejected_2 / repetitions],
            "joint_power_event": "both_primary_hypotheses_rejected_after_holm",
            "joint_power": joint_power,
            "joint_power_95_percent_wilson_interval": joint_ci,
            "joint_power_mc_standard_error": float(np.sqrt(joint_power * (1 - joint_power) / repetitions)),
            "familywise_power": rejected_family / repetitions,
            "familywise_power_event": "at_least_one_primary_hypothesis_rejected_after_holm",
            "familywise_power_95_percent_wilson_interval": ci,
            "familywise_power_mc_standard_error": float(np.sqrt((rejected_family / repetitions) * (1 - rejected_family / repetitions) / repetitions))}
