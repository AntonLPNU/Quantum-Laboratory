# Scenario 2 — Phase Damping

**Goal.** Reproduce an exact 21×21 grid for two independent local phase-damping channels on an unrotated singlet. This corresponds to the decoherence thesis without including its manuscript.

**Model.** Each qubit uses `K₀=√(1−λ/2) I` and `K₁=√(λ/2) σᶻ`, with `0≤λ≤1`. Both channels act on the complete `ρ_AB`; joint correlations, concurrence and CHSH use that complete state, while local Born quantities use partial traces. For this singlet, `q=(1−λ_A)(1−λ_B)`, `C=q`, optimized `S_max=2√(1+q²)` and the specified fixed-axis `S_fixed=2√2 q`. The CHSH bound `S=2` applies to the local-hidden-variable comparison; fixed-axis and optimized values must not be conflated. `λ` is dimensionless, not a measured T₂ or Hensen calibration.

**Command.** From a source environment with the project installed:

```powershell
.\.venv\Scripts\python.exe research\phase_damping\run.py
```

The command calls `quantum_lab.experiments.run_phase_damping_sweep`, stores the complete grid through the existing experiment storage API and writes `research/outputs/phase_damping/checks.json`. It does not sample individual measurement outcomes. The output directory is Git-ignored and does not modify historical research files.

**Checked result, 2026-10-28.** All 441 points passed an independent analytic comparison: maximum absolute errors were 8.88×10⁻¹⁶ for concurrence, 1.78×10⁻¹⁵ for optimized CHSH and 1.33×10⁻¹⁵ for fixed-axis CHSH; the maximum local `⟨σᶻ_B⟩` was 0. At `(λ_A,λ_B)=(0,0)`, `C≈1`, `S_max≈2.828427`; at `(1,1)`, `C=0`, `S_max≈2`.

**Limits.** This is an ideal CPTP-channel simulation. Agreement with known formulas is a verification of implementation, not a new effect or an apparatus prediction. The full local receiver state and no-signaling tests are documented separately.

**Sources.** Choi, *Linear Algebra and its Applications* 10 (1975), DOI [10.1016/0024-3795(75)90075-0](https://doi.org/10.1016/0024-3795(75)90075-0); Wootters, *Physical Review Letters* 80 (1998), DOI [10.1103/PhysRevLett.80.2245](https://doi.org/10.1103/PhysRevLett.80.2245); Horodecki et al., *Physics Letters A* 200 (1995), DOI [10.1016/0375-9601(95)00214-N](https://doi.org/10.1016/0375-9601(95)00214-N); Clauser et al., *Physical Review Letters* 23 (1969), DOI [10.1103/PhysRevLett.23.880](https://doi.org/10.1103/PhysRevLett.23.880).
