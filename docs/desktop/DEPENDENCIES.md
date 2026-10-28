# Desktop dependency review — 2026-10-28

The installer is a local research preview. These are the versions and declared
license identifiers inspected for this build; this inventory is not a license
grant for Quantum Laboratory source or research data.

| Bundled runtime component | Version | Declared license metadata |
| --- | --- | --- |
| Electron | 45.1.0 | MIT; packaged Electron also includes `LICENSE.electron.txt` and `LICENSES.chromium.html` |
| React / React DOM | 19.3.1 | MIT |
| Three.js | 0.179.1 | MIT |
| React Three Fiber / Drei | 9.8.2 / 10.7.9 | MIT |
| KaTeX | 0.19.1 | MIT |
| Lucide React | 0.468.0 | ISC |
| NumPy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| Pillow | 12.3.0 | MIT-CMU |

PyInstaller 6.22.3 is used to construct the Python executable; its installed
metadata describes GPL-2.0-or-later with a special distribution exception.
QuTiP and QuSpin remain independent validation tools and are not bundled.

`npm audit` reported zero known vulnerabilities for both frontend and desktop
lockfiles on 2026-10-28. The older KaTeX version was updated before this build.
Before any public release, inspect the full transitive license notices in the
exact binary, determine permissions for bundled datasets and assets, and obtain
the owner's decision on the Quantum Laboratory source license and attribution.
