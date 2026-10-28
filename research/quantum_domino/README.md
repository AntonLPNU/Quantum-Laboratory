# Scenario 3 — Quantum Domino / Remote Influence Analysis

**Goal.** Rerun the locked Stage 5B protocol for a sender spin A and a three-spin receiver R. This corresponds to the remote-influence thesis without publishing its full manuscript.

**Model and parameters.** The complete state is `A⊗R`, with A at site 0 initially entangled with receiver site 1. During evolution, `H_AR/ℏ=I_A⊗H_R/ℏ`; no A–R coupling or classical channel is included. Receiver TFIM uses open boundaries, `J=1.0×10⁶ s⁻¹`, `h=0.8×10⁶ s⁻¹` and 101 times through 10 μs. Three branches are reference, nonselective local `σˣ` on A, and a Gaussian transverse control on receiver site 2 with amplitude `6.0×10⁴ s⁻¹`, center `5 μs` and width `1 μs`. The predeclared primary measurement is `σᶻ` at receiver site 3, `6.9 μs`.

**Locked statistics.** The copied `preregistration.json` has the same SHA-256 as the protected original: `66349b9599408952562b38110c69a9015342b914760de1d9c4793757a366f64b`. It specifies 14,000 independent preparations per group, two two-sided Fisher comparisons sharing one control group, Holm familywise α=0.01, 99.5% Newcombe–Wilson intervals and a fixed seed. The script calls the existing Stage 5B implementation; it does not change criteria after seeing outcomes.

**Command.** From a source environment with the project installed:

```powershell
.\.venv\Scripts\python.exe research\quantum_domino\run.py
```

For a faster exact-dynamics check without the finite-shot primary sampling, add `--physics-only`. The full command writes an experiment JSON/CSV and a concise `checks.json` to `research/outputs/quantum_domino/`; the complete raw sampling ledger stays in the experiment JSON. Historical records are not overwritten.

**Checked rerun, 2026-10-28.** The maximum exact receiver-state trace distance after A's local operation was `5.48×10⁻¹⁴`; the local positive control reached `0.082392` trace distance. The same preregistered seed reproduced counts 1636 vs 1595 for A versus reference (`Δp=0.002929`, Holm `p=0.454345`, 99.5% interval `[-0.007796,0.013654]`) and 1942 vs 1595 for positive control versus reference (`Δp=0.024786`, Holm `p=9.42×10⁻¹⁰`, interval `[0.013645,0.035931]`). An exact trajectory is an ensemble prediction, not continuous monitoring of one system. Non-rejection for A is limited by this design's sensitivity; it does not prove that every possible effect is absent. The descriptive distant/local response ratio was `0.662`, not a general amplification claim.

**Limits.** The finite model assumes ideal preparation, independent repeated shots and no hidden interaction channel. The separate, versioned power-semantics audit in the private local research record must be retained with any future full data release. Hensen observations are separate historical context and are not used as data in this simulation.

**Sources.** Simon, Bužek & Gisin, *Physical Review Letters* 87 (2001), DOI [10.1103/PhysRevLett.87.170405](https://doi.org/10.1103/PhysRevLett.87.170405); Holm, *Scandinavian Journal of Statistics* 6 (1979), stable identifier [10.2307/4615733](https://doi.org/10.2307/4615733); Newcombe, *Statistics in Medicine* 17 (1998), DOI [10.1002/(SICI)1097-0258(19980430)17:8<873::AID-SIM779>3.0.CO;2-I](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C873::AID-SIM779%3E3.0.CO;2-I).
