"""Independent QuTiP checks of Stage 5B's isolated full A tensor R state."""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum_lab.multispin import partial_trace_subsystems
from quantum_lab.tfim import FieldSchedule, evolve_tfim

TOL = 1e-8


def _initial(n=4):
    state = np.zeros(2**n, complex)
    state[1 << (n-2)] = 1 / np.sqrt(2)  # |0 1 0 ...>
    state[1 << (n-1)] = -1 / np.sqrt(2)  # -|1 0 0 ...>
    return state


def _local(qutip, operator, site, n):
    factors = [qutip.qeye(2) for _ in range(n)]
    factors[site] = operator
    return qutip.tensor(factors)


def _projectors(n, J, h_schedule, pulse=None):
    import qutip
    sx, sz = qutip.sigmax(), qutip.sigmaz()
    dim = 2**n
    identity = qutip.tensor([qutip.qeye(2) for _ in range(n)])
    hj = 0 * identity
    for site in range(1, n-1):
        hj += -J * _local(qutip, sz, site, n) * _local(qutip, sz, site+1, n)
    hx = 0 * identity
    for site in range(1, n):
        hx += -_local(qutip, sx, site, n)
    def schedule_value(schedule, time):
        value = float(time)
        if schedule.kind == "piecewise_constant":
            value = min(max(value, schedule.edges_s[0]), schedule.edges_s[-1])
        return schedule.value_at(value)
    terms = [hj, [hx, lambda t, **kwargs: schedule_value(h_schedule, t)]]
    if pulse is not None:
        hp = -_local(qutip, sx, pulse[0], n)
        terms.append([hp, lambda t, **kwargs: schedule_value(pulse[1], t)])
    return terms


def _compare_case(label, h_schedule, times, pulse=None, sender_flip=False):
    import qutip
    n, J = 4, 1e6
    initial = _initial(n)
    if sender_flip:
        # Local Pauli-X on site zero is an independent direct basis permutation.
        flipped = np.empty_like(initial)
        for index, amplitude in enumerate(initial):
            flipped[index ^ (1 << (n-1))] = amplitude
        initial = flipped
    initial_q = qutip.Qobj(initial, dims=[[2]*n, [1]*n])
    qtimes = np.asarray(times, float)
    edges = [float(qtimes[0])]
    if h_schedule.kind == "piecewise_constant":
        edges.extend(edge for edge in h_schedule.edges_s if qtimes[0] < edge < qtimes[-1])
    edges.append(float(qtimes[-1]))
    states_at_time = {}
    current = initial_q
    for interval_index, (start, stop) in enumerate(zip(edges, edges[1:])):
        selected = qtimes[(qtimes >= start) & (qtimes <= stop)]
        if interval_index and selected.size and selected[0] == start:
            selected = selected[1:]
        targets = np.unique(np.concatenate(([start], selected)))
        ref_part = qutip.sesolve(_projectors(n, J, h_schedule, pulse), current, targets,
                                options={"rtol": 2e-12, "atol": 2e-14, "store_states": True,
                                         "nsteps": 100000})
        for t, state in zip(targets, ref_part.states):
            states_at_time[float(t)] = state
        current = ref_part.states[-1]
    q_states = [states_at_time[float(t)] for t in qtimes]
    local_controls = {} if pulse is None else {pulse[0]: pulse[1]}
    project = evolve_tfim(initial, n, J, h_schedule, qtimes,
                          local_controls=local_controls, active_sites=range(1, n),
                          rtol=1e-12, atol=1e-14, max_steps=100000,
                          save_states_at=range(len(qtimes)))
    if project.status != "success":
        raise RuntimeError(f"project solver failed: {project.error}")
    state_differences, reduced_differences, observable_differences = [], [], []
    for i, q_state in enumerate(q_states):
        qket = q_state.full().ravel()
        pket = project.snapshots[i]
        state_differences.append(float(np.linalg.norm(qket-pket)))
        qrho = np.outer(qket, qket.conj())
        prho = np.outer(pket, pket.conj())
        qr = qutip.Qobj(qrho, dims=[[2]*n, [2]*n]).ptrace([1, 2, 3]).full()
        pr = partial_trace_subsystems(prho, [1, 2, 3])
        hermitian_difference = (qr - pr + (qr - pr).conj().T) / 2
        reduced_differences.append(float(.5*np.sum(np.abs(np.linalg.eigvalsh(hermitian_difference)))))
        # Independently evaluate every local receiver sigma-z expectation.
        qz = [float(np.real(qutip.expect(_local(qutip, qutip.sigmaz(), s, n), q_state))) for s in range(1, n)]
        pz = np.asarray(project.observables["sigma_z"][i, 1:])
        observable_differences.append(float(np.max(np.abs(np.asarray(qz)-pz))))
    errors = {"max_state_l2": max(state_differences),
              "max_receiver_trace_distance": max(reduced_differences),
              "max_receiver_sigma_z_abs": max(observable_differences)}
    return {"fixture": label, "errors": errors, "threshold": TOL,
            "solver": {"qutip": "sesolve", "qutip_rtol": 2e-12, "qutip_atol": 2e-14,
                       "project": project.diagnostics},
            "passed": max(errors.values()) <= TOL}


def run_all():
    """Зіставити Stage 5B receiver trajectories із QuTiP за еквівалентної моделі."""
    try:
        import qutip
    except ImportError as exc:
        raise SystemExit("Install requirements-stage5-validation.txt in the isolated validation environment") from exc
    # Snap ULP-near representations of preregistered interval edges to one
    # unique timestamp; duplicate adjacent values can force minimum-step exits.
    times = np.unique(np.round(np.r_[np.linspace(0, 1e-5, 31), 4e-6, 7e-6], 15))
    static = FieldSchedule.constant(0.8e6)
    smooth = FieldSchedule.gaussian(0.25e6, 5e-6, 1e-6, offset=0.8e6)
    piecewise = FieldSchedule.piecewise_constant([0, 4e-6, 7e-6, 1e-5], [0.8e6, -0.2e6, 0.4e6])
    pulse = (2, FieldSchedule.gaussian(0.06e6, 5e-6, 1e-6))
    cases = [
        _compare_case("static_receiver_oBC", static, times),
        _compare_case("noncommuting_smooth_receiver_field", smooth, times),
        _compare_case("smooth_local_gaussian_positive_control", static, times, pulse),
        _compare_case("sender_local_unitary_no_signaling", static, times, sender_flip=True),
        _compare_case("piecewise_field_with_stage5a_boundary_splitting", piecewise, times),
    ]
    return {"status": "pass" if all(case["passed"] for case in cases) else "fail",
            "reference": "QuTiP sesolve; independently tensor-assembled OBC Pauli Hamiltonian on sites 1..N-1; H/hbar in s^-1 and t in s",
            "qutip_version": qutip.__version__, "python_version": platform.python_version(),
            "n_spins": 4, "sender_site": 0, "receiver_sites": [1, 2, 3],
            "time_grid_s": times.tolist(), "cases": cases, "threshold": TOL,
            "invariants": "project solver reports norm, trace, Hermiticity, positivity and unitarity defect; independent trajectory comparison also required"}


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
