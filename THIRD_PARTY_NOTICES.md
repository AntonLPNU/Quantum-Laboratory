# Third-party materials and notices — v0.5.0 release review

This inventory separates project-authored code from third-party material. It does **not** apply a Quantum Laboratory code license to dependencies, research datasets, fonts, published figures, or copied examples. This is a release review document, not yet a complete binary notice bundle.

## Bundled desktop runtime

| Component | Version in tested build | Identified terms | Use |
| --- | --- | --- | --- |
| Electron / Chromium | 45.1.0 | Electron MIT; packaged Chromium notices in `LICENSES.chromium.html` | Desktop shell and browser engine |
| React / React DOM | 19.3.1 | MIT | Interface |
| Three.js | 0.179.1 | MIT | Schematic 3D scene |
| React Three Fiber / Drei | 9.8.2 / 10.7.9 | MIT | Scene integration and controls |
| KaTeX and bundled KaTeX font files | 0.19.1 | MIT license in installed KaTeX package | Offline formula rendering |
| Lucide React | 0.468.0 | ISC | Interface icons |
| NumPy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 in installed metadata | Scientific calculations |
| Pillow | 12.3.0 | MIT-CMU in installed metadata | Generated desktop icon |

The icon in `desktop/assets` is generated from project geometry by `scripts/generate_desktop_icon.py`; no stock image or proprietary font is required to generate it. The browser UI uses system fonts. KaTeX fonts are packaged locally for offline use; preserve the upstream KaTeX notice with any binary distribution.

The current desktop lockfile records 283 transitive npm packages; the frontend lockfile records 216. Metadata includes MIT, ISC, Apache-2.0, BSD, CC-BY-4.0, BlueOak-1.0.0 and other identifiers. These counts include build-time tools and do not identify precisely which files are inside the final binary. `webgl-constants@1.1.1` lacks a lockfile license field, but its installed LICENSE states MIT. `caniuse-lite` metadata states CC-BY-4.0. The exact binary still needs an inventory of copied license texts and Chromium notices before public distribution. See `docs/desktop/DEPENDENCIES.md` and `DEPENDENCY_AUDIT.md` for the existing audits.

Python source/runtime dependencies declared in `pyproject.toml` also include Streamlit (Apache-2.0), Plotly (MIT), Kaleido (license metadata incomplete in the previously audited installation), and Matplotlib (PSF-style license plus bundled notices). These are needed for the source/legacy application and are **not** the same as the minimal frozen desktop Python package. PyInstaller 6.22.3 is a build tool with GPL-2.0-or-later plus its documented special distribution exception; retain its applicable bootloader notice. QuTiP and QuSpin are independent verification tools, not runtime dependencies of the desktop package.

## External scientific data and examples

Hensen 2015 and 2016 datasets in `data/references/` are the work of their respective authors and 4TU.ResearchData, **not** Anton Volos's code or data. The included manifests record dataset DOIs, source URLs, version 1 and immutable SHA-256 values. They identify the rights statement as “4TU General Terms of Use”; they do not establish a standard SPDX license or a clear grant to repackage raw files. The older development checkout and its history contain original archives, readmes, spreadsheets and `*_analysis_example.py` files; these raw files are excluded from this curated public source snapshot. Do not publish binaries built from the older checkout, which can bundle those original files. The 2016 journal article being CC BY 4.0 does not by itself change the separate dataset's or example script's terms. Before a public data or binary release, confirm the exact dataset terms and permission to redistribute **each** archive/example in this form. Do not relabel these files MIT.

- Hensen 2015 dataset: DOI [10.4121/uuid:6e19e9b2-4a2d-40b5-8dd3-a660bf3c0a31](https://doi.org/10.4121/uuid:6e19e9b2-4a2d-40b5-8dd3-a660bf3c0a31).
- Hensen 2016 dataset: DOI [10.4121/uuid:53644d31-d862-4f9f-9ad2-0b571874b829](https://doi.org/10.4121/uuid:53644d31-d862-4f9f-9ad2-0b571874b829).
- Data reuse guidance: [TU Delft Copyright Information Point](https://www.tudelft.nl/library/support/copyright); [Figshare reuse guidance](https://info.figshare.com/user-guide/how-to-search-for-and-reuse-content-on-figshare/).

The local `docs/ui-design/stage-5c/` Stitch HTML/PNG handoff assets are excluded from the clean public source snapshot pending a separate review of their generation and redistribution terms. Local conference manuscripts under `docs/theses/2026/` are also excluded pending conference guidance. Neither exclusion deletes the local materials. The older development Git history contains original Hensen files; the public source snapshot is a new curated initial commit and does not inherit that history. Raw Hensen files are excluded; only provenance manifests (DOI, source locations, and hashes) are included.

## Project-authored research results

The Stage 5B simulation records and thesis-derived plots are separate research outputs, not third-party Hensen observations. Their provenance, protocol and checksums must remain intact. The current public candidate excludes full records and manuscripts until their release scope and conference timing are approved. A later data release should state its own reuse terms; a code license should not silently cover research data.
