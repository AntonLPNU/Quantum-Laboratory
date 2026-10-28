# Quantum Laboratory

**Version:** 0.5.0 Research Preview. **Software author:** Anton Volos (Волос Антон Володимирович). Author-owned project software and documentation are covered by the MIT License. Third-party components and datasets retain their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). A binary release has not yet been published.

Quantum Laboratory combines a Python scientific core for two-spin state calculations and 2–6 spin open-boundary transverse-field Ising dynamics with the interactive Orbital Lab interface. The Windows desktop package uses Electron for its window and a bundled Python backend. All physical quantities are computed in Python; 3D spin positions are schematic and are not particle trajectories.

## Run from source on Windows

Use Python 3.10+ and run `start_windows.bat` from the project root. It creates a local virtual environment, installs dependencies, builds the React frontend, chooses an available localhost port and waits for the Python API before opening the interface. The first run needs package-index access. For tests, run `run_tests_windows.bat` or `python -m unittest discover -s tests -v` from an installed environment. Full Hensen regression tests require separately obtained source datasets; provenance and hashes are documented in `docs/source-register.md`.

The project includes an Electron shell, React/Three.js interface and Python packaging scripts. Installer and portable EXEs are not part of this source release; public binaries will follow a separate review. See [desktop setup and limitations](docs/desktop/README.md).

## Implemented research functions

- Bell-state preparation, local operations and projective measurements; density matrices, partial traces, concurrence, correlations and fixed/optimized CHSH.
- Independent local phase-damping channels on the complete two-spin state and exact 21×21 parameter sweeps.
- Pauli-normalized open-boundary TFIM with constant, piecewise and smooth fields, 2–6 spins, and numerical diagnostics.
- Stage 5B Dynamic Receiver, exact reduced-state comparisons, fixed finite-shot Quantum Domino protocol and Deviation Analyzer.
- Separate read-only reanalysis of original Hensen 2015/2016 datasets, not a full apparatus simulation.
- Local experiment save/load/compare and JSON/CSV export; offline scientific help in Orbital Lab.

The models are idealized. The program does not establish a new remote-signaling effect, calibrated decoherence time, or large-system performance. Scientific assumptions and independent checks are in [SCIENTIFIC_METHODS.md](SCIENTIFIC_METHODS.md), [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md), [docs/scientific_model.md](docs/scientific_model.md), and [research/](research/README.md). The three reproducible scenarios correspond to software verification, phase damping and Quantum Domino, with separate descriptions, commands and expected numerical checks.

## Citation, contributions and release review

The software author and version are in [CITATION.cff](CITATION.cff); no DOI, ORCID or release date has been invented. Cite original scientific papers and datasets separately. [CONTRIBUTING.md](CONTRIBUTING.md) explains tests and contribution expectations; [SECURITY.md](SECURITY.md) explains private vulnerability reporting. The [third-party inventory](THIRD_PARTY_NOTICES.md) records licensing boundaries. Raw Hensen data, local binaries and student-conference manuscripts are not included in this public source snapshot.
