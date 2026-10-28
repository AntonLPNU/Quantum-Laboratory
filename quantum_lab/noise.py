"""Parameterized local quantum-noise channels for finite-dimensional spin states."""
from __future__ import annotations

import numpy as np

from .operations import I2, PAULI


def _validated_dephasing_fraction(dephasing_fraction: float) -> float:
    try:
        fraction = float(dephasing_fraction)
    except (TypeError, ValueError) as exc:
        raise ValueError("dephasing_fraction must be a finite number in [0, 1]") from exc
    if not np.isfinite(fraction) or not 0.0 <= fraction <= 1.0:
        raise ValueError("dephasing_fraction must be a finite number in [0, 1]")
    return fraction


def phase_damping(rho: np.ndarray, dephasing_fraction: float) -> np.ndarray:
    """Apply a qubit phase-damping Kraus channel to a 2x2 density matrix.

    The channel uses K0=sqrt(1-λ/2) I and K1=sqrt(λ/2) Z, so populations
    are preserved and coherences are multiplied by 1-λ. λ is a dimensionless
    phenomenological coherence-loss fraction, not a measured T2 or rate.
    The Kraus sum is a trace-preserving completely-positive map (SRC-010);
    the phase-damping channel's microscopic Kraus derivation is SRC-013.
    """
    fraction = _validated_dephasing_fraction(dephasing_fraction)
    matrix = np.asarray(rho, dtype=complex)
    if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
        raise ValueError("rho must be a finite 2x2 qubit density matrix")
    k0 = np.sqrt(1.0 - fraction / 2.0) * I2
    k1 = np.sqrt(fraction / 2.0) * PAULI[2]
    return k0 @ matrix @ k0.conj().T + k1 @ matrix @ k1.conj().T


def apply_local_phase_damping(rho: np.ndarray, dephasing_fraction: float, subsystem: int) -> np.ndarray:
    """Apply phase damping locally and return the complete 4x4 two-spin state.

    Use subsystem 0 for A and 1 for B. The Kraus sum acts on the full state,
    retaining coherences and correlations needed by joint-state analyses.
    """
    fraction = _validated_dephasing_fraction(dephasing_fraction)
    matrix = np.asarray(rho, dtype=complex)
    if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
        raise ValueError("rho must be a finite 4x4 two-qubit density matrix")
    if subsystem not in (0, 1):
        raise ValueError("subsystem must be 0 (A) or 1 (B)")
    k0 = np.sqrt(1.0 - fraction / 2.0) * I2
    k1 = np.sqrt(fraction / 2.0) * PAULI[2]
    identity = I2
    local_operators = (k0, k1)
    result = np.zeros((4, 4), dtype=complex)
    for operator in local_operators:
        full_operator = np.kron(operator, identity) if subsystem == 0 else np.kron(identity, operator)
        result += full_operator @ matrix @ full_operator.conj().T
    return result
