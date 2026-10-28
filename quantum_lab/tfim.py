"""Homogeneous open-boundary transverse-field Ising model (SRC-015).

Return the angular-frequency generator
    H / hbar = -J sum(i=0..N-2) sigma_z(i) sigma_z(i+1)
               -h sum(i=0..N-1) sigma_x(i).
J and h are finite real angular frequencies in s^-1; time is in seconds.
The physical energy Hamiltonian is hbar times the returned matrix, which
enters U(t) = exp(-i (H/hbar) t). Pauli eigenvalues are +/-1; physical spin
is S = hbar sigma / 2, so spin-operator coefficients cannot be substituted
without an explicit conversion. Positive J favors aligned Z neighbors;
positive h favors +X polarization. Either coefficient can be signed or zero.
J=0 gives independent transverse spins, h=0 gives a diagonal Ising generator,
and J=h=0 gives the zero generator. There are exactly N-1 path bonds and
no last-to-first bond. Spin 0 is the leftmost tensor factor, in big-endian
computational order; the supported register range is N=2..6.

Source: Weinberg and Bukov, SciPost Physics 7, 020 (2019),
DOI 10.21468/SciPostPhys.7.2.020, Pauli-normalized TFI convention. Its
published periodic-chain example is distinct from this open path model.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Literal

import numpy as np

from .multispin import _ATOL, _indices, _sequence, _spin_count, _state, embed_operator

_PAULI = {
    "x": np.array([[0, 1], [1, 0]], dtype=np.complex128),
    "y": np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
    "z": np.array([[1, 0], [0, -1]], dtype=np.complex128),
}


def _frequency(value: float, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real scalar in s^-1")
    try:
        frequency = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be finite in s^-1") from exc
    if not np.isfinite(frequency):
        raise ValueError(f"{name} must be finite in s^-1")
    return frequency


def local_pauli(n_spins: int, site: int, component: Literal["x", "y", "z"]) -> np.ndarray:
    """Return sigma_component at site, with identity on all other factors."""
    n_spins = _spin_count(n_spins)
    selected = _indices([site], n_spins, "site")
    if not isinstance(component, str) or component not in _PAULI:
        raise ValueError("component must be 'x', 'y', or 'z'")
    return embed_operator(_PAULI[component], selected, n_spins)


def open_tfim_hamiltonian(n_spins: int, J: float, h: float,
                          sites: Sequence[int] | None = None) -> np.ndarray:
    """Return complex128 H/hbar for a homogeneous N-spin open path.

    J and h are finite real scalars in s^-1, excluding Boolean values.
    Interaction terms include only (i, i+1), for i=0 through N-2.
    Raise ValueError if accumulation exceeds finite complex128 range.
    """
    n_spins = _spin_count(n_spins)
    J = _frequency(J, "J")
    h = _frequency(h, "h")
    selected = list(range(n_spins)) if sites is None else _indices(sites, n_spins, "sites")
    active = set(selected)
    result = np.zeros((2 ** n_spins,) * 2, dtype=np.complex128)
    zz = np.kron(_PAULI["z"], _PAULI["z"])
    try:
        with np.errstate(over="raise", invalid="raise"):
            for site in range(n_spins - 1):
                if site in active and site + 1 in active:
                    result -= J * embed_operator(zz, [site, site + 1], n_spins)
            for site in selected:
                result -= h * local_pauli(n_spins, site, "x")
    except FloatingPointError as exc:
        raise ValueError("Hamiltonian must be representable as finite complex128 entries") from exc
    return result

# Spectral propagation uses the same absolute physical-state tolerance as
# multispin; inputs are never normalized or repaired silently.


@dataclass
class EvolutionResult:
    """Evolution trajectory: observable arrays lead with time; snapshots use indexes.

    final_state always retains the input ket/density representation. Invalid
    inputs raise TypeError/ValueError before propagation; successful runs have
    status='success' and error=None. Energy values and drifts are <H/hbar>
    in s^-1. Multiply by hbar for physical energies in joules.
    """

    status: str
    times_s: np.ndarray
    observables: dict[str, np.ndarray]
    snapshots: dict[int, np.ndarray]
    diagnostics: dict[str, object]
    error: str | None
    final_state: np.ndarray


def _hermitian_generator(H_over_hbar: np.ndarray, dimension: int | None = None) -> np.ndarray:
    matrix = np.asarray(H_over_hbar, dtype=np.complex128)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError('H_over_hbar must be a nonempty square matrix')
    if dimension is not None and matrix.shape != (dimension, dimension):
        raise ValueError('H_over_hbar must match the state dimension')
    if not np.all(np.isfinite(matrix)):
        raise ValueError('H_over_hbar must have finite entries')
    if not np.allclose(matrix, matrix.conj().T, atol=_ATOL, rtol=0):
        raise ValueError('H_over_hbar must be Hermitian')
    return matrix


def _spectral_phases(values: np.ndarray, times: np.ndarray) -> np.ndarray:
    try:
        with np.errstate(over='raise', invalid='raise'):
            phases = np.exp(-1j * np.outer(times, values))
    except FloatingPointError as exc:
        raise ValueError('spectral phases must be representable as finite complex128') from exc
    if not np.all(np.isfinite(phases)):
        raise ValueError('spectral phases must be finite')
    return phases


def unitary_from_hermitian(H_over_hbar: np.ndarray, elapsed_s: float) -> np.ndarray:
    """Return exp(-i H_over_hbar elapsed_s) for any finite Hermitian matrix.

    This mathematical helper permits one spin and signed elapsed times.
    Public register evolution remains restricted to N=2..6.
    """
    matrix = _hermitian_generator(H_over_hbar)
    elapsed = _frequency(elapsed_s, 'elapsed_s')
    values, vectors = np.linalg.eigh(matrix)
    phases = _spectral_phases(values, np.array([elapsed]))[0]
    return (vectors * phases) @ vectors.conj().T


def _observable_operators(n_spins: int, sites: list[int]) -> dict[str, list[np.ndarray]]:
    operators = {
        f'sigma_{component}': [local_pauli(n_spins, site, component) for site in sites]
        for component in ('x', 'y', 'z')
    }
    all_z = [local_pauli(n_spins, site, 'z') for site in range(n_spins)]
    operators['mean_sigma_z'] = [sum(all_z) / n_spins]
    operators['nearest_neighbor_zz'] = [all_z[i] @ all_z[i+1] for i in range(n_spins-1)]
    return operators


def _measure(state: np.ndarray, operators: dict[str, list[np.ndarray]], H: np.ndarray | None) -> dict:
    def expectation(operator):
        value = np.vdot(state, operator @ state) if state.ndim == 1 else np.trace(state @ operator)
        return float(value.real)

    result = {name: np.array([expectation(operator) for operator in group]) for name, group in operators.items()}
    result['mean_sigma_z'] = float(result['mean_sigma_z'][0])
    if H is not None:
        result['energy_over_hbar'] = expectation(H)
    return result


def tfim_observables(state: np.ndarray, n_spins: int, sites: Sequence[int] | None = None,
                     *, H_over_hbar: np.ndarray | None = None) -> dict:
    """Return Pauli expectations for a physical state on N=2..6 spins.

    sigma_x/y/z arrays follow the supplied sites order (default all sites).
    mean_sigma_z always averages all spins; nearest_neighbor_zz always lists
    all N-1 open path bonds. Empty sites gives empty local arrays. Optional
    energy_over_hbar is <H_over_hbar> in s^-1 and is present only when the
    keyword generator is supplied; it cannot be inferred from a state alone.
    evolve_static supplies its generator automatically.
    """
    n_spins = _spin_count(n_spins)
    array, actual_spins = _state(state, physical=True)
    if actual_spins != n_spins:
        raise ValueError('n_spins must match the state dimension')
    selected = list(range(n_spins)) if sites is None else _indices(sites, n_spins, 'sites')
    H = None if H_over_hbar is None else _hermitian_generator(H_over_hbar, 2**n_spins)
    return _measure(array, _observable_operators(n_spins, selected), H)


def _estimate_static_memory_bytes(array: np.ndarray, n_spins: int, samples: int, snapshots: int) -> int:
    # np.exp simultaneously retains its complex argument and complex output.
    # This also covers the smaller real outer-product temporary.
    dimension = 2**n_spins
    operator_count = 3*n_spins + 1 + n_spins-1
    return int(
        (operator_count + 10)*dimension*dimension*16
        + (snapshots+3)*array.nbytes
        + samples*dimension*32
        + samples*(4*n_spins+2)*8
    )


def evolve_static(state: np.ndarray, H_over_hbar: np.ndarray, times_s: Sequence[float],
                  save_states_at: Sequence[int] = ()) -> EvolutionResult:
    """Propagate an initial physical state at absolute elapsed times in seconds.

    Times must be nonempty, finite, nonnegative and nondecreasing (duplicates
    allowed). The initial state is at t=0, even if the first requested time
    is positive. One eigendecomposition serves the whole trajectory. Only
    requested full snapshots and an independent final_state are retained.
    Full snapshots above 256 MiB are rejected before eigendecomposition or
    trajectory allocation; exactly 256 MiB is allowed.
    memory_estimate_bytes is a conservative ndarray storage estimate for
    states, operators, phases, results and matrix workspaces, calculated before
    allocating trajectory storage; it is not a process RSS guarantee or limit.
    Diagnostics are maxima over requested samples, including U dagger U's
    Frobenius defect, norm/trace/Hermiticity errors, minimum density eigenvalue,
    and absolute energy drift relative to the initial state in s^-1.
    """
    array, n_spins = _state(state, physical=True)
    dimension = 2**n_spins
    H = _hermitian_generator(H_over_hbar, dimension)
    requested = _sequence(times_s, 'times_s')
    times = np.array([_frequency(t, 'times_s entry') for t in requested], dtype=float)
    if times.size == 0 or np.any(times < 0) or np.any(np.diff(times) < 0):
        raise ValueError('times_s must be nonempty, nonnegative and sorted')
    indexes = _indices(save_states_at, len(times), 'save_states_at')
    _guard_tfim_snapshots(n_spins, len(indexes), 'ket' if array.ndim == 1 else 'density')
    # Estimate all persistent ndarray storage plus conservative complex matrix
    # workspaces before allocating phases, observables or full snapshots.
    memory_estimate = _estimate_static_memory_bytes(array, n_spins, len(times), len(indexes))
    values, vectors = np.linalg.eigh(H)
    phases = _spectral_phases(values, times)
    operators = _observable_operators(n_spins, list(range(n_spins)))
    observables = {
        name: np.empty((len(times), len(group)), dtype=float)
        for name, group in operators.items() if name != 'mean_sigma_z'
    }
    observables['mean_sigma_z'] = np.empty(len(times))
    observables['energy_over_hbar'] = np.empty(len(times))
    initial_energy = float((np.vdot(array, H @ array) if array.ndim == 1 else np.trace(array @ H)).real)
    diagnostics = {'memory_estimate_bytes': memory_estimate, 'unitary_defect': 0.0,
                   'energy_drift_over_hbar': 0.0}
    if array.ndim == 1:
        diagnostics['norm_error'] = 0.0
        coefficients = vectors.conj().T @ array
    else:
        diagnostics.update(trace_error=0.0, hermiticity_error=0.0, minimum_eigenvalue=float('inf'))
    snapshots = {}
    selected = set(indexes)
    identity = np.eye(dimension)
    for index, phase in enumerate(phases):
        U = (vectors * phase) @ vectors.conj().T
        propagated = vectors @ (phase * coefficients) if array.ndim == 1 else U @ array @ U.conj().T
        measured = _measure(propagated, operators, H)
        for name, value in measured.items():
            observables[name][index] = value
        diagnostics['unitary_defect'] = max(diagnostics['unitary_defect'], float(np.linalg.norm(U.conj().T @ U - identity)))
        diagnostics['energy_drift_over_hbar'] = max(diagnostics['energy_drift_over_hbar'], abs(measured['energy_over_hbar']-initial_energy))
        if array.ndim == 1:
            diagnostics['norm_error'] = max(diagnostics['norm_error'], float(abs(np.linalg.norm(propagated)-1)))
        else:
            diagnostics['trace_error'] = max(diagnostics['trace_error'], float(abs(np.trace(propagated)-1)))
            diagnostics['hermiticity_error'] = max(diagnostics['hermiticity_error'], float(np.linalg.norm(propagated-propagated.conj().T)))
            diagnostics['minimum_eigenvalue'] = min(diagnostics['minimum_eigenvalue'], float(np.linalg.eigvalsh(propagated).min()))
        if index in selected:
            snapshots[index] = propagated.copy()
    return EvolutionResult('success', times.copy(), observables, snapshots, diagnostics, None, propagated.copy())


@dataclass(frozen=True)
class FieldSchedule:
    """Reconstructible transverse frequency in s^-1, evaluated in seconds.

    Constant, sinusoidal and Gaussian schedules have domain [0, infinity).
    Piecewise intervals are [edge_i, edge_i+1); the last edge is included
    with the last value. At an internal edge the post-jump value is used.
    Gaussian width is its standard deviation, exp(-0.5*((t-center)/width)^2).
    to_dict/from_dict use JSON-compatible data with no executable callbacks.
    """

    kind: str
    parameters: tuple[float, ...] = ()
    edges_s: tuple[float, ...] = ()
    values: tuple[float, ...] = ()

    def __post_init__(self):
        counts = {'constant': 1, 'piecewise_constant': 0, 'sinusoidal': 4, 'gaussian': 4}
        if not isinstance(self.kind, str) or self.kind not in counts:
            raise ValueError('unknown field schedule kind')
        for name in ('parameters', 'edges_s', 'values'):
            items = _sequence(getattr(self, name), name)
            object.__setattr__(self, name, tuple(_frequency(v, name) for v in items))
        if len(self.parameters) != counts[self.kind]:
            raise ValueError('incorrect schedule parameter count')
        if self.kind == 'piecewise_constant':
            if (len(self.edges_s) < 2 or len(self.values) != len(self.edges_s)-1
                    or self.edges_s[0] < 0 or any(b <= a for a, b in zip(self.edges_s, self.edges_s[1:]))):
                raise ValueError('piecewise edges must be nonnegative, finite and strictly sorted with one value per interval')
        elif self.edges_s or self.values:
            raise ValueError('only piecewise schedules have edges and values')
        if self.kind == 'gaussian' and self.parameters[2] <= 0:
            raise ValueError('Gaussian width_s must be positive')

    @classmethod
    def constant(cls, value):
        """Створити сталий поперечний коефіцієнт у s⁻¹."""
        return cls('constant', (value,))

    @classmethod
    def piecewise_constant(cls, edges_s, values):
        """Створити кусково-сталий розклад з межею в секундах на кожній точці edges_s."""
        return cls('piecewise_constant', edges_s=edges_s, values=values)

    @classmethod
    def sinusoidal(cls, offset, amplitude, angular_frequency_s, phase_rad=0):
        """Створити синусоїдальне поле; частота має одиниці rad/s, фаза — rad."""
        return cls('sinusoidal', (offset, amplitude, angular_frequency_s, phase_rad))

    @classmethod
    def gaussian(cls, amplitude, center_s, width_s, offset=0):
        """Створити гаусове поле з центром і додатною шириною у секундах."""
        return cls('gaussian', (amplitude, center_s, width_s, offset))

    def to_dict(self):
        """Повернути JSON-сумісні параметри без втрати структури розкладу."""
        return {'kind': self.kind, 'parameters': list(self.parameters),
                'edges_s': list(self.edges_s), 'values': list(self.values)}

    @classmethod
    def from_dict(cls, data):
        """Відновити перевірений розклад з точного словника запису."""
        if not isinstance(data, dict) or set(data) != {'kind', 'parameters', 'edges_s', 'values'}:
            raise ValueError('schedule record must contain kind, parameters, edges_s and values')
        return cls(**data)

    def value_at(self, time_s):
        """Обчислити значення поля в невід'ємний часі seconds; поза piecewise domain кидає ValueError."""
        t = _frequency(time_s, 'time_s')
        if t < 0:
            raise ValueError('time_s must be nonnegative')
        if self.kind == 'constant':
            return self.parameters[0]
        if self.kind == 'piecewise_constant':
            if t < self.edges_s[0] or t > self.edges_s[-1]:
                raise ValueError('time_s is outside the schedule domain')
            index = min(int(np.searchsorted(self.edges_s, t, side='right'))-1, len(self.values)-1)
            return self.values[index]
        with np.errstate(over='raise', invalid='raise'):
            if self.kind == 'sinusoidal':
                offset, amplitude, omega, phase = self.parameters
                value = offset + amplitude*np.sin(np.float64(omega)*t + phase)
            else:
                amplitude, center, width, offset = self.parameters
                # The tail underflows harmlessly to zero; avoid overflowing
                # the squared standardized distance before evaluating it.
                with np.errstate(over='ignore', divide='ignore'):
                    distance = (np.float64(t)-center)/width
                value = offset if abs(distance) > 40 else offset+amplitude*np.exp(-.5*distance*distance)
        if not np.isfinite(value):
            raise ValueError('field value must be finite')
        return float(value)



TFIM_SOURCE_IDS = ('SRC-015', 'SRC-016', 'SRC-017', 'SRC-018', 'SRC-019')
_TFIM_SNAPSHOT_LIMIT_BYTES = 256 * 1024**2


def estimate_tfim_memory(n_spins: int, n_times: int, state_kind: str,
                         save_full_states: bool) -> dict:
    """Estimate complex128 ndarray storage without allocating state arrays.

    n_times is the number of snapshots when save_full_states=True. A ket
    needs 16*2**N bytes and a density matrix 16*4**N per saved state.
    Hamiltonian/operator/propagator workspaces, state buffers and observable
    arrays are included in total_bytes as a conservative planning estimate,
    not a process RSS guarantee. Only snapshot_bytes is subject to the
    256 MiB policy; exactly 256 MiB is allowed. N remains restricted to 2..6.
    """
    from numbers import Integral

    n_spins = _spin_count(n_spins)
    if isinstance(n_times, (bool, np.bool_)) or not isinstance(n_times, Integral):
        raise TypeError('n_times must be a nonnegative integer')
    if n_times < 0:
        raise ValueError('n_times must be a nonnegative integer')
    if not isinstance(state_kind, str) or state_kind not in ('ket', 'density'):
        raise ValueError("state_kind must be 'ket' or 'density'")
    if not isinstance(save_full_states, (bool, np.bool_)):
        raise TypeError('save_full_states must be Boolean')
    n_times = int(n_times)
    dimension = 2**n_spins
    matrix_bytes = 16*dimension**2
    state_bytes = 16*dimension if state_kind == 'ket' else matrix_bytes
    snapshot_bytes = n_times*state_bytes if save_full_states else 0
    state_buffers = 7*state_bytes
    matrix_buffers = (5*n_spins+35)*matrix_bytes
    trajectory_bytes = n_times*((4*n_spins+2)*8+dimension*32)
    return {
        'state_kind': state_kind, 'state_bytes': state_bytes,
        'hamiltonian_bytes': matrix_bytes, 'state_buffers_bytes': state_buffers,
        'matrix_buffers_bytes': matrix_buffers, 'trajectory_bytes': trajectory_bytes,
        'snapshot_bytes': snapshot_bytes,
        'total_bytes': snapshot_bytes+state_buffers+matrix_buffers+trajectory_bytes,
        'snapshot_limit_bytes': _TFIM_SNAPSHOT_LIMIT_BYTES,
        'exceeds_snapshot_limit': snapshot_bytes > _TFIM_SNAPSHOT_LIMIT_BYTES,
    }


def _guard_tfim_snapshots(n_spins: int, count: int, state_kind: str) -> dict:
    estimate = estimate_tfim_memory(n_spins, count, state_kind, True)
    if estimate['exceeds_snapshot_limit']:
        raise ValueError('requested full-state snapshots exceed the 256 MiB limit')
    return estimate


def evolve_tfim(state: np.ndarray, n_spins: int, J: float, h_schedule: FieldSchedule,
                times_s: Sequence[float], *, local_controls=None, active_sites=None, rtol=1e-9,
                atol=1e-12, max_steps=100000, save_states_at=(), cancel_check=None) -> EvolutionResult:
    """Unitary OBC evolution from t=0 with explicit additive -delta_h_i X_i.

    Local controls map site indices to FieldSchedule objects. Every schedule
    must cover [0, times_s[-1]]. Static segments use cached eigensystems;
    smooth segments use order-two exponential midpoint and two chronological
    half steps, accepting the fine state when ||fine-coarse||/3 divided by
    atol+rtol*max(||fine||,||coarse||) is at most one. Density norms are
    Frobenius norms. The bounded controller uses safety .9 and exponent 1/3.

    Tolerances control local errors only. global_comparison explicitly records
    that no independent convergence comparison was performed by this call.
    Failed/cancelled results contain only completed requested samples, the
    last accepted final_state, a machine-readable error and final_time_s in
    diagnostics. They never imply that unrequested final observables exist.
    Snapshot keys are requested sample indexes, as in evolve_static. Full-state
    snapshots above 256 MiB are rejected before allocating trajectory/operator
    arrays; exactly 256 MiB is allowed.
    """
    from collections.abc import Mapping
    from numbers import Integral

    n_spins = _spin_count(n_spins)
    array, actual_spins = _state(state, physical=True)
    if n_spins != actual_spins:
        raise ValueError('n_spins must match the state dimension')
    J = _frequency(J, 'J')
    if not isinstance(h_schedule, FieldSchedule):
        raise TypeError('h_schedule must be a FieldSchedule')
    if local_controls is None:
        local_controls = {}
    if not isinstance(local_controls, Mapping):
        raise TypeError('local_controls must map sites to schedules')
    active_sites = list(range(n_spins)) if active_sites is None else _indices(active_sites, n_spins, 'active_sites')
    active = set(active_sites)
    controls = {}
    for site, schedule in local_controls.items():
        selected_site = _indices([site], n_spins, 'local control site')[0]
        if selected_site not in active:
            raise ValueError('local controls must target active sites')
        if not isinstance(schedule, FieldSchedule):
            raise TypeError('local controls must be FieldSchedule objects')
        controls[selected_site] = schedule
    times = np.array([_frequency(t, 'times_s entry') for t in _sequence(times_s, 'times_s')])
    if times.size == 0 or np.any(times < 0) or np.any(np.diff(times) < 0):
        raise ValueError('times_s must be nonempty, nonnegative and sorted')
    indexes = _indices(save_states_at, len(times), 'save_states_at')
    _guard_tfim_snapshots(n_spins, len(indexes), 'ket' if array.ndim == 1 else 'density')
    selected = set(indexes)
    rtol, atol = _frequency(rtol, 'rtol'), _frequency(atol, 'atol')
    if rtol < 0 or atol < 0 or (rtol == 0 and atol == 0):
        raise ValueError('tolerances must be nonnegative and at least one positive')
    if isinstance(max_steps, (bool, np.bool_)) or not isinstance(max_steps, Integral) or max_steps < 1:
        raise ValueError('max_steps must be a positive integer')
    if cancel_check is not None and not callable(cancel_check):
        raise TypeError('cancel_check must be callable')
    schedules = [h_schedule, *controls.values()]
    for schedule in schedules:
        if schedule.kind == 'piecewise_constant' and (schedule.edges_s[0] > 0 or schedule.edges_s[-1] < times[-1]):
            raise ValueError('every schedule domain must cover [0, times_s[-1]]')
    smooth = any(s.kind not in ('constant', 'piecewise_constant') for s in schedules)
    boundaries = sorted({edge for s in schedules for edge in s.edges_s if 0 < edge <= times[-1]})
    method = 'exponential_midpoint' if smooth else ('piecewise_spectral' if boundaries else 'spectral')
    dimension = 2**n_spins
    # Midpoint trials retain three generators, four propagators, cumulative
    # propagation and eigensolver workspaces alongside cached local Paulis.
    memory_estimate = (_estimate_static_memory_bytes(array, n_spins, len(times), len(indexes))
                       + (n_spins+24)*dimension*dimension*16)
    operators = _observable_operators(n_spins, list(range(n_spins)))
    output = {name: np.empty((len(times), len(group))) for name, group in operators.items() if name != 'mean_sigma_z'}
    output['mean_sigma_z'] = np.empty(len(times))
    output['energy_over_hbar'] = np.empty(len(times))
    diagnostics = {'method': method, 'order': 2 if smooth else None,
                   'rtol': rtol, 'atol': atol, 'max_steps': int(max_steps),
                   'accepted_steps': 0, 'rejected_steps': 0, 'attempted_steps': 0,
                   'maximum_local_error': 0.0, 'maximum_scaled_local_error': 0.0,
                   'unitary_defect': 0.0, 'boundary_times_s': [], 'final_time_s': 0.0,
                   'global_comparison': {'status': 'not_performed'},
                   'active_sites': list(active_sites),
                   'memory_estimate_bytes': memory_estimate}
    if array.ndim == 1:
        diagnostics['norm_error'] = float(abs(np.linalg.norm(array)-1))
    else:
        diagnostics.update(trace_error=float(abs(np.trace(array)-1)),
                           hermiticity_error=float(np.linalg.norm(array-array.conj().T)),
                           minimum_eigenvalue=float(np.linalg.eigvalsh(array).min()))
    snapshots, completed, current, t = {}, 0, array.copy(), 0.0
    total_U = np.eye(dimension, dtype=complex)
    identity = np.eye(dimension)

    def finish(status, reason=None):
        diagnostics['final_time_s'] = t
        return EvolutionResult(status, times[:completed].copy(),
                               {name: values[:completed].copy() for name, values in output.items()},
                               snapshots, diagnostics, reason, current.copy())

    def physical_diagnostics():
        diagnostics['unitary_defect'] = max(diagnostics['unitary_defect'], float(np.linalg.norm(total_U.conj().T @ total_U-identity)))
        if current.ndim == 1:
            diagnostics['norm_error'] = max(diagnostics['norm_error'], float(abs(np.linalg.norm(current)-1)))
        else:
            diagnostics['trace_error'] = max(diagnostics['trace_error'], float(abs(np.trace(current)-1)))
            diagnostics['hermiticity_error'] = max(diagnostics['hermiticity_error'], float(np.linalg.norm(current-current.conj().T)))
            diagnostics['minimum_eigenvalue'] = min(diagnostics['minimum_eigenvalue'], float(np.linalg.eigvalsh(current).min()))

    try:
        base = open_tfim_hamiltonian(n_spins, J, 0, sites=active_sites)
    except ValueError:
        return finish('failed', 'nonfinite_hamiltonian')
    xs = {site: local_pauli(n_spins, site, 'x') for site in active_sites}
    sum_x = sum(xs.values(), np.zeros_like(base))

    def generator(time):
        with np.errstate(over='raise', invalid='raise'):
            H = base - h_schedule.value_at(time)*sum_x
            for site, schedule in controls.items():
                H -= schedule.value_at(time)*xs[site]
        return _hermitian_generator(H, dimension)

    def apply(U, value):
        return U @ value if value.ndim == 1 else U @ value @ U.conj().T

    if smooth and times[-1] > 0 and atol+rtol*np.linalg.norm(array) < 8*np.finfo(float).eps*np.linalg.norm(array):
        return finish('failed', 'tolerance_exhausted')
    step_limit = float(times[-1])
    if smooth:
        # Resolve known field variation scales even when midpoint samples alone
        # could alias a full oscillation or miss a narrow Gaussian pulse.
        for schedule in schedules:
            if schedule.kind == 'sinusoidal' and schedule.parameters[2] != 0:
                step_limit = min(step_limit, .125/abs(schedule.parameters[2]))
            if schedule.kind == 'gaussian':
                step_limit = min(step_limit, schedule.parameters[2]/4)
    step = min(float(times[-1])/16, step_limit)
    boundary_index = 0
    cached_segment, cached_spectrum = None, None
    for index, requested_time in enumerate(times):
        while t < requested_time:
            if cancel_check is not None and cancel_check():
                return finish('cancelled', 'cancelled')
            if diagnostics['attempted_steps'] >= max_steps:
                return finish('failed', 'max_steps')
            stop = min(requested_time, boundaries[boundary_index]) if boundary_index < len(boundaries) else requested_time
            next_time = min(t+step, stop) if smooth else stop
            dt = next_time-t
            if smooth and (dt <= 0 or t+dt/4 <= t or t+3*dt/4 >= next_time):
                return finish('failed', 'minimum_step')
            diagnostics['attempted_steps'] += 1
            try:
                if smooth:
                    coarse_H = generator(t+dt/2)
                    early_H, late_H = generator(t+dt/4), generator(t+3*dt/4)
                elif cached_segment != boundary_index:
                    constant_H = generator(t)
            except (ValueError, FloatingPointError, OverflowError):
                diagnostics['rejected_steps'] += 1
                return finish('failed', 'nonfinite_hamiltonian')
            try:
                if smooth:
                    coarse_U = unitary_from_hermitian(coarse_H, dt)
                    early_U = unitary_from_hermitian(early_H, dt/2)
                    late_U = unitary_from_hermitian(late_H, dt/2)
                    U = late_U @ early_U
                    fine, coarse = apply(U, current), apply(coarse_U, current)
                    error = float(np.linalg.norm(fine-coarse)/3)
                    scale = atol+rtol*max(np.linalg.norm(fine), np.linalg.norm(coarse))
                    scaled = error/scale
                    if not np.isfinite(scaled):
                        diagnostics['rejected_steps'] += 1
                        return finish('failed', 'tolerance_exhausted')
                    factor = 5.0 if scaled == 0 else min(5.0, max(.2, .9*scaled**(-1/3)))
                    if scaled > 1:
                        diagnostics['rejected_steps'] += 1
                        step = dt*min(1.0, factor)
                        continue
                else:
                    if cached_segment != boundary_index:
                        cached_spectrum = np.linalg.eigh(constant_H)
                        cached_segment = boundary_index
                    values, vectors = cached_spectrum
                    U = (vectors*_spectral_phases(values, np.array([dt]))[0]) @ vectors.conj().T
                    fine, error, scaled = apply(U, current), 0.0, 0.0
                if not np.all(np.isfinite(fine)) or not np.all(np.isfinite(U)):
                    raise ValueError('nonfinite propagation')
            except (ValueError, np.linalg.LinAlgError, FloatingPointError, OverflowError):
                diagnostics['rejected_steps'] += 1
                return finish('failed', 'nonfinite_propagator')
            current, t = fine, float(next_time)
            total_U = U @ total_U
            diagnostics['accepted_steps'] += 1
            diagnostics['maximum_local_error'] = max(diagnostics['maximum_local_error'], error)
            diagnostics['maximum_scaled_local_error'] = max(diagnostics['maximum_scaled_local_error'], float(scaled))
            physical_diagnostics()
            if boundary_index < len(boundaries) and t == boundaries[boundary_index]:
                diagnostics['boundary_times_s'].append(t)
                boundary_index += 1
            if smooth:
                step = min(dt*factor, step_limit)
        try:
            H = generator(t)
        except (ValueError, FloatingPointError, OverflowError):
            return finish('failed', 'nonfinite_hamiltonian')
        try:
            with np.errstate(over='raise', invalid='raise'):
                measured = _measure(current, operators, H)
        except (ValueError, FloatingPointError, OverflowError):
            return finish('failed', 'nonfinite_observable')
        if any(not np.all(np.isfinite(value)) for value in measured.values()):
            return finish('failed', 'nonfinite_observable')
        for name, value in measured.items():
            output[name][index] = value
        if index in selected:
            snapshots[index] = current.copy()
        completed += 1
    return finish('success')
