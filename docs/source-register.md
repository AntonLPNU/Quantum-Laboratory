# Реєстр наукових джерел

У довідці застосунку метадані й короткі твердження для джерел зберігаються в `frontend/src/docs/references.ts`. Файл [`references.bib`](references.bib) є BibTeX-поданням тих самих стабільних ключів для наукового тексту. При зміні запису синхронізуйте обидва формати та frontend-тести.

## Як читати реєстр

- DOI веде до ідентифікатора публікації; посилання не є доказом правильності програмного результату.
- «Підтримує» означає лише відповідну теорему, метод або опубліковані дані. Локальні домовленості й межі симуляції задаються окремо в [науковій моделі](scientific_model.md).
- Hensen 2015 і Hensen 2016 — окремі публікації та набори даних. Їхні хеші, події, фільтри й критерії залишаються розділеними.
- QuTiP і QuSpin є незалежними інструментами валідації, а не обов'язковими runtime-залежностями.

## Джерела за темою

| ID | Джерело | Використання в програмі |
|---|---|---|
| `bell1964` | Bell, *On the Einstein Podolsky Rosen paradox* (1964), [DOI](https://doi.org/10.1103/PhysicsPhysiqueFizika.1.195) | Теоретичний контекст теореми Белла. |
| `chsh1969` | Clauser, Horne, Shimony & Holt, *Proposed Experiment to Test Local Hidden-Variable Theories* (1969), [DOI](https://doi.org/10.1103/PhysRevLett.23.880) | CHSH вираз і локально-реалістична межа. |
| `wootters1998` | Wootters, *Entanglement of Formation of an Arbitrary State of Two Qubits* (1998), [DOI](https://doi.org/10.1103/PhysRevLett.80.2245) | Двокубітна формула concurrence/entanglement of formation. |
| `horodecki1995` | Horodecki et al., *Violating Bell inequality by mixed spin-1/2 states* (1995), [DOI](https://doi.org/10.1016/0375-9601(95)00214-N) | Максимально досяжний CHSH для двокубітної матриці. |
| `nielsen2000` | Nielsen & Chuang, *Quantum Computation and Quantum Information* (2000), [publisher DOI](https://doi.org/10.1017/CBO9780511976667) | Базисний формалізм станів, каналів та вимірювань. |
| `kraus1983` | Kraus, *States, Effects, and Operations* (1983), [Springer](https://link.springer.com/book/10.1007/3-540-12732-1) | Операторний формалізм квантових операцій. |
| `choi1975` | Choi, *Completely positive linear maps on complex matrices* (1975), [DOI](https://doi.org/10.1016/0024-3795(75)90075-0) | Скінченновимірний контекст подання цілком додатних відображень. |
| `gks1976` | Gorini, Kossakowski & Sudarshan, *Completely positive dynamical semigroups of N-level systems* (1976), [DOI](https://doi.org/10.1063/1.522979) | Генератор марковської цілком додатної динаміки. |
| `lindblad1976` | Lindblad, *On the generators of quantum dynamical semigroups* (1976), [DOI](https://doi.org/10.1007/BF01608499) | Загальна форма генератора Ліндблада. |
| `pfeuty1970` | Pfeuty, *The one-dimensional Ising model with a transverse field* (1970), [DOI](https://doi.org/10.1016/0003-4916(70)90270-8) | Літературний контекст TFIM; реалізація тут — скінченний відкритий ланцюг. |
| `magnus2009` | Blanes et al., *The Magnus expansion and some of its applications* (2009), [DOI](https://doi.org/10.1016/j.physrep.2008.11.001) | Часовий порядок і експоненціальні методи; підстава для чисельної схеми, не твердження про точний нескінченно малий крок у комп'ютері. |
| `simon2001` | Simon, Bužek & Gisin, *No-Signaling Condition and Quantum Dynamics* (2001), [DOI](https://doi.org/10.1103/PhysRevLett.87.170405) | Математичний контекст локальних CPTP-карт і no-signaling. |
| `hensen2015` | Hensen et al., *Loophole-free Bell inequality violation using electron spins separated by 1.3 kilometres* (2015), [Nature DOI](https://doi.org/10.1038/nature15759) | Оригінальна стаття та джерельний контекст окремого аналізу 2015 року. |
| `hensen2016` | Hensen et al., *Loophole-free Bell test using electron spins in diamond: second experiment and additional analysis* (2016), [DOI](https://doi.org/10.1038/srep30289) | Окрема стаття й дані другого експерименту. |
| `johansson2012` | Johansson, Nation & Nori, *QuTiP* (2012), [DOI](https://doi.org/10.1016/j.cpc.2012.02.021) | Незалежний програмний інструмент перевірки еволюції. |
| `weinberg2017` | Weinberg & Bukov, *QuSpin* (2017), [DOI](https://doi.org/10.21468/SciPostPhys.2.1.003) | Незалежна діагоналізація та спінові ланцюги. |
| `newcombe1998` | Newcombe, *Interval estimation for the difference between independent proportions* (1998), [DOI](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C873::AID-SIM779%3E3.0.CO;2-I) | Інтервали для незалежних пропорцій у статистичному звіті. |
| `holm1979` | Holm, *A Simple Sequentially Rejective Multiple Test Procedure* (1979), [DOI](https://doi.org/10.2307/4615733) | Поправка Холма для множинних перевірок. |

Метадані Hensen 2015 перевірено на сторінці Nature та PubMed; Hensen 2016 — у PubMed/Sci Rep; Wootters і Bell — у сторінках APS; TFIM — на сторінці Annals of Physics/Elsevier. Інші DOI наведені з існуючого наукового реєстру проєкту або офіційних видавничих записів. Для програмної документації та ручної перевірки використовуйте DOI-ціль, а не цей короткий перелік як заміну першоджерелу.
