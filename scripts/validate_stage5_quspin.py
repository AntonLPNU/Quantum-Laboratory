"""Необов'язкове незалежне порівняння TFIM з QuSpin у σ-нормуванні."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum_lab.tfim import FieldSchedule, evolve_static, open_tfim_hamiltonian
from scripts.stage5_validation_common import comparison_report

TOLERANCE = {"hamiltonian": 2e-12, "spectrum": 2e-11, "state": 2e-10, "observable": 2e-10}


def _load_quspin():
    try:
        import quspin
        from quspin.basis import spin_basis_1d
        from quspin.operators import hamiltonian
    except ImportError as error:
        raise SystemExit("QuSpin is unavailable. Install requirements-stage5-validation.txt in the isolated validation environment.") from error
    return quspin, spin_basis_1d, hamiltonian


def _quspin_to_project_indices(basis, n_spins):
    """Map project |q0...qN-1> big-endian indices to QuSpin basis rows.

    QuSpin spin_basis_1d encodes site 0 in the least-significant state bit;
    the project's q0 is the most-significant bit. The integer state label is
    therefore the same, but basis.states ordering is looked up explicitly.
    """
    positions = {int(state): row for row, state in enumerate(basis.states)}
    labels = range(1 << n_spins)
    try:
        return np.asarray([positions[label] for label in labels], dtype=int)
    except KeyError as error:
        raise RuntimeError("QuSpin basis does not contain the full computational basis") from error


def _quspin_operator(n_spins, J, h, periodic=False):
    _, spin_basis_1d, hamiltonian = _load_quspin()
    basis = spin_basis_1d(n_spins, pauli=1)
    # QuSpin site 0 is the least-significant bit, opposite tensor-site order.
    # A homogeneous open path or ring is invariant under this full reversal.
    zz = [[-float(J), i, (i + 1) % n_spins] for i in range(n_spins if periodic else n_spins - 1)]
    x = [[-float(h), i] for i in range(n_spins)]
    # QuSpin prints successful consistency checks; capture these so stdout remains valid JSON.
    with contextlib.redirect_stdout(io.StringIO()):
        operator = hamiltonian([["zz", zz], ["x", x]], [], basis=basis,
                               dtype=np.complex128, check_symm=True, check_herm=True,
                               check_pcon=False)
    order = _quspin_to_project_indices(basis, n_spins)
    matrix = operator.toarray()[np.ix_(order, order)]
    return operator, basis, order, matrix


def _quspin_matrix(n_spins, J, h, periodic=False):
    return _quspin_operator(n_spins, J, h, periodic)[3]


def _base_model(n_spins, J, h, times, boundary="open", seed=None, initial_state=None):
    return {"n_spins": n_spins, "boundary": boundary,
            "pauli_normalization": "sigma_eigenvalues_pm1",
            "time_unit": "s", "coupling_unit": "s^-1",
            "hamiltonian_convention": "H/hbar=-J*sum(zz)-h*sum(x)",
            "J_s^-1": float(J), "h_s^-1": float(h),
            "times_s": [float(value) for value in times],
            "initial_state_preparation": "normalized seeded complex standard-normal ket" if seed is not None else None,
            "seed": seed,
            "initial_ket_real_imag": ([[float(value.real), float(value.imag)] for value in initial_state]
                                       if initial_state is not None else None)}


def run_open_chain_sweep():
    """Порівняти гамільтоніан, спектр, стан і спостережувані для скінченних OBC-ланцюгів."""
    quspin, _, _ = _load_quspin()
    import scipy
    cases = []
    maximum = {key: 0.0 for key in ("max_hamiltonian_error", "max_spectrum_error", "max_state_error", "max_observable_error")}
    for n_spins in range(2, 7):
        for J, h in ((0.73, -0.31), (0.0, 0.8), (-0.4, 0.0)):
            times = np.linspace(0.0, 1.7, 18)
            project_h = open_tfim_hamiltonian(n_spins, J, h)
            reference_operator, basis, order, reference_h = _quspin_operator(n_spins, J, h)
            h_error = float(np.max(np.abs(project_h-reference_h)))
            spectrum_error = float(np.max(np.abs(np.linalg.eigvalsh(project_h)-np.linalg.eigvalsh(reference_h))))
            rng = np.random.default_rng(7100 + n_spins)
            initial = rng.normal(size=2**n_spins)+1j*rng.normal(size=2**n_spins)
            initial /= np.linalg.norm(initial)
            project_result = evolve_static(initial, project_h, times, save_states_at=range(len(times)))
            quspin_initial = np.empty_like(initial)
            quspin_initial[order] = initial
            # QuSpin integrates the Schrödinger equation independently (DOP853).
            evolved_quspin = reference_operator.evolve(quspin_initial, 0.0, times, eom="SE",
                                                        solver_name="dop853", iterate=False,
                                                        atol=1e-12, rtol=1e-12, verbose=False)
            ref_states = evolved_quspin[order, :].T
            project_states = np.asarray([project_result.snapshots[i] for i in range(len(times))])
            state_error = float(np.max(np.linalg.norm(project_states-ref_states, axis=1)))
            z = np.diag([1.0, -1.0]).astype(complex)
            local_z = [np.kron(np.eye(2**site), np.kron(z, np.eye(2**(n_spins-site-1)))) for site in range(n_spins)]
            project_mz = project_result.observables["sigma_z"]
            ref_mz = np.asarray([[np.vdot(state, op@state).real for op in local_z] for state in ref_states])
            observable_error = float(np.max(np.abs(project_mz-ref_mz)))
            errors = {"max_hamiltonian_error": h_error, "max_spectrum_error": spectrum_error,
                      "max_state_error": state_error, "max_observable_error": observable_error}
            limits = dict(zip(errors, (TOLERANCE["hamiltonian"], TOLERANCE["spectrum"], TOLERANCE["state"], TOLERANCE["observable"])))
            passed = all(errors[key] <= limits[key] for key in errors)
            report = comparison_report(_base_model(n_spins, J, h, times, seed=7100+n_spins, initial_state=initial),
                                       _base_model(n_spins, J, h, times, seed=7100+n_spins, initial_state=initial), {**errors, "thresholds": limits, "passed": passed})
            cases.append(report)
            for key, value in errors.items():
                maximum[key] = max(maximum[key], value)
    return {"fixture": "open-chain-sweep", "status": "pass" if all(c["status"] == "pass" for c in cases) else "fail",
            "quspin_version": quspin.__version__,
            "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
            "reference": "QuSpin spin_basis_1d full computational basis, independently constructed OBC coupling lists",
            "cases": cases, "maximum_differences": maximum}


def _periodic_kronecker_reference(n_spins, J, h):
    """Build published periodic-chain fixture independently of QuSpin and app API."""
    I = np.eye(2, dtype=complex)
    X = np.array([[0, 1], [1, 0]], dtype=complex)
    Z = np.diag([1, -1]).astype(complex)
    def local(op, site):
        factors = [op if i == site else I for i in range(n_spins)]
        result = factors[0]
        for factor in factors[1:]:
            result = np.kron(result, factor)
        return result
    H = np.zeros((2**n_spins, 2**n_spins), complex)
    for site in range(n_spins):
        H -= J*local(Z, site)@local(Z, (site+1) % n_spins)
    for site in range(n_spins):
        H -= h*local(X, site)
    return H


def run_periodic_l8_fixture():
    """Перевірити periodic L=8 літературний fixture як окрему periodic-модель."""
    quspin, _, _ = _load_quspin()
    import scipy
    n_spins, J, h = 8, 1.0, float(np.sqrt(2.0))
    qspin_h = _quspin_matrix(n_spins, J, h, periodic=True)
    independent_h = _periodic_kronecker_reference(n_spins, J, h)
    difference = float(np.max(np.abs(np.linalg.eigvalsh(qspin_h)-np.linalg.eigvalsh(independent_h))))
    return {"fixture": "published-tfim-periodic-L8", "classification": "periodic_reference_only",
            "status": "pass" if difference <= TOLERANCE["spectrum"] else "fail",
            "quspin_version": quspin.__version__,
            "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
            "n_spins": n_spins, "boundary": "periodic",
            "J_s^-1": J, "h_s^-1": h, "h_over_J": h/J,
            "pauli_normalization": "sigma_eigenvalues_pm1", "time_unit": "s", "coupling_unit": "s^-1",
            "source": "Weinberg & Bukov, SciPost Phys. 7, 020 (2019), DOI 10.21468/SciPostPhys.7.2.020; periodic example is reported separately and is not an OBC check",
            "maximum_spectrum_error": difference, "threshold": TOLERANCE["spectrum"],
            "projected_to_obc": False}


def main():
    """Розібрати fixture/output параметри та виконати відповідну незалежну перевірку."""
    parser = argparse.ArgumentParser(description="Independent optional QuSpin checks for Stage 5 OBC TFIM.")
    parser.add_argument("--fixture", choices=("open-chain-sweep", "published-tfim-periodic-L8"), default="open-chain-sweep")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    reports = ([run_open_chain_sweep(), run_periodic_l8_fixture()] if args.all else
               [run_periodic_l8_fixture() if args.fixture == "published-tfim-periodic-L8" else run_open_chain_sweep()])
    print(json.dumps(reports[0] if len(reports) == 1 else reports, indent=2, sort_keys=True, allow_nan=False))
    if any(report["status"] != "pass" for report in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
