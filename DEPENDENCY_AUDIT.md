# Third-party dependency audit

Audit date: 2026-10-21. This is an inventory of dependency metadata in the
current checkout, not a legal opinion or a grant of rights for Quantum
Laboratory itself.

## Frontend

`frontend/package-lock.json` contains 214 npm package entries. Their declared
license fields group as follows:

| Declared license | Packages |
| --- | ---: |
| MIT | 183 |
| ISC | 12 |
| Apache-2.0 | 10 |
| BSD-3-Clause | 4 |
| BSD-2-Clause | 2 |
| MIT-0 | 1 |
| CC-BY-4.0 | 1 |

`webgl-constants@1.1.1` is the only locked package without a `license` field
in its `package.json`; its installed package includes a `LICENSE` file stating
MIT terms. Before redistributing a built bundle, generate and inspect a full
third-party notices inventory from the exact release artifact, including
transitive packages and license texts. This metadata scan alone is not a
substitute for that review.

## Python runtime

The current environment reports these direct runtime versions and metadata:

| Distribution | Version | Available license metadata |
| --- | ---: | --- |
| NumPy | 2.5.3 | SPDX expression: BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| Streamlit | 1.65.0 | SPDX expression: Apache-2.0 |
| Plotly | 6.9.0 | SPDX expression: MIT |
| Kaleido | 1.5.0 | No SPDX expression or license classifier in installed metadata; inspect distribution license files for release notices |
| Matplotlib | 3.11.2 | Python Software Foundation License classifier; distribution includes its license agreement and bundled third-party notices |

The versions above describe the audited environment, while `pyproject.toml`
declares compatible ranges. The independent QuTiP/QuSpin validation environment
is test-only and is not a runtime dependency of the application.

## Project ownership and release implications

No license for the Quantum Laboratory source itself is established in this
checkout. Dependency licenses do not grant a license to the project's own
code, experiment records, data, screenshots, or contributed assets. Do not add
a project license or redistribute a release until the owner approves the code
license and the applicable data/asset permissions. The authorship and citation
metadata still requiring owner confirmation are listed in
[`CITATION_METADATA_NEEDED.md`](CITATION_METADATA_NEEDED.md).

Before a public release, retain notices required by the exact dependency
licenses and inspect bundled assets/fonts separately. This audit does not
publish or modify any external service.
