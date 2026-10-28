# Параметри фізичної установки Hensen

Ця таблиця відділяє опубліковані параметри від невідомих калібрувань. Значення з часових журналів або статей не означають, що повна установка вже реалізована.

| Процес | Параметр / одиниця | Опубліковане значення або доступність | Джерело / статус у моделі |
|---|---|---|---|
| Електронні спіни NV | Спіновий ступінь свободи | Електронні спіни в NV-центрах алмазу; дві віддалені лабораторії | Hensen 2015/2016; двоспіновий абстрактний шар є, NV-структура NOT IMPLEMENTED |
| Просторове розділення | Відстань A–B, m | Близько 1.3 km (оптичний шлях/розділення; 2015 описує 1280 m) | Hensen 2015; просторова локальність не моделюється |
| Bernien 2013 setup (3 m) | Температура NV A/B; G; optical pulse/lifetime | 8 K / 4 K; 17.5 G; laser pulse 2 ns; excited-state lifetime 12 ns; source reports about 3% ZPL and about 1% scattered-light contribution for a typical filtered window; uncertainties not stated alongside these approximate values | Bernien et al. 2013; separate 3 m apparatus, not transferred to Hensen 2015/2016 runs |
| Bernien 2013 spin memory | Coherence time, s | Exceeds 10 ms under dynamical decoupling; sequence-dependent and not a free-evolution T2* | Bernien et al. 2013; not a measured rate for later Bell runs |
| Bernien 2013 estimated errors | Microwave pulses, initialization, decoherence, optical spin flip | 3.5%, 2%, <1%, 1%; source gives estimates without uncertainty in the main text | Bernien et al. 2013 supplementary reference; separate apparatus and protocol; not used as Hensen Bell-run calibration |
| Stage 4 phase-damping channel | `λ`, dimensionless coherence-loss fraction | API accepts caller-supplied [0,1]; not an experimental measurement; uncertainty is caller-defined/not provided | Choi/GKS/Lindblad mathematical references; `NOT CALIBRATED`, never fitted to Hensen CHSH |
| Stage 4 independent phase-damping controls | `λ_A`, `λ_B`, dimensionless | Independently controlled in the lab UI and scanned over `[0,1]×[0,1]`; channel acts in the computational Z basis after local rotations | Core Kraus map on full `ρ_AB`; exact sweep outputs are reproducible; still `NOT CALIBRATED` and not device parameters |
| Optimized CHSH sweep | `S_max`, dimensionless | Calculated from the two largest eigenvalues of `TᵀT`; fixed-axis CHSH is recorded separately | Horodecki criterion (SRC-014); mathematical optimization, not a measured apparatus value |
| Markov generator reference | `γ`, inverse normalized-time unit | Derived in the unit-time test as `−log1p(−λ)`; no SI unit because test time is dimensionless; analytic full-dephasing limit at `λ=1` | GKS/Lindblad; verification reference only, not a device rate |
| Локальне керування | Вісь/кут, rad; pulse history, s | Вимірювальні базиси та умови наведено в статті; повні незалежно калібровані поля, pulse envelopes і помилки в наборах trial data відсутні | Ідеальні осі можна розрахувати; пристрійні імпульси NOT IMPLEMENTED |
| Віддалене створення заплутаності | Bell-state fidelity, безрозмірна | 2015: оцінка стану 0.92 ± 0.03; це не повна густинна матриця | Hensen 2015; параметр не підганяється і не використовується як модель стану |
| Heralding / вікна часу | Старт та ширина, ps | 2015: starts 5426350/5425700 ps, 52450 ps width, 250000 ps separation. 2016: ch0 старий APD 5426000 ps, замінний APD 5425300 ps, ch1 5425100 ps; ширина 50000 ps, separation 250000 ps | Авторські приклади аналізу; окремі фільтри даних реалізовані, повний фотонний heralding процес NOT IMPLEMENTED |
| Післяімпульс / відбір ψ+ | Друге вікно, ps | Hensen 2016: 4000 ps для каналу 0, 2500 ps для каналу 1; ψ− використовує 50000 ps | Авторський приклад 2016; відтворено у парсері |
| Декогеренція / релаксація | T1, T2, s; спектр шуму, Hz | Каліброваних для конкретних runs значень у цих trial records немає | Lindblad/QuTiP `mesolve` наразі не параметризується та не запускається |
| Підготовка і зчитування | Assignment fidelity, безрозмірна | Hensen 2015 повідомляє combined initialization + single-shot-readout: A 0.971 ± 0.002, B 0.963 ± 0.003 | Симетричний binary assignment channel реалізовано як феноменологічний компонент; ці combined числа не трактуються як detector-only калібрування |
| Детектори та втрати | Efficiency, dimensionless; dark/after-pulse rates, Hz | Сира таблиця зберігає прийняті/відхилені herald candidates; повна незалежна ефективність кожного каналу та rate calibration для detector model відсутня | Детекторний ланцюг і втрати NOT IMPLEMENTED |
| Локальність у часі | basis-to-measurement latency, ns | 2015 стаття обмежує вибір базису й віддалений readout; 2016 додає 70 ns для RNG XOR і повідомляє, що умова locality зберігається | Ці числа є описом експерименту, а не параметрами симуляції |
| Відбір статистичної вибірки | Спроби, події | 2015: 245 Bell trials. 2016: 300; чотири setting counts 69/69/78/84 | Відтворено окремими аналізаторами; raw files захищені SHA-256 |

## Феноменологічний канал зчитування

Для результату `s ∈ {-1,+1}` симетричний канал із fidelity `F` задається `P(s_out=s_in)=F`, `P(s_out=-s_in)=1-F`; тому `E[s_out|s_in]=s_in(2F-1)`. Два незалежні локальні канали множать кореляцію на `(2F_A-1)(2F_B-1)`. Це перевірено аналітично та seeded Monte Carlo. Реалізація не включена автоматично у Hensen data analysis і не є повною моделлю оптичного/спінового readout.

## Фазове затухання та Lindblad / QuTiP

Поточний Kraus-канал фазового затухання — параметризована карта з λ, а не часовий пристрійний rate. Його generator-equivalent (`dρ/dt=(γ/2)(ZρZ−ρ)`, `γ=−log1p(−λ)` за одиничного безрозмірного часу) використовується тільки як незалежний чисельний тест із RK4; `λ=1` береться як аналітична границя. Для марковської відкритої системи застосування Ліндблада/QuTiP `mesolve` вимагає обґрунтованих наближень і заданих `H(t)` та collapse operators. Тут бракує незалежно каліброваних T1/T2, noise spectrum, повної pulse history і rates саме для Bell runs. Тому `λ` не перетлумачується як T2 і модель установки лишається `NOT IMPLEMENTED`.

### Джерела

- Hensen et al. (2015), Nature, [DOI 10.1038/nature15759](https://doi.org/10.1038/nature15759).
- Hensen et al. (2016), Scientific Reports, [DOI 10.1038/srep30289](https://doi.org/10.1038/srep30289); [офіційний PDF](https://pure.tudelft.nl/ws/portalfiles/portal/11820176/srep30289.pdf).
- Dataset version 1, Figshare/4TU, [DOI 10.4121/uuid:53644d31-d862-4f9f-9ad2-0b571874b829](https://doi.org/10.4121/uuid:53644d31-d862-4f9f-9ad2-0b571874b829).
- QuTiP, [master-equation dynamics guide](https://qutip.readthedocs.io/en/stable/guide/dynamics/dynamics-master.html).

- Choi (1975), Kraus-form representation theorem, DOI [10.1016/0024-3795(75)90075-0](https://doi.org/10.1016/0024-3795(75)90075-0); Arsenijević & Banković (2016), microscopic phase-damping Kraus derivation, DOI [10.5937/KgJSci1638041A](https://doi.org/10.5937/KgJSci1638041A).
- Gorini, Kossakowski & Sudarshan (1976), DOI [10.1063/1.522979](https://doi.org/10.1063/1.522979); Lindblad (1976), DOI [10.1007/BF01608499](https://doi.org/10.1007/BF01608499).
- Horodecki, Horodecki & Horodecki (1995), optimized CHSH criterion for mixed two-spin states, DOI [10.1016/0375-9601(95)00214-N](https://doi.org/10.1016/0375-9601(95)00214-N).
- Bernien et al. (2013), Nature 497, 86–90, DOI [10.1038/nature12016](https://doi.org/10.1038/nature12016); [QuTech-hosted primary PDF](https://qutech.nl/wp-content/uploads/2017/03/Heralded-entanglement-between-solid-state-qubits-separated-by-three-metres.pdf). This 3 m apparatus is not a parameter source for the 1.3 km 2015/2016 Bell runs.
