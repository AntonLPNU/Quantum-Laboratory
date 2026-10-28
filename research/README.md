# Reproducible research scenarios / Відтворювані дослідження

These three scenarios use the existing Python scientific core. They do not add new physics or treat a rendered trajectory as continuous observation of one quantum system. Run commands from the repository root after installing the source environment. Generated outputs go to `research/outputs/`, which Git ignores; existing Stage 5B records, Hensen source files and thesis manuscripts are never overwritten.

1. [Software Verification](software_verification/README.md) — analytic, regression and independent QuTiP/QuSpin checks.
2. [Phase Damping](phase_damping/README.md) — 21×21 exact singlet sweep and analytic concurrence/CHSH checks.
3. [Quantum Domino](quantum_domino/README.md) — locked Stage 5B receiver protocol, exact reduced states and finite-shot primary contrasts.

`manifest.json` identifies immutable local source records by SHA-256. Full historical Stage 5B records and complete thesis manuscripts are excluded from the proposed public source set pending review. A new run includes a timestamp and UUID, so compare numerical fields and tolerances; do not expect the whole new JSON file to have the historical byte hash. Independent validation tools belong in an optional environment.

Verify the fixed local files with `python research/check_manifest.py`. In a curated public source export that intentionally omits local historical outputs, use `python research/check_manifest.py --included-only` and regenerate the numerical scenarios.

For a Windows source checkout:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe research\phase_damping\run.py
.\.venv\Scripts\python.exe research\quantum_domino\run.py
```

Hensen data have separate upstream rights and are not included in the public source snapshot. The manifests in `data/references/*/manifest.json` preserve provenance and hashes without including raw files. Full test execution that includes Hensen reanalysis requires the exact version-1 source files; obtain them from the original repository and verify their SHA-256 values first.
