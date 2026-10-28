"""Entanglement and correlation measures for two spin-1/2 systems."""
from __future__ import annotations

import numpy as np

from .operations import PAULI, spin_operator


def correlator(rho: np.ndarray, axis_a: np.ndarray, axis_b: np.ndarray) -> float:
    """E(a,b)=Tr[ρ(a·σ⊗b·σ)] (SRC-006); dimensionless ±1 outcomes."""
    return float(np.trace(np.asarray(rho) @ np.kron(spin_operator(axis_a), spin_operator(axis_b))).real)


def chsh_value(rho: np.ndarray, a: np.ndarray, a_prime: np.ndarray, b: np.ndarray, b_prime: np.ndarray) -> float:
    """Absolute CHSH S=|E(a,b)+E(a,b')+E(a',b)−E(a',b')| (SRC-001, SRC-006); ideal two-qubit correlations."""
    value = correlator(rho, a, b) + correlator(rho, a, b_prime) + correlator(rho, a_prime, b) - correlator(rho, a_prime, b_prime)
    return abs(value)


def maximal_chsh_value(rho: np.ndarray) -> float:
    """Optimized two-setting CHSH bound for arbitrary two-qubit ρ (SRC-001, SRC-006).

    The Horodecki criterion (SRC-014) is 2*sqrt(m1+m2), with m1,m2 the two largest
    eigenvalues of T.T@T and T_ij=Tr[ρ(σ_i⊗σ_j)]. This is distinct from
    evaluating CHSH for any one fixed quartet of measurement axes.
    """
    state = np.asarray(rho, dtype=complex)
    if state.shape != (4, 4) or not np.all(np.isfinite(state)):
        raise ValueError("rho must be a finite 4x4 two-qubit density matrix")
    basis = np.eye(3)
    correlation_tensor = np.array(
        [[correlator(state, basis[i], basis[j]) for j in range(3)] for i in range(3)],
        dtype=float,
    )
    eigenvalues = np.linalg.eigvalsh(correlation_tensor.T @ correlation_tensor)
    return float(2.0 * np.sqrt(max(0.0, eigenvalues[-1] + eigenvalues[-2])))


def concurrence(rho: np.ndarray) -> float:
    """Wootters two-qubit concurrence (SRC-007); exact 4×4 density matrix, clipped only for roundoff."""
    y = PAULI[1]
    spin_flip = np.kron(y, y)
    transformed = spin_flip @ np.asarray(rho, dtype=complex).conj() @ spin_flip
    eigenvalues = np.linalg.eigvals(np.asarray(rho, dtype=complex) @ transformed)
    roots = np.sqrt(np.clip(eigenvalues.real, 0, None))
    roots.sort()
    return float(np.clip(roots[-1] - roots[-2] - roots[-3] - roots[-4], 0, 1))


def von_neumann_entropy(rho: np.ndarray) -> float:
    """S(ρ)=−Tr(ρ log₂ρ) (SRC-006); information entropy in bits."""
    values = np.linalg.eigvalsh(np.asarray(rho, dtype=complex))
    values = values[values > 1e-14]
    return float(-np.sum(values * np.log2(values)))
