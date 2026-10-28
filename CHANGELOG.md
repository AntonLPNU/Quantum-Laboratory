# Changelog

## 0.5.0 Desktop Research Preview — local candidate, 2026-10-28

- Added a standalone Windows Electron shell around the existing Orbital Lab and Python API.
- Added a bundled PyInstaller backend, private ephemeral loopback session, local experiment storage and offline documentation.
- Added NSIS installer and portable packaging scripts, desktop icon and packaged backend smoke checks.
- Fixed rendering of Bloch expectation formulas in the Inspector. Scientific models and original Hensen/Stage 5B data were not changed.
- Added expandable/collapsible scientific, Inspector and graph panels for compact desktop windows; verified the three-panel layout at 1272×706.
- Prepared bilingual release notes, citation metadata for Anton Volos, third-party inventory, publication audit and three reproducible research scenarios. The license decision, tag and public release remain pending.

## 0.5.0 Research Preview — local candidate, 2026-10-21

This is a release-candidate version label for the current mixed working tree. It is not a tagged Git release and has not been published.

- Integrates the verified two-spin channels and N-spin open-boundary TFIM core with the Dynamic Receiver, deviation analysis and read-only Hensen reanalysis.
- Adds Orbital Lab as a React/TypeScript/Three.js interface whose physical results are computed by the local Python core.
- Adds Windows setup/build/startup readiness checks, record save/load/compare, and JSON/CSV export.
- Improves recovery after API disconnection and closes the Hensen data handles used by the legacy Streamlit page.
- Adds methods, results, architecture, and reproducibility documentation.
- No new physical process or calibrated apparatus model is introduced. Hensen files and Stage 5B research records remain unchanged.

## Earlier history

Prior version entries are not reconstructed from the mixed working tree. See Git history after the release candidate is reviewed and recorded by its owner.
