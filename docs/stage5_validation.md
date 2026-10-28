# Stage 5A independent TFIM validation

## Scope and reproducibility

This report records the optional independent-solver checks for the Stage 5A dense Pauli-normalized transverse-field Ising model. The application runtime dependencies remain unchanged; run the external solvers only in an isolated Python 3.13 environment:

```powershell
py -3.13 -m venv .venv-stage5-validation
.venv-stage5-validation\Scripts\python.exe -m pip install -r requirements-stage5-validation.txt
.venv-stage5-validation\Scripts\python.exe scripts\validate_stage5_quspin.py --all
.venv-stage5-validation\Scripts\python.exe scripts\validate_stage5_qutip.py --fixture smooth-controls
```

Both scripts emit complete JSON reports to stdout. To preserve an exact run record, redirect stdout to a file. The report includes package version, model/boundary convention, exact times, coupling values, initial-state preparation and seed (plus the generated ket), solver tolerances, diagnostics, acceptance limits, differences, and status. The checks compare like-for-like angular-frequency generators: `H/ℏ`, with Pauli matrices having eigenvalues ±1, `J,h` in s⁻¹, and time in seconds. No experimental calibration is inferred.

## Independent methods

- QuSpin 1.0.1: each open-chain coupling list contains precisely `(i,i+1)` for `i=0,…,N−2`; the full, unsymmetrized spin basis is used. Hamiltonian matrices and spectra are checked for three signed/zero parameter combinations at every size `N=2,…,6`. Seeded complex initial kets are evolved by QuSpin's independent DOP853 Schrödinger solver and compared to the project spectral propagator. Local `σᶻ` expectations are also compared.
- QuTiP 5.3.0: independently tensor-assembled OBC operators are passed to `sesolve` with the same Gaussian transverse field, initial kets, sample times, and angular-frequency units as the project midpoint solver. The comparison includes state vectors, site-resolved `σᶻ`, and two-spin reductions for the deliberately reversed `keep=[N−1,0]` order. QuTiP's `ptrace()` result is explicitly permuted from ascending site order to requested order.
- Periodic reference only: QuSpin's `L=8, J=1, h=√2` periodic TFIM spectrum is checked against a separate explicit Kronecker construction. This corresponds to the periodic TFIM fixture in Sec. 2.1 / Fig. 1 of Weinberg & Bukov (2019). It is not passed to, or treated as, an open-boundary test. QuSpin Example 9 concerns a periodically driven 2D model and is not an OBC reference.

## Acceptance limits declared before comparison

| Check | Limit |
| --- | ---: |
| QuSpin Hamiltonian max absolute entry difference | 2×10⁻¹² |
| QuSpin spectrum max absolute difference | 2×10⁻¹¹ |
| QuSpin / project trajectory max ket 2-norm difference | 2×10⁻¹⁰ |
| QuSpin / project local observable max absolute difference | 2×10⁻¹⁰ |
| QuTiP / project trajectory, observables, ordered reductions | 5×10⁻⁷ |

These are numerical cross-check thresholds for the declared finite-dimensional fixtures, not fit parameters. Project local tolerances for the driven run are `rtol=10⁻¹⁰`, `atol=10⁻¹²`; QuTiP uses `rtol=10⁻¹²`, `atol=10⁻¹⁴`. The QuSpin solver uses DOP853 with `rtol=atol=10⁻¹²`.

## Observed results

Environment: CPython 3.13 on Windows; QuSpin 1.0.1; QuTiP 5.3.0; NumPy 2.5.4 and SciPy 1.18.1 in the isolated environment. The application environment was not modified. QuTiP emitted an import-time warning that Matplotlib is absent; this validation does not use plotting.

| Fixture | Cases | Maximum observed difference | Result |
| --- | ---: | ---: | --- |
| QuSpin OBC sizes N=2…6, three `(J,h)` pairs per size, 18 times each | 15 | Hamiltonian 0; spectrum 0; ket trajectory 4.89138830183238×10⁻¹²; local `σᶻ` 8.85624906743487×10⁻¹³ | PASS |
| QuSpin published-model periodic `L=8,J=1,h=√2` versus explicit periodic Kronecker matrix | 1 | Spectrum 0 | PASS, `periodic_reference_only` |
| QuTiP Gaussian-driven OBC N=2…6, 29 times each | 5 | Ket trajectory 4.41601714277870×10⁻⁸; local `σᶻ` 3.52721001850576×10⁻⁸; ordered reduced density matrix 1.73142243320434×10⁻⁸ | PASS |

The largest project norm drift in the QuTiP trajectories was 1.29452004671293×10⁻¹³. QuTiP-vs-project differences are expected to exceed machine epsilon because their time integrators and local error controls differ; both remain below the predeclared limit. Successful cross-checks support implementation consistency for these ideal models and do not establish a calibrated apparatus model.

## Sources

1. P. Weinberg and M. Bukov, “QuSpin: a Python package for dynamics and exact diagonalisation of quantum many body systems. Part II: bosons, fermions and higher spins,” *SciPost Physics* 7, 020 (2019), DOI [10.21468/SciPostPhys.7.2.020](https://doi.org/10.21468/SciPostPhys.7.2.020). Section 2.1 gives the Pauli TFIM and periodic boundary conditions; Fig. 1 and the supplied code list `L=8`, `J=1.0`, `h=√2`.
2. QuSpin 1.0.1, [TFIM/Jordan–Wigner example 4](https://quspin.github.io/QuSpin/examples/example4.html) and [Hamiltonian evolution API](https://quspin.github.io/QuSpin/generated/quspin.operators.hamiltonian.html).
3. QuTiP 5.3, [time-dependent Hamiltonian evolution guide](https://qutip.readthedocs.io/en/stable/guide/dynamics/dynamics-time.html) and [tensor/partial-trace guide](https://qutip.readthedocs.io/en/stable/guide/guide-tensor.html).

## Limits and exclusions

These are dense exact-diagonalization checks up to six spins for OBC. They do not validate large-system scaling, an apparatus calibration, open-system evolution, experimental pulse histories, or finite-sample Hensen analyses. The periodic L=8 case is a separate reference-model reproduction; it cannot establish the open-boundary interaction structure. No Hensen source data, hashes, event selection, or analysis code were modified by this task.

## Final Stage 5A regression run

After the demonstration and research-guide documentation were added, the full application suite ran with CPython 3.13: `python -m unittest discover -s tests -v` reported **143 tests, all passing**. This includes the existing Hensen analysis and data-integrity checks. The final independent reruns also passed: QuSpin's 15 OBC cases plus the distinct periodic fixture, and QuTiP's five smooth-control cases. `compileall` and `git diff --check` completed successfully. The isolated QuTiP import prints a non-fatal warning that Matplotlib is absent; neither solver comparison uses plotting.

On the Windows sandbox, the first full-suite attempt used the default system temporary folder and failed cleanup with access denied. Re-running with `TEMP` and `TMP` set to a writable Stage 5 work folder passed all 143 tests; this was an environment permission issue, not a code or physics test failure.
## Stage 5B: повторення ізольованого приймача

Для протоколу Quantum Domino спочатку зафіксуйте дизайн через `lock_quantum_domino_protocol`; протокол виконує фізичний preflight та потужність і блокує точні оператор, спін, час, контрольний імпульс, кількість вибірки й критерії до першого confirmatory RNG draw. Не змінюйте початкову preregistration після відкриття результатів. Основна вибірка генерується окремими seed-потоками для груп і перемішаними нейтральними мітками; seed не визначається міткою сценарію або часовою точкою.

Основні параметри затверджено до вибірки: N=4; J=1.0×10⁶ s⁻¹; h=0.8×10⁶ s⁻¹; 101 точка 0…10 μs; вимір σᶻ на фізичному спіні 3 при 6.9 μs; sender-група застосовує локальний σˣ на A; позитивний контроль прикладає гаусове transverse field на фізичний спін 2 (амплітуда 6.0×10⁴ s⁻¹, центр 5 μs, ширина 1 μs). Вибір амплітуди відбувся до confirmatory вибірки за наперед заданим правилом |ΔP(+1)|≥0.025.

Заблокований дизайн використовує 14,000 незалежних підготовок на групу, дві двосторонні Fisher exact первинні перевірки, спільну reference-групу, Holm FWER=0.01 та 99.5% Newcombe–Wilson інтервали. Первісний preregistration зберігає оцінку `familywise_power=0.999995` для 200,000 повторів; код визначав її як імовірність відхилити принаймні одну первинну гіпотезу. Аудит виявив помилкове використання цього показника як `target_joint_power`. У версійованому перерахунку з незмінними параметрами, альтернативами та seed `1529012602` імовірність відхилити обидві гіпотези після Holm становила `0.999875` (95% Wilson MC інтервал `[0.9998154715, 0.9999153263]`; MC SE `2.49984×10⁻⁵`); імовірність відхилити принаймні одну лишилася `0.999995`. Обидві оцінки перевищують 0.90, отже, 14,000 підготовок на групу достатньо для зафіксованих альтернатив. Протокол і первісний запис не переписувалися. Позитивний контроль у точному preflight мав Δp=0.0262380185. Повторний аналіз і чутливість менших ефектів: `results/stage5b/reanalysis/power-semantics-v2-2026-10-27.json`.

Фактичні вибіркові рахунки: reference 1,595 із 14,000 результатів +1; sender-operation 1,636; positive-control 1,942. Sender проти reference: Δp=0.00292857, 99.5% CI [−0.00779573, 0.01365392], Fisher p=0.454345, Holm p=0.454345 — різницю не виявлено за цією чутливістю. Це не виключає менші відмінності та не поширюється на інші оператори, часи чи моделі. Positive-control проти reference: Δp=0.02478571, 99.5% CI [0.01364545, 0.03593124], Fisher p=4.7110×10⁻¹⁰, Holm p=9.4220×10⁻¹⁰ — локальний імпульс детектовано на обраному віддаленому спіні.

На момент первинного виміру зміни ⟨σᶻ⟩ у приймачі для фізичних спінів 1,2,3 дорівнювали приблизно [0, 0.106056, 0.052476]. За визначенням віддаленого сигналу на спіні 3 відносно локальної відповіді на спіні 2 відношення амплітуд 0.4948; за максимумами всієї фіксованої траєкторії — 0.6619. Контрольний сигнал поширився до обраного спіну, але цей показник не демонструє підсилення локальною системою.

Повні hash preregistration, параметри, повні A⊗R траєкторії, редукції, очікувані характеристики, shot ledger, рахунки, інтервали, p-values, seed-потоки й plot-ready data знаходяться в `results/stage5b/`. JSON зберігає числові компоненти complex128 без округлення; CSV містить розгорнуті поля. Файл `experiment_*` є записом фактично виконаної вибірки; `stage5b_quantum_domino_v1.json` — передреєстрацією.

У записі передреєстрації git HEAD зафіксовано як `1f059fea559ae84bd9ff982ed16146db83da6142`; реалізація на той момент містила незакомічені зміни. Python source fingerprint доданий у механізм записів пізніше, тож його відсутність у первинній preregistration явно залишається обмеженням походження; він не відновлюється заднім числом і не використовується для підміни її хешу.

Глобальну збіжність перевірено окремо від локального контролю кроку. Для pulse branch trace distance повних кінцевих станів між `rtol=10⁻¹⁰, atol=10⁻¹²` та уточненими `rtol=10⁻¹², atol=10⁻¹⁴` дорівнювала 4.79795418×10⁻⁹; різниця первинної ймовірності 7.43051981×10⁻¹⁰. Чисельні межі 1e−8 виконано.

Незалежні звірки виконано QuTiP 5.3.0 `sesolve` та QuSpin 1.0.1 `spin_basis_1d(pauli=True)` + SciPy DOP853 для сталого Hamiltonian, гладкого некомутуючого поля, гаусового локального контролю, σˣ на передавачі та відрізково-сталого поля з розбиттям на розривах. Для всіх п'яти сценаріїв в кожному незалежному інструменті максимальні відмінності повного ket, reduced receiver trace distance та ⟨σᶻ⟩ були нижчими за 1e−8; точні значення зберігаються в `results/stage5b/validation_qutip.json` і `validation_quspin.json`. Наукові джерела SRC-020…SRC-026 наведено у `docs/scientific_model.md` та затвердженій специфікації Stage 5B.

Stage 5B не є моделлю просторового передавання частинок, пристрою чи детектора. Контрольний ефект і no-signaling висновок стосуються лише заданої замкненої скінченної моделі, обраної локальної операції та одного первинного вимірювання. Інші часи, оператори, спектри й кореляції є вторинними аналізами з окремим контролем множинності.
