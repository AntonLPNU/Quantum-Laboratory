"""Ordered primitives for registers of 2–6 spin-1/2 subsystems.

The basis is |q0 ... q(N-1)>: q0 is the leftmost tensor factor and
computational-basis indices are big-endian. Subsystem lists retain their
caller-provided order. State validity and unitarity use absolute tolerance
1e-10 (zero relative tolerance); no input is silently normalized.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Integral

import numpy as np

_ATOL = 1e-10


def _sequence(values: Sequence, name: str) -> list:
    if isinstance(values, (str, bytes)) or not isinstance(values, (Sequence, np.ndarray)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, np.ndarray) and values.ndim == 0:
        raise TypeError(f"{name} must be an ordered sequence")
    return list(values)


def _spin_count(n_spins: int) -> int:
    if isinstance(n_spins, (bool, np.bool_)) or not isinstance(n_spins, Integral):
        raise TypeError("n_spins must be an integer")
    if not 2 <= n_spins <= 6:
        raise ValueError("register must contain 2 through 6 spins")
    return int(n_spins)


def _dimension_spins(dimension: int) -> int:
    if dimension < 1 or dimension & (dimension - 1):
        raise ValueError("register dimension must be a power of two")
    return _spin_count(dimension.bit_length() - 1)


def _indices(values: Sequence[int], n_spins: int, name: str) -> list[int]:
    indices = _sequence(values, name)
    for index in indices:
        if isinstance(index, (bool, np.bool_)) or not isinstance(index, Integral):
            raise TypeError(f"{name} indices must be integers, excluding Booleans")
        if not 0 <= index < n_spins:
            raise ValueError(f"{name} indices must be in range 0 through {n_spins - 1}")
    if len(set(indices)) != len(indices):
        raise ValueError(f"{name} must not contain duplicate indices")
    return [int(index) for index in indices]


def _normalized_ket(state: np.ndarray, dimension: int | None = None) -> np.ndarray:
    ket = np.asarray(state, dtype=complex)
    if ket.ndim != 1 or (dimension is not None and ket.size != dimension):
        raise ValueError("ket must be a one-dimensional array of the required length")
    if not np.all(np.isfinite(ket)) or not np.isclose(np.vdot(ket, ket), 1.0, atol=_ATOL, rtol=0):
        raise ValueError("ket must have finite entries and unit norm")
    return ket


def _state(state: np.ndarray, *, physical: bool) -> tuple[np.ndarray, int]:
    array = np.asarray(state, dtype=complex)
    if array.ndim == 1:
        n_spins = _dimension_spins(array.size)
        return _normalized_ket(array), n_spins
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        raise ValueError("state must be a ket or square matrix")
    n_spins = _dimension_spins(array.shape[0])
    if not np.all(np.isfinite(array)):
        raise ValueError("state must have finite entries")
    if physical:
        if not np.allclose(array, array.conj().T, atol=_ATOL, rtol=0):
            raise ValueError("density matrix must be Hermitian")
        if not np.isclose(np.trace(array), 1.0, atol=_ATOL, rtol=0):
            raise ValueError("density matrix must have unit trace")
        if np.linalg.eigvalsh((array + array.conj().T) / 2).min() < -_ATOL:
            raise ValueError("density matrix must be positive semidefinite")
    return array, n_spins


def tensor_product_state(kets: Sequence[np.ndarray]) -> np.ndarray:
    """Return a normalized product ket, with the first spin leftmost."""
    factors = _sequence(kets, "kets")
    _spin_count(len(factors))
    ket = np.array([1.0], dtype=complex)
    for factor in factors:
        ket = np.kron(ket, _normalized_ket(factor, dimension=2))
    return ket


def partial_trace_subsystems(state: np.ndarray, keep: Sequence[int]) -> np.ndarray:
    """Trace complementary spins, retaining exactly the supplied factor order.

    Accept a normalized ket or any finite square operator on 2–6 spins.
    Empty keep returns [[Tr(state)]] (the density operator is used for kets).
    Matrix inputs need not be normalized, Hermitian, or positive: this is a
    linear operator contraction. Use reduced_density_matrix for physical
    density-state validation.
    """
    array, n_spins = _state(state, physical=False)
    kept = _indices(keep, n_spins, "keep")
    rho = np.outer(array, array.conj()) if array.ndim == 1 else array
    traced = [site for site in range(n_spins) if site not in kept]
    permutation = kept + traced + [site + n_spins for site in kept + traced]
    tensor = rho.reshape((2,) * (2 * n_spins)).transpose(permutation)
    retained_dim, traced_dim = 2 ** len(kept), 2 ** len(traced)
    tensor = tensor.reshape(retained_dim, traced_dim, retained_dim, traced_dim)
    return np.einsum("abcb->ac", tensor)


def embed_operator(operator: np.ndarray, targets: Sequence[int], n_spins: int) -> np.ndarray:
    """Embed an arbitrary operator in ordered targets, with identity spectators.

    The first target is the operator's leftmost factor. Empty targets require
    a 1x1 operator and produce its scalar times the register identity.
    """
    n_spins = _spin_count(n_spins)
    selected = _indices(targets, n_spins, "targets")
    matrix = np.asarray(operator, dtype=complex)
    local_dim = 2 ** len(selected)
    if matrix.shape != (local_dim, local_dim) or not np.all(np.isfinite(matrix)):
        raise ValueError("operator must be finite and have dimension 2**len(targets)")
    full = np.zeros((2 ** n_spins,) * 2, dtype=complex)
    masks = [1 << (n_spins - 1 - site) for site in selected]
    selected_mask = sum(masks)
    for source in range(2 ** n_spins):
        local_source = 0
        for mask in masks:
            local_source = (local_source << 1) | bool(source & mask)
        spectator_bits = source & ~selected_mask
        for local_output in range(local_dim):
            output = spectator_bits
            for j, mask in enumerate(masks):
                if local_output & (1 << (len(selected) - 1 - j)):
                    output |= mask
            full[output, source] = matrix[local_output, local_source]
    return full


def apply_subsystem_unitary(state: np.ndarray, unitary: np.ndarray, targets: Sequence[int]) -> np.ndarray:
    """Apply U to a physical state, preserving ket versus density representation."""
    array, n_spins = _state(state, physical=True)
    full = embed_operator(unitary, targets, n_spins)
    local = np.asarray(unitary, dtype=complex)
    if not np.allclose(local.conj().T @ local, np.eye(local.shape[0]), atol=_ATOL, rtol=0):
        raise ValueError("unitary must satisfy U dagger U = identity")
    if array.ndim == 1:
        return full @ array
    return full @ array @ full.conj().T


def apply_subsystem_kraus(state: np.ndarray, kraus_operators: Sequence[np.ndarray],
                          targets: Sequence[int], *, atol: float = _ATOL) -> np.ndarray:
    """Apply a trace-preserving local Kraus channel without selecting outcomes.

    Kets become density matrices because the unobserved Kraus outcome is
    averaged over. The first target is the leftmost factor of every Kraus
    operator, matching :func:`embed_operator`.
    """
    from collections.abc import Sequence as SequenceABC

    array, n_spins = _state(state, physical=True)
    selected = _indices(targets, n_spins, "targets")
    if not isinstance(kraus_operators, SequenceABC) or isinstance(kraus_operators, (str, bytes)) or len(kraus_operators) == 0:
        raise TypeError("kraus_operators must be a nonempty ordered sequence")
    if isinstance(atol, (bool, np.bool_)) or not np.isscalar(atol) or not np.isfinite(atol) or atol < 0:
        raise ValueError("atol must be finite and nonnegative")
    local_dim = 2 ** len(selected)
    operators = []
    completeness = np.zeros((local_dim, local_dim), dtype=complex)
    for operator in kraus_operators:
        local = np.asarray(operator, dtype=complex)
        if local.shape != (local_dim, local_dim) or not np.all(np.isfinite(local)):
            raise ValueError("each Kraus operator must be finite with dimension 2**len(targets)")
        operators.append(embed_operator(local, selected, n_spins))
        completeness += local.conj().T @ local
    if not np.allclose(completeness, np.eye(local_dim), atol=atol, rtol=0):
        raise ValueError("Kraus operators must satisfy sum(K dagger K) = identity")
    rho = np.outer(array, array.conj()) if array.ndim == 1 else array
    result = np.zeros_like(rho, dtype=complex)
    for full in operators:
        result += full @ rho @ full.conj().T
    return result


def reduced_density_matrix(state: np.ndarray, keep: Sequence[int]) -> np.ndarray:
    """Return the ordered reduction of a validated physical ket or density state."""
    array, _ = _state(state, physical=True)
    return partial_trace_subsystems(array, keep)


def expectation_value(state: np.ndarray, operator: np.ndarray, targets: Sequence[int]) -> complex:
    """Return <O> for ordered targets; arbitrary operators may give complex values."""
    array, n_spins = _state(state, physical=True)
    full = embed_operator(operator, targets, n_spins)
    if array.ndim == 1:
        return complex(np.vdot(array, full @ array))
    return complex(np.trace(array @ full))


def density_matrix_from_ket(ket: np.ndarray) -> np.ndarray:
    """Return |ket><ket| for a normalized 2–6-spin ket (SRC-006).

    Preserve complex coherences; reject invalid shapes, norms and entries
    without silently normalizing or flattening the input.
    """
    array = _normalized_ket(ket)
    _dimension_spins(array.size)
    return np.outer(array, array.conj())


def prepare_bell_pair_state(
    n_spins: int,
    pair: Sequence[int],
    bell: str = "singlet",
    spectator_kets: Mapping[int, np.ndarray] | None = None,
) -> np.ndarray:
    """Embed a Bell ket in the exact supplied pair order (SRC-006).

    The first pair site is the Bell ket's leftmost factor. Every unspecified
    spectator is |0>; supplied spectators must be normalized single-spin
    kets. The returned global ket uses the module's big-endian site order.
    Reversing singlet targets multiplies the ket by -1, so its density
    matrix is invariant. This is ideal pure preparation, with no mixing.
    """
    n_spins = _spin_count(n_spins)
    selected = _indices(pair, n_spins, "pair")
    if len(selected) != 2:
        raise ValueError("pair must contain exactly two distinct spin indices")
    if not isinstance(bell, str):
        raise TypeError("bell must be a Bell-state label string")
    states = {
        "phi+": [1, 0, 0, 1],
        "phi-": [1, 0, 0, -1],
        "psi+": [0, 1, 1, 0],
        "singlet": [0, 1, -1, 0],
    }
    try:
        ket = np.array(states[bell.lower()], dtype=complex) / np.sqrt(2)
    except KeyError as exc:
        raise ValueError(f"unknown Bell state {bell!r}; choose {', '.join(states)}") from exc
    supplied = {} if spectator_kets is None else spectator_kets
    if not isinstance(supplied, Mapping):
        raise TypeError("spectator_kets must be a mapping from site to ket")
    spectator_sites = _indices(list(supplied), n_spins, "spectator_kets")
    if any(site in selected for site in spectator_sites):
        raise ValueError("spectator_kets must not include Bell-pair sites")
    spectators = [site for site in range(n_spins) if site not in selected]
    for site in spectators:
        local = _normalized_ket(supplied.get(site, [1, 0]), dimension=2)
        ket = np.kron(ket, local)
    factor_order = selected + spectators
    permutation = [factor_order.index(site) for site in range(n_spins)]
    return ket.reshape((2,) * n_spins).transpose(permutation).reshape(-1)
