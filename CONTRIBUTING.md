# Contributing to Quantum Laboratory

Quantum Laboratory is a research program. Before submitting changes, read `AGENTS.md`, `docs/scientific_model.md` and `docs/research_guide.md`. Keep the Python scientific core separate from the React/Electron interface; interface code must display core results rather than implement an alternate physical model.

## Development checks

1. Create a local Python virtual environment and install the project from `pyproject.toml`.
2. Run `python -m unittest discover -s tests -v`. Full historical-data tests require the exact Hensen files and hashes documented in their local manifests.
3. In `frontend/`, run `npm ci`, `npm test` and `npm run build`.
4. For numerical-model changes, add analytic and independent reference checks, record units/boundary conditions, and run the optional QuTiP/QuSpin validation scripts in a separate test environment. Do not fit thresholds to preferred results.
5. Record meaningful changes in `CHANGELOG.md` and keep saved experiment provenance, seed and numerical diagnostics intact.

Contributions should include a clear description, test results, source citations for physical formulas and a statement about any new data or assets. Do not commit virtual environments, node_modules, build outputs, EXE files, credentials, private research records, complete conference manuscripts, or third-party datasets without a documented redistribution grant.

The project code license is pending owner approval. Until a license is applied, do not assume that a public contribution or fork has granted reuse rights beyond those explicitly available. Contributor terms may be clarified after the owner's license decision.
