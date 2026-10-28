# Scenario 1 — Software Verification

**Goal.** Verify the finite-dimensional state model, partial traces and open-boundary transverse-field Ising evolution implemented in Python. This scenario corresponds to the software-verification thesis without reproducing its full manuscript.

**Model and units.** For 2–6 spins the basis is `|q₀…qₙ₋₁⟩` with spin 0 leftmost. The Pauli-normalized model is `H/ℏ = −J Σ σᶻᵢσᶻᵢ₊₁ − h(t) Σ σˣᵢ`; `J` and `h` are angular frequencies in s⁻¹, and time is in seconds. Only links 0–1 through N−2–N−1 are included. Constant-H evolution uses a Hermitian spectral decomposition; smooth drives use adaptive second-order exponential midpoint steps with a one-step/two-half-step local error estimate. Separate tolerance tightening checks global convergence. These are ideal model parameters, not calibrated apparatus values.

**Commands.** From the repository root, install `pyproject.toml` into a virtual environment and run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The complete suite includes Hensen reanalysis and therefore requires the exact 2015/2016 source data from their original 4TU/Figshare records, with checksums in `data/references/*/manifest.json`. Independent tools are optional and should be installed in a separate test environment:

```powershell
py -3.13 -m venv .venv-stage5-validation
.\.venv-stage5-validation\Scripts\python.exe -m pip install -e .
.\.venv-stage5-validation\Scripts\python.exe -m pip install -r requirements-stage5-validation.txt
.\.venv-stage5-validation\Scripts\python.exe scripts\validate_stage5b_qutip.py --all --output research\outputs\validation_qutip.json
.\.venv-stage5-validation\Scripts\python.exe scripts\validate_stage5b_quspin.py --all --output research\outputs\validation_quspin.json
```

**Checked reference.** The recorded 2026-10-28 desktop review ran 190 Python tests successfully. The five independent Stage 5B fixtures are static OBC receiver, noncommuting smooth receiver field, Gaussian local positive control, sender local unitary/no-signaling, and piecewise field with boundary splitting. Across these five cases, maximal state-vector L2 differences were 9.94×10⁻¹⁰ for QuTiP 5.3.0 and 1.01×10⁻⁹ for QuSpin 1.0.1 plus SciPy DOP853, under a 1×10⁻⁸ threshold. The three reported metrics are maxima **across** the five fixtures: state-vector L2 error, receiver-state trace distance and local Pauli-`z` expectation difference; they are not three fixtures. Fixed historical validation file checksums are in `research/manifest.json`.

**Limits.** These checks validate equivalence for the stated finite models, units and OBC, not large-N scaling or reproduction of a calibrated Hensen apparatus. QuSpin's published periodic example is not used as an OBC reference. Norm and unitarity checks accompany, but do not replace, independent trajectory and convergence comparisons.

**Sources.** Blanes et al., *Physics Reports* 470 (2009), DOI [10.1016/j.physrep.2008.11.001](https://doi.org/10.1016/j.physrep.2008.11.001); Weinberg & Bukov, *SciPost Physics* 2 (2017), DOI [10.21468/SciPostPhys.2.1.003](https://doi.org/10.21468/SciPostPhys.2.1.003); Johansson et al., *Computer Physics Communications* 183 (2012), DOI [10.1016/j.cpc.2012.02.021](https://doi.org/10.1016/j.cpc.2012.02.021); Pfeuty, *Annals of Physics* 57 (1970), DOI [10.1016/0003-4916(70)90270-8](https://doi.org/10.1016/0003-4916(70)90270-8).
