"""Необов'язкова незалежна звірка гладких TFIM-керувань із QuTiP sesolve."""

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
from scripts.stage5_validation_common import comparison_report

THRESHOLDS = {"state": 5e-7, "observable": 5e-7, "reduced_density": 5e-7}


def _load_qutip():
    try:
        import qutip
    except ImportError as error:
        raise SystemExit("QuTiP is unavailable. Install requirements-stage5-validation.txt in the isolated validation environment.") from error
    return qutip


def _tensor_local(qutip, operator, site, n_spins):
    factors = [qutip.qeye(2) for _ in range(n_spins)]
    factors[site] = operator
    return qutip.tensor(factors)


def _reorder_from_sorted(matrix, sorted_sites, target_sites):
    """Permute a QuTiP sorted ptrace result into the project's explicit keep order."""
    dimension = 1 << len(sorted_sites)
    permutation = np.zeros((dimension, dimension), dtype=complex)
    for source in range(dimension):
        source_bits = [(source >> (len(sorted_sites)-1-i)) & 1 for i in range(len(sorted_sites))]
        selected = {site: source_bits[i] for i, site in enumerate(sorted_sites)}
        target = 0
        for site in target_sites:
            target = 2*target + selected[site]
        permutation[target, source] = 1.0
    return permutation @ matrix @ permutation.conj().T


def _model(n_spins, times, seed=None, initial_state=None):
    return {"n_spins": n_spins, "boundary": "open", "pauli_normalization": "sigma_eigenvalues_pm1",
            "time_unit": "s", "coupling_unit": "s^-1",
            "hamiltonian_convention": "H/hbar=-J*sum(zz)-h(t)*sum(x)",
            "J_s^-1": 0.61, "h_s^-1": {"kind": "gaussian", "amplitude_s^-1": 0.55,
                                            "center_s": 0.9, "width_s": 0.27, "offset_s^-1": 0.18},
            "times_s": [float(value) for value in times],
            "initial_state_preparation": "normalized seeded complex standard-normal ket" if seed is not None else None,
            "seed": seed,
            "initial_ket_real_imag": ([[float(value.real), float(value.imag)] for value in initial_state]
                                       if initial_state is not None else None)}


def run_smooth_controls():
    """Зіставити гаусове керування, контрольне поле, no-signaling та стрибки полів."""
    qutip = _load_qutip()
    import scipy
    times = np.linspace(0.0, 2.2, 29)
    schedule = FieldSchedule.gaussian(amplitude=0.55, center_s=0.9, width_s=0.27, offset=0.18)
    J = 0.61
    cases = []
    maxima = {"max_state_error": 0.0, "max_observable_error": 0.0, "max_reduced_density_error": 0.0}
    sx, sz = qutip.sigmax(), qutip.sigmaz()
    for n_spins in range(2, 7):
        identity = qutip.tensor([qutip.qeye(2) for _ in range(n_spins)])
        H0 = 0*identity
        for site in range(n_spins-1):
            H0 += -J*_tensor_local(qutip, sz, site, n_spins)*_tensor_local(qutip, sz, site+1, n_spins)
        Hx = 0*identity
        for site in range(n_spins):
            Hx += -_tensor_local(qutip, sx, site, n_spins)
        h_of_t = lambda t, **kwargs: schedule.value_at(float(t))
        hamiltonian = [H0, [Hx, h_of_t]]
        rng = np.random.default_rng(8300+n_spins)
        initial = rng.normal(size=2**n_spins)+1j*rng.normal(size=2**n_spins)
        initial /= np.linalg.norm(initial)
        initial_q = qutip.Qobj(initial, dims=[[2]*n_spins, [1]*n_spins])
        e_ops = [_tensor_local(qutip, sz, site, n_spins) for site in range(n_spins)]
        reference = qutip.sesolve(hamiltonian, initial_q, times, e_ops=e_ops,
                                  options={"rtol": 1e-12, "atol": 1e-14, "store_states": True,
                                           "nsteps": 100000})
        project = evolve_tfim(initial, n_spins, J, schedule, times,
                              rtol=1e-10, atol=1e-12, max_steps=100000,
                              save_states_at=range(len(times)))
        if project.status != "success":
            raise RuntimeError(f"project solver failed for N={n_spins}: {project.error}")
        state_errors = []
        observable_errors = []
        reduced_errors = []
        keep = [n_spins-1, 0]
        sorted_keep = sorted(keep)
        for index, q_state in enumerate(reference.states):
            project_state = project.snapshots[index]
            state_errors.append(float(np.linalg.norm(project_state-q_state.full().ravel())))
            q_mz = np.asarray([values[index] for values in reference.expect]).real
            p_mz = project.observables["sigma_z"][index]
            observable_errors.append(float(np.max(np.abs(q_mz-p_mz))))
            if index in (0, len(times)//2, len(times)-1):
                q_reduced_sorted = q_state.ptrace(sorted_keep).full()
                q_reduced_ordered = _reorder_from_sorted(q_reduced_sorted, sorted_keep, keep)
                p_reduced = partial_trace_subsystems(project_state, keep=keep)
                reduced_errors.append(float(np.max(np.abs(q_reduced_ordered-p_reduced))))
        errors = {"max_state_error": max(state_errors), "max_observable_error": max(observable_errors),
                  "max_reduced_density_error": max(reduced_errors)}
        maximum_error = max(errors.values())
        passed = (errors["max_state_error"] <= THRESHOLDS["state"] and
                  errors["max_observable_error"] <= THRESHOLDS["observable"] and
                  errors["max_reduced_density_error"] <= THRESHOLDS["reduced_density"])
        case = comparison_report(_model(n_spins, times, 8300+n_spins, initial),
                                 _model(n_spins, times, 8300+n_spins, initial),
                                 {**errors, "thresholds": THRESHOLDS, "max_invariant_drift": float(project.diagnostics["norm_error"]),
                                  "project_solver": project.diagnostics, "qutip_solver": {"method": "sesolve",
                                      "rtol": 1e-12, "atol": 1e-14, "states_returned": len(reference.states)},
                                  "keep_order_tested": keep, "passed": passed})
        cases.append(case)
        for key, value in errors.items():
            maxima[key] = max(maxima[key], value)
    return {"fixture": "smooth-controls", "status": "pass" if all(case["status"] == "pass" for case in cases) else "fail",
            "qutip_version": qutip.__version__,
            "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
            "reference": "QuTiP sesolve with independently tensor-assembled open-chain Pauli Hamiltonian; Gaussian drive in s^-1 and seconds",
            "cases": cases, "maximum_differences": maxima, "thresholds": THRESHOLDS}


def main():
    """Запустити QuTiP порівняння та видати машинозчитуваний JSON звіт."""
    import argparse
    parser = argparse.ArgumentParser(description="Independent optional QuTiP comparison for Stage 5 driven OBC TFIM.")
    parser.add_argument("--fixture", choices=("smooth-controls",), default="smooth-controls")
    parser.add_argument("--all", action="store_true")
    parser.parse_args()
    report = run_smooth_controls()
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
