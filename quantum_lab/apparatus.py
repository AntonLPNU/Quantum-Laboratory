"""Phenomenological local binary readout assignment channel."""
from __future__ import annotations

import random
from collections.abc import Iterable


def apply_binary_assignment_noise(outcomes: Iterable[int], fidelity: float, seed: int | None = None) -> list[int]:
    """Flip a +/-1 measurement result with probability 1-fidelity.

    This symmetric binary channel is a phenomenological detector/assignment
    model, not a complete NV-center readout model. F is dimensionless. Hensen
    2015 reports combined initialization and single-shot-readout fidelities,
    so those values are only illustrative benchmarks, not detector-only
    calibration. See DOI: 10.1038/nature15759, Methods/Supplementary.
    """
    if not 0.0 <= fidelity <= 1.0:
        raise ValueError("fidelity must be between zero and one")
    values = list(outcomes)
    if any(value not in (-1, 1) for value in values):
        raise ValueError("outcomes must contain only -1 or +1")
    rng = random.Random(seed)
    return [-value if rng.random() >= fidelity else value for value in values]


def assignment_channel_expectation(true_outcome: int, fidelity: float) -> float:
    """Analytic mean of the symmetric binary assignment channel.

    For outcome s in {-1,+1}, E[s_observed|s_true] = s_true(2F-1).
    Independent local channels therefore attenuate a two-site correlation by
    (2F_A-1)(2F_B-1); this identity is the mathematical regression reference.
    """
    if true_outcome not in (-1, 1):
        raise ValueError("true_outcome must be -1 or +1")
    if not 0.0 <= fidelity <= 1.0:
        raise ValueError("fidelity must be between zero and one")
    return true_outcome * (2.0 * fidelity - 1.0)


def simulate_binary_readout_correlations(correlations: dict[str, float], fidelity_a: float, fidelity_b: float) -> dict:
    """Apply the analytic expectation of two independent local assignment channels.

    The deterministic analytic method has no random seed. It is a component
    simulation only and intentionally cannot return an apparatus-validation status.
    """
    for fidelity in (fidelity_a, fidelity_b):
        if not 0.0 <= fidelity <= 1.0:
            raise ValueError("fidelities must be between zero and one")
    if any(not -1.0 <= value <= 1.0 for value in correlations.values()):
        raise ValueError("correlations must be between -1 and +1")
    attenuation = (2.0 * fidelity_a - 1.0) * (2.0 * fidelity_b - 1.0)
    return {"correlations": {key: value * attenuation for key, value in correlations.items()},
            "input_correlations": dict(correlations), "fidelity_a": fidelity_a,
            "fidelity_b": fidelity_b, "attenuation": attenuation,
            "model_version": "binary-assignment-v1", "numerical_method": "analytic expectation",
            "seed": None, "status": "COMPONENT ONLY - NOT APPARATUS VALIDATION",
            "diagnostics": {"input_range_valid": True, "independent_local_channels": True}}
