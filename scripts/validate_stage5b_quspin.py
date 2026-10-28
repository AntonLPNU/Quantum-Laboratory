"""Independent QuSpin operator and DOP853 checks for Stage 5B receiver dynamics."""
from __future__ import annotations

import contextlib
import io
import json
import platform
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum_lab.multispin import partial_trace_subsystems
from quantum_lab.tfim import FieldSchedule, evolve_tfim

TOL = 1e-8


def _initial(n=4):
    state = np.zeros(2**n, complex)
    state[1 << (n-2)] = 1/np.sqrt(2)
    state[1 << (n-1)] = -1/np.sqrt(2)
    return state


def _operator(n=4, J=1e6):
    try:
        import quspin
        from quspin.basis import spin_basis_1d
        from quspin.operators import hamiltonian
    except ImportError as exc:
        raise SystemExit("Install requirements-stage5-validation.txt in the isolated validation environment") from exc
    basis = spin_basis_1d(n, pauli=True)
    # QuSpin's full spin_basis_1d labels have site 0 as the most significant
    # bit in this basis ordering; physical big-endian site labels therefore
    # map directly. The validator independently checks this with local Zs.
    zz = [[-J, site, site+1] for site in range(1, n-1)]
    x_receiver = [[-1., site] for site in range(1, n)]
    x_pulse = [[-1., 2]]
    with contextlib.redirect_stdout(io.StringIO()):
        Hzz = hamiltonian([["zz", zz]], [], basis=basis, dtype=np.complex128,
                           check_herm=True, check_symm=True, check_pcon=False).toarray()
        Hx = hamiltonian([["x", x_receiver]], [], basis=basis, dtype=np.complex128,
                         check_herm=True, check_symm=True, check_pcon=False).toarray()
        Hp = hamiltonian([["x", x_pulse]], [], basis=basis, dtype=np.complex128,
                         check_herm=True, check_symm=True, check_pcon=False).toarray()
    positions = {int(label): row for row, label in enumerate(basis.states)}
    order = np.asarray([positions[index] for index in range(1 << n)], int)
    return quspin, basis, order, Hzz[np.ix_(order, order)], Hx[np.ix_(order, order)], Hp[np.ix_(order, order)]


def _run_case(label, h_schedule, times, pulse=None, sender_flip=False):
    n, J = 4, 1e6
    quspin, basis, order, Hzz, Hx, Hp = _operator(n, J)
    initial = _initial(n)
    if sender_flip:
        flipped = np.empty_like(initial)
        for index, amplitude in enumerate(initial):
            flipped[index ^ (1 << (n-1))] = amplitude
        initial = flipped
    # The independently assembled matrices are permuted into project tensor
    # order below, so the integration vector uses that same explicit order.
    qinitial = initial.copy()

    def rhs(time, state):
        h = h_schedule.value_at(float(time))
        g = 0.0 if pulse is None else pulse[1].value_at(float(time))
        return -1j * ((Hzz+h*Hx+g*Hp) @ state)

    edges = [float(times[0])]
    if h_schedule.kind == "piecewise_constant":
        edges.extend(e for e in h_schedule.edges_s if times[0] < e < times[-1])
    edges.append(float(times[-1]))
    state = qinitial
    states = {}
    for segment, (start, stop) in enumerate(zip(edges, edges[1:])):
        selected = times[(times >= start) & (times <= stop)]
        if segment and selected.size and selected[0] == start:
            selected = selected[1:]
        targets = np.unique(np.concatenate(([start], selected)))
        solution = solve_ivp(rhs, (start, stop), state, method="DOP853", t_eval=targets,
                             rtol=2e-13, atol=2e-15, max_step=max((stop-start)/10, 1e-15))
        if not solution.success:
            raise RuntimeError(solution.message)
        for t, value in zip(targets, solution.y.T):
            states[float(t)] = value
        state = solution.y[:, -1]
    qstates = np.asarray([states[float(t)] for t in times])

    controls = {} if pulse is None else {2: pulse[1]}
    project = evolve_tfim(initial, n, J, h_schedule, times, active_sites=range(1, n),
                          local_controls=controls, rtol=1e-12, atol=1e-14,
                          max_steps=100000, save_states_at=range(len(times)))
    if project.status != "success":
        raise RuntimeError(project.error)
    p_states = np.asarray([project.snapshots[i] for i in range(len(times))])
    state_error = float(np.max(np.linalg.norm(p_states-qstates, axis=1)))
    reduced_error = 0.0
    for p_state, q_state in zip(p_states, qstates):
        rho_q = np.outer(q_state, q_state.conj())
        rho_p = np.outer(p_state, p_state.conj())
        q_r = np.empty((8, 8), complex)
        # Independent partial trace over sender: sum the A=0 and A=1 blocks.
        q_r[:] = rho_q[:8, :8] + rho_q[8:, 8:]
        p_r = partial_trace_subsystems(rho_p, [1, 2, 3])
        delta = (q_r-p_r + (q_r-p_r).conj().T)/2
        reduced_error = max(reduced_error, float(.5*np.sum(np.abs(np.linalg.eigvalsh(delta)))))
    observable_error = 0.0
    z = np.diag([1., -1.]).astype(complex)
    for t_index, (q_state, p_state) in enumerate(zip(qstates, p_states)):
        q_values, p_values = [], project.observables["sigma_z"][t_index, 1:]
        for site in range(1, n):
            operator = np.eye(1 << site)
            operator = np.kron(np.eye(1 << site), np.kron(z, np.eye(1 << (n-site-1))))
            q_values.append(float(np.vdot(q_state, operator@q_state).real))
        observable_error = max(observable_error, float(np.max(np.abs(np.asarray(q_values)-p_values))))
    errors = {"max_state_l2": state_error, "max_receiver_trace_distance": reduced_error,
              "max_receiver_sigma_z_abs": observable_error}
    return {"fixture": label, "errors": errors, "threshold": TOL,
            "quspin_version": quspin.__version__, "solver": {"reference": "independent SciPy DOP853", "rtol": 2e-13,
            "atol": 2e-15, "project": project.diagnostics},
            "passed": max(errors.values()) <= TOL}


def run_all():
    """Виконати всі заблоковані незалежні QuSpin fixtures для Dynamic Receiver."""
    # Collapse floating-point near-duplicates at piecewise schedule edges.
    times = np.unique(np.round(np.r_[np.linspace(0, 1e-5, 31), 4e-6, 7e-6], 15))
    static = FieldSchedule.constant(0.8e6)
    smooth = FieldSchedule.gaussian(0.25e6, 5e-6, 1e-6, offset=0.8e6)
    piecewise = FieldSchedule.piecewise_constant([0, 4e-6, 7e-6, 1e-5], [0.8e6, -0.2e6, 0.4e6])
    pulse = (2, FieldSchedule.gaussian(0.06e6, 5e-6, 1e-6))
    cases = [_run_case("static_receiver_oBC", static, times),
             _run_case("noncommuting_smooth_receiver_field", smooth, times),
             _run_case("smooth_local_gaussian_positive_control", static, times, pulse),
             _run_case("sender_local_unitary_no_signaling", static, times, sender_flip=True),
             _run_case("piecewise_field_with_explicit_segment_boundaries", piecewise, times)]
    return {"status": "pass" if all(row["passed"] for row in cases) else "fail",
            "reference": "QuSpin spin_basis_1d(pauli=True) independently assembles OBC receiver terms; SciPy DOP853 integrates the QuSpin matrix; Pauli units s^-1 and time seconds",
            "python_version": platform.python_version(), "n_spins": 4,
            "times_s": times.tolist(), "cases": cases, "threshold": TOL,
            "boundary_conditions": "open; sender has no Hamiltonian term or receiver coupling"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="run all deterministic receiver fixtures")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_all()
    encoded = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    if report["status"] != "pass":
        raise SystemExit(1)
