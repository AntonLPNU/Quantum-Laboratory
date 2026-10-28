"""Two-spin density operators and state preparation.

The computational basis is |00>, |01>, |10>, |11>. The singlet is
|S>=(|01>-|10>)/sqrt(2), a maximally entangled spin state.
"""
from __future__ import annotations

import numpy as np


def density_matrix(state: np.ndarray) -> np.ndarray:
    """Pure-state density operator ρ=|ψ><ψ| (SRC-006); ket norm is unity; dimension 4."""
    ket = np.asarray(state, dtype=complex).reshape(-1)
    if ket.size != 4 or not np.isclose(np.vdot(ket, ket).real, 1.0, atol=1e-10):
        raise ValueError("state must be a normalized four-component ket")
    return np.outer(ket, ket.conj())


def bell_state(name: str = "singlet") -> np.ndarray:
    """Prepare a standard Bell basis state (SRC-006); ideal pure two-spin state, dimension 4."""
    states = {
        "phi+": np.array([1, 0, 0, 1], complex) / np.sqrt(2),
        "phi-": np.array([1, 0, 0, -1], complex) / np.sqrt(2),
        "psi+": np.array([0, 1, 1, 0], complex) / np.sqrt(2),
        "singlet": np.array([0, 1, -1, 0], complex) / np.sqrt(2),
    }
    try:
        return density_matrix(states[name.lower()])
    except KeyError as exc:
        raise ValueError(f"unknown Bell state {name!r}; choose {', '.join(states)}") from exc


def partial_trace(rho: np.ndarray, keep: int) -> np.ndarray:
    """Compute ρ_A=Tr_Bρ_AB or ρ_B=Tr_Aρ_AB (SRC-004); exact finite-dimensional trace."""
    matrix = np.asarray(rho, dtype=complex)
    if matrix.shape != (4, 4):
        raise ValueError("rho must be a 4x4 two-qubit density matrix")
    if keep not in (0, 1):
        raise ValueError("keep must be 0 (A) or 1 (B)")
    tensor = matrix.reshape(2, 2, 2, 2)
    return np.einsum("abcb->ac", tensor) if keep == 0 else np.einsum("abad->bd", tensor)


def validate_density_matrix(rho: np.ndarray, atol: float = 1e-10) -> bool:
    """Check density-operator conditions (SRC-006); atol is a numerical tolerance, not physics."""
    matrix = np.asarray(rho, dtype=complex)
    if matrix.shape != (4, 4) or not np.allclose(matrix, matrix.conj().T, atol=atol):
        return False
    if not np.isclose(np.trace(matrix), 1.0, atol=atol):
        return False
    return bool(np.linalg.eigvalsh((matrix + matrix.conj().T) / 2).min() >= -atol)
