# Orbital Lab UI prototype

An isolated React + TypeScript + React Three Fiber prototype for the Quantum Laboratory Stage 5C review. It lives outside the Streamlit repository and has no Python scientific-core connection.

## Run locally

```powershell
npm install
npm run dev
```

Open the local address printed by Vite. The central viewport supports orbit/pan/zoom with mouse and wheel. Use **Fly Mode**, click inside the canvas to capture the pointer, move with W/A/S/D and Q/E, and press Esc to release. Select a spin by clicking its 3D node. Side panels and the bottom plot are overlays and can be collapsed.

## Scientific boundary

All visible numeric values, the chart, time transport, and spin attributes are labelled demo/UI data. Animation is decorative and does not represent a quantum trajectory. No Hamiltonian, state evolution, matrix operation, or physical observable is computed in JavaScript. This prototype must not be used to support a scientific claim.

## Design source

Tokens are recorded in `resources/style-guide.json`, based on the repository's Orbital Lab `DESIGN.md` and `orbital-blank.html`. Colors and type use the shared CSS variables in `src/styles.css`.

## Review artifacts

`artifacts/` will contain viewport screenshots, interaction notes, and a read-only checksum manifest for the source science files captured before prototyping.
