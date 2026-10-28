"""Local spin rotations and projective measurements."""
from __future__ import annotations

import numpy as np

I2 = np.eye(2, dtype=complex)
PAULI = (
    np.array([[0, 1], [1, 0]], complex),
    np.array([[0, -1j], [1j, 0]], complex),
    np.array([[1, 0], [0, -1]], complex),
)


def _unit_vector(axis: np.ndarray) -> np.ndarray:
    vector = np.asarray(axis, dtype=float).reshape(-1)
    if vector.size != 3 or not np.all(np.isfinite(vector)):
        raise ValueError("axis must contain three finite values")
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("axis cannot be zero")
    return vector / norm


def spin_operator(axis: np.ndarray) -> np.ndarray:
    """Build n·σ for spin measurement (SRC-006); normalized axis; dimensionless outcomes ±1."""
    n = _unit_vector(axis)
    return sum(n[i] * PAULI[i] for i in range(3))


def local_rotation(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    """Spin-1/2 rotation U=exp(−iθ n·σ/2) (SRC-002, SRC-006); θ in radians; ideal coherent control."""
    if not np.isfinite(angle_rad):
        raise ValueError("angle_rad must be finite")
    operator = spin_operator(axis)
    return np.cos(angle_rad / 2) * I2 - 1j * np.sin(angle_rad / 2) * operator


def apply_local_unitary(rho: np.ndarray, unitary: np.ndarray, subsystem: int) -> np.ndarray:
    """Apply ρ'=(U⊗I)ρ(U⊗I)† or (I⊗U)ρ(I⊗U)† (SRC-003, SRC-006); no noise or postselection."""
    matrix = np.asarray(rho, dtype=complex)
    operation = np.asarray(unitary, dtype=complex)
    if matrix.shape != (4, 4) or operation.shape != (2, 2):
        raise ValueError("expected a 4x4 state and a 2x2 unitary")
    if subsystem not in (0, 1):
        raise ValueError("subsystem must be 0 (A) or 1 (B)")
    full = np.kron(operation, I2) if subsystem == 0 else np.kron(I2, operation)
    return full @ matrix @ full.conj().T


def measurement_probabilities(rho: np.ndarray, axis: np.ndarray, subsystem: int | None = None) -> dict[int, float]:
    """Born rule p(s)=Tr[ρ(I+s n·σ)/2] (SRC-006), s=±1; ideal projective measurement."""
    matrix = np.asarray(rho, dtype=complex)
    observable = spin_operator(axis)
    if subsystem is not None:
        if subsystem not in (0, 1):
            raise ValueError("subsystem must be 0 (A) or 1 (B)")
        matrix = np.trace(matrix.reshape(2, 2, 2, 2), axis1=1 - subsystem, axis2=3 - subsystem)
    if matrix.shape != (2, 2):
        raise ValueError("provide a single-spin state or specify subsystem for a pair")
    return {outcome: float(np.clip(np.trace(matrix @ (I2 + outcome * observable) / 2).real, 0, 1)) for outcome in (-1, 1)}


def joint_measurement_probabilities(rho: np.ndarray, axis_a: np.ndarray, axis_b: np.ndarray) -> dict[tuple[int, int], float]:
    """Joint Born rule Tr[ρ(Π_s^A⊗Π_t^B)] (SRC-006); axes are unit directions, ideal readout."""
    a, b = spin_operator(axis_a), spin_operator(axis_b)
    return {
        (x, y): float(np.clip(np.trace(np.asarray(rho) @ np.kron((I2 + x * a) / 2, (I2 + y * b) / 2)).real, 0, 1))
        for x in (-1, 1) for y in (-1, 1)
    }
