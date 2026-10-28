# Hensen 2016 Reanalysis and Apparatus Model Plan

## Fixed analysis design

The Hensen 2016 records are parsed separately for the old and replacement APD files; source hashes are checked before analysis. The event-ready channel-0 start is 5426000 ps for the old APD and 5425300 ps for the replacement APD, with channel 1 at 5425100 ps. Apply the author script's 50000 ps first-event window, 250000 ps separation, state-dependent second-click window (50000 ps for psi-minus; 4000 ps on channel 0 and 2500 ps on channel 1 for psi-plus), invalid-marker rule, no-after-excitation-click rule, and readout threshold 10620 < t <= 14320 ns. Report per-state input counts/correlations/CHSH and uncertainty, then combine by trial-count weighting. The complete-analysis local-realist score is recomputed from each accepted record with the paper's RNG bias bound. Hensen 2015 remains a separately filtered dataset; combined results do not erase experiment identity.

## No-signaling design (predeclared)

For each heralded state separately, test the two conditional-independence questions at each local setting: A outcome vs remote B setting given A setting, and B outcome vs remote A setting given B setting. Report the four cell counts, local + outcome frequencies and Wilson 95% intervals, two-sided Fisher exact p-values, and Holm-adjusted p-values across the eight Hensen 2016 tests (or four 2015 tests). Family-wise alpha is 0.05. The exact test assumes independent trials; because event-sequence memory is not modeled in this stage, a non-rejection is descriptive and the no-signaling assessment remains INCONCLUSIVE. Heralding and event filters select the analyzed sample. A joint-record test requires classical comparison of the two observers' records and cannot give either observer a signaling channel.

## Physical scope and statuses

Add a symmetric binary assignment-error channel as a phenomenological readout component. A local readout reports the correct eigenvalue with probability F and flips it with probability 1-F. The Hensen 2015 paper reports combined initialization and single-shot-readout fidelities (A 0.971 +/- 0.002; B 0.963 +/- 0.003), which are not pure detector calibrations; therefore these values are documented as illustrative benchmarks only and are not used to fit or validate Hensen results. Lindblad/QuTiP evolution is deferred: device-specific T1/T2, noise spectra, driven Hamiltonian, and calibrated pulse histories are insufficient in the cited data release. Mathematical checks, data reproduction, and physical apparatus validation receive separate statuses; apparatus validation remains NOT IMPLEMENTED.

## Work sequence

1. Add regression tests for Hensen 2016 extraction, combined Hensen scores, no-signaling multiplicity/intervals, and readout-channel invariants.
2. Implement parsers and analysis APIs in the scientific-validation and apparatus-physics modules.
3. Extend the validation tab with year selection, original trial records, analysis/no-signaling results, assumptions, and explicit physical-validation status.
4. Update sources, parameter inventory, AGENTS guidance, and scientific-model documentation.
5. Run the full existing and new test suite, verify the app, checksums, and rendered UI, then re-index the code graph.
