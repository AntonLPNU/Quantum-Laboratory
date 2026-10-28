"""Independent re-analysis of published Bell-test source data.

The Hensen data pipeline in this module is deliberately separate from the
ideal two-spin simulation routines. It reimplements the published event
filters and statistics from the authors' data-analysis example.
"""
from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

HENSEN_2015_DATA_SHA256 = "5A6B1853554AD508D35C795415D64922ED9E5BC0469F6052AD222486AD3566FF"
HENSEN_2015_PUBLISHED = {
    "valid_trials": 245,
    "setting_counts": {"00": 53, "01": 79, "10": 62, "11": 51},
    "chsh_s": 2.42,
    "chsh_standard_error": 0.20,
    "local_realist_p_value": 0.039,
}
# Predeclared tolerances are the rounding half-width of each published value.
HENSEN_2015_ROUNDING_TOLERANCES = {
    "chsh_s": 0.0055,
    "chsh_standard_error": 0.0055,
    "local_realist_p_value": 0.00051,
}


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file without changing its contents."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _binomial_upper_tail(n: int, k: int, probability: float) -> float:
    """Exact binomial survival probability P[X >= k] using a recurrence."""
    if n < 0 or k < 0 or k > n or not 0.0 <= probability <= 1.0:
        raise ValueError("invalid binomial parameters")
    if k == 0:
        return 1.0
    if probability == 0.0:
        return 0.0
    if probability == 1.0:
        return 1.0
    term = math.comb(n, k) * probability**k * (1.0 - probability) ** (n - k)
    tail = term
    for index in range(k, n):
        term *= ((n - index) / (index + 1)) * (probability / (1.0 - probability))
        tail += term
    return min(1.0, tail)


def assess_hensen_2015_reproduction(result: dict) -> str:
    """Apply fixed criteria for reproducing the rounded 2015 report."""
    if result.get("dataset_sha256") != HENSEN_2015_DATA_SHA256:
        return "FAILED"
    if result.get("valid_trials") != HENSEN_2015_PUBLISHED["valid_trials"]:
        return "FAILED"
    if result.get("setting_counts") != HENSEN_2015_PUBLISHED["setting_counts"]:
        return "FAILED"
    for key, tolerance in HENSEN_2015_ROUNDING_TOLERANCES.items():
        if abs(float(result[key]) - HENSEN_2015_PUBLISHED[key]) > tolerance:
            return "FAILED"
    return "VALIDATED"


def analyze_hensen_2015(path: str | Path) -> dict:
    """Reproduce Hensen et al. (2015) filters, CHSH estimate, error, and p-value.

    The source has no header: a timestamp followed by the 16 integer columns
    described in the included author-provided header spreadsheet and example.
    """
    source = Path(path)
    digest = sha256_file(source)
    if digest != HENSEN_2015_DATA_SHA256:
        raise ValueError(f"Hensen 2015 source data checksum mismatch: {digest}")

    rows: list[list[int]] = []
    with source.open("r", encoding="ascii", newline="") as handle:
        for row_number, row in enumerate(csv.reader(handle), start=1):
            if len(row) != 17:
                raise ValueError(f"expected 17 CSV fields on row {row_number}, got {len(row)}")
            try:
                rows.append([int(value) for value in row[1:]])
            except ValueError as exc:
                raise ValueError(f"non-integer measurement field on row {row_number}") from exc

    starts = {0: 5_426_350, 1: 5_425_700}
    event_window_length = 55_000 - 2_550
    event_window_separation = 250_000
    readout_start_ns = 10_620
    readout_end_ns = readout_start_ns + 3_700
    setting_products: dict[str, list[int]] = {f"{a}{b}": [] for a in (0, 1) for b in (0, 1)}
    wins = 0
    valid_trials = 0
    trial_records = []

    for values in rows:
        (day, run, click1_time, click1_channel, click2_time, click2_channel,
         setting_a, setting_b, rng_a_time, rng_b_time, readout_a_time,
         readout_b_time, excite_a_time, excite_b_time, invalid_a, invalid_b) = values
        del rng_a_time, rng_b_time  # RNG timestamps are not part of this estimator

        start_1 = starts.get(click1_channel)
        start_2 = starts.get(click2_channel)
        event_1_valid = (
            start_1 is not None
            and start_1 <= click1_time < start_1 + event_window_length
        )
        event_2_valid = (
            start_2 is not None
            and start_2 + event_window_separation <= click2_time
            < start_2 + event_window_separation + event_window_length
        )
        no_recent_invalid_marker = (
            (invalid_a == 0 or invalid_a > 250)
            and (invalid_b == 0 or invalid_b > 250)
        )
        no_excitation_clicks = excite_a_time == 0 and excite_b_time == 0
        valid = (
            event_1_valid and event_2_valid
            and click1_channel != click2_channel
            and no_recent_invalid_marker and no_excitation_clicks
        )
        if not valid:
            continue

        valid_trials += 1
        outcome_a = 1 if readout_start_ns < readout_a_time <= readout_end_ns else -1
        outcome_b = 1 if readout_start_ns < readout_b_time <= readout_end_ns else -1
        product = outcome_a * outcome_b
        setting = f"{setting_a}{setting_b}"
        if setting not in setting_products:
            raise ValueError(f"unexpected binary setting on row {row_number}")
        setting_products[setting].append(product)
        wins += int(((-1) ** (setting_a * setting_b)) * product == 1)
        trial_records.append({"state": "psi_minus", "setting_a": setting_a, "setting_b": setting_b,
                              "outcome_a": outcome_a, "outcome_b": outcome_b, "day": day, "run": run})

    if valid_trials == 0 or any(not values for values in setting_products.values()):
        raise ValueError("source data produced no valid trials for one or more settings")

    setting_counts = {key: len(values) for key, values in setting_products.items()}
    correlations = {
        key: sum(values) / len(values) for key, values in setting_products.items()
    }
    correlation_standard_errors = {
        key: math.sqrt((1.0 - value * value) / setting_counts[key])
        for key, value in correlations.items()
    }
    chsh_s = correlations["00"] + correlations["01"] + correlations["10"] - correlations["11"]
    chsh_standard_error = math.sqrt(sum(value * value for value in correlation_standard_errors.values()))
    rng_bias_bound = 0.75 + 3.0 * (1.08e-5 + 1.08e-5**2)
    p_value = _binomial_upper_tail(valid_trials, wins, rng_bias_bound)

    result = {
        "dataset_sha256": digest,
        "source_rows": len(rows),
        "valid_trials": valid_trials,
        "setting_counts": setting_counts,
        "correlations": correlations,
        "correlation_standard_errors": correlation_standard_errors,
        "chsh_s": chsh_s,
        "chsh_standard_error": chsh_standard_error,
        "chsh_95_percent_interval": [
            chsh_s - 1.96 * chsh_standard_error,
            chsh_s + 1.96 * chsh_standard_error,
        ],
        "chsh_winning_trials": wins,
        "local_realist_win_probability_bound": rng_bias_bound,
        "local_realist_p_value": p_value,
        "analysis_status": "",
        "trials": trial_records,
        "model_comparison_status": "NOT IMPLEMENTED",
        "model_comparison_limitation": (
            "The current simulator omits the event-ready heralding path, real spin preparation/"
            "control/readout timing, losses and detector response, setting-generator and locality "
            "conditions, and the published event-selection process. The ideal two-spin model is "
            "not a reproduction of this apparatus."
        ),
    }
    result["analysis_status"] = assess_hensen_2015_reproduction(result)
    return result


def hensen_ideal_model_baseline(state_name: str = "singlet") -> dict:
    """Return ideal singlet correlations at Hensen's nominal settings.

    This analytical baseline uses the simulator's existing state and
    correlation API. It is explicitly not a model of the Hensen apparatus.
    """
    import numpy as np

    from quantum_lab.metrics import correlator
    from quantum_lab.states import bell_state

    settings = {
        "00": (0.0, -3.0 * math.pi / 4.0),
        "01": (0.0, 3.0 * math.pi / 4.0),
        "10": (math.pi / 2.0, -3.0 * math.pi / 4.0),
        "11": (math.pi / 2.0, 3.0 * math.pi / 4.0),
    }
    state = bell_state(state_name)
    correlations = {}
    for name, (angle_a, angle_b) in settings.items():
        axis_a = np.array([math.cos(angle_a), math.sin(angle_a), 0.0])
        axis_b = np.array([math.cos(angle_b), math.sin(angle_b), 0.0])
        correlations[name] = correlator(state, axis_a, axis_b)
    chsh_s = correlations["00"] + correlations["01"] + correlations["10"] - correlations["11"]
    return {
        "state": state_name,
        "setting_angles_rad": settings,
        "correlations": correlations,
        "chsh_s": abs(float(chsh_s)),
        "model_comparison_status": "NOT IMPLEMENTED",
        "interpretation": "Ideal model baseline only; real apparatus effects are not implemented.",
    }

HENSEN_2016_SOURCE_SHA256 = {
    "old_detector": "96D51CCFE8D2155B18A8C1D6ED4F620AC5BEFE152D08D429A74060584B24FC83",
    "new_detector": "1D07D08266F7DAB0A41D44C75264C05A237448AE7BA457A893F519444A5BA864",
}
HENSEN_2016_PUBLISHED = {"valid_trials": 300, "chsh_s": 2.35, "chsh_standard_error": 0.18}
HENSEN_2016_ROUNDING_TOLERANCES = {"chsh_s": 0.0055, "chsh_standard_error": 0.0055}


def _hensen_2016_state_statistics(products: dict[str, list[int]], wins: int) -> dict:
    counts = {key: len(values) for key, values in products.items()}
    if any(count == 0 for count in counts.values()):
        raise ValueError("source data produced no trials for one or more state/settings")
    correlations = {key: sum(values) / counts[key] for key, values in products.items()}
    errors = {key: math.sqrt(max(0.0, 1.0 - correlations[key] ** 2) / counts[key])
              for key in correlations}
    if set(products) == {"00", "01", "10", "11"}:
        if wins < 0:
            raise ValueError("wins cannot be negative")
    return {"setting_counts": counts, "correlations": correlations,
            "correlation_standard_errors": errors, "wins": wins}


def assess_hensen_2016_reproduction(result: dict) -> str:
    """Compare unrounded raw-data analysis with fixed publication tolerances."""
    if result.get("source_sha256") != HENSEN_2016_SOURCE_SHA256:
        return "FAILED"
    if result.get("valid_trials") != HENSEN_2016_PUBLISHED["valid_trials"]:
        return "FAILED"
    for key, tolerance in HENSEN_2016_ROUNDING_TOLERANCES.items():
        if abs(float(result[key]) - HENSEN_2016_PUBLISHED[key]) > tolerance:
            return "FAILED"
    return "VALIDATED"


def analyze_hensen_2016(old_detector_path: str | Path, new_detector_path: str | Path) -> dict:
    """Independently reprocess Hensen et al. (2016) raw trial records.

    Implements the author's released event filter. Times are ps for herald
    clicks and ns for spin readout. The old/new files are kept distinct because
    the replacement APD has a calibrated 700 ps channel-0 delay correction.
    DOI: 10.1038/srep30289; dataset DOI: 10.4121/uuid:53644d31-d862-4f9f-9ad2-0b571874b829.
    """
    sources = (("old_detector", Path(old_detector_path)), ("new_detector", Path(new_detector_path)))
    digests = {name: sha256_file(path) for name, path in sources}
    if digests != HENSEN_2016_SOURCE_SHA256:
        raise ValueError(f"Hensen 2016 source data checksum mismatch: {digests}")
    states = {
        "psi_minus": {key: [] for key in ("00", "01", "10", "11")},
        "psi_plus": {key: [] for key in ("00", "01", "10", "11")},
    }
    state_wins = {"psi_minus": 0, "psi_plus": 0}
    trials = []
    source_rows = 0
    starts_by_file = {"old_detector": {0: 5_426_000, 1: 5_425_100},
                      "new_detector": {0: 5_425_300, 1: 5_425_100}}
    first_window_ps = 50_000
    separation_ps = 250_000
    readout_start_ns, readout_end_ns = 10_620, 14_320
    for file_name, source in sources:
        starts = starts_by_file[file_name]
        with source.open("r", encoding="ascii", newline="") as handle:
            for row_number, row in enumerate(csv.reader(handle), start=1):
                source_rows += 1
                if len(row) != 17:
                    raise ValueError(f"expected 17 CSV fields in {file_name} row {row_number}, got {len(row)}")
                try:
                    (day, run, click1_time, click1_channel, click2_time, click2_channel,
                     setting_a, setting_b, rng_a, rng_b, readout_a, readout_b,
                     excite_a, excite_b, invalid_a, invalid_b) = [int(x) for x in row[1:]]
                except ValueError as exc:
                    raise ValueError(f"non-integer field in {file_name} row {row_number}") from exc
                del rng_a, rng_b
                if setting_a not in (0, 1) or setting_b not in (0, 1):
                    raise ValueError(f"unexpected binary setting in {file_name} row {row_number}")
                start1, start2 = starts.get(click1_channel), starts.get(click2_channel)
                first_valid = start1 is not None and start1 <= click1_time < start1 + first_window_ps
                same_channel = click1_channel == click2_channel
                state = "psi_plus" if same_channel else "psi_minus"
                second_window_ps = 50_000
                if state == "psi_plus":
                    second_window_ps = 4_000 if click2_channel == 0 else 2_500
                second_start = None if start2 is None else start2 + separation_ps
                second_valid = (second_start is not None
                                and second_start <= click2_time < second_start + second_window_ps)
                clean_markers = (invalid_a == 0 or invalid_a > 250) and (invalid_b == 0 or invalid_b > 250)
                no_excitation = excite_a == 0 and excite_b == 0
                if not (first_valid and second_valid and clean_markers and no_excitation):
                    continue
                outcome_a = 1 if readout_start_ns < readout_a <= readout_end_ns else -1
                outcome_b = 1 if readout_start_ns < readout_b <= readout_end_ns else -1
                key = f"{setting_a}{setting_b}"
                product = outcome_a * outcome_b
                states[state][key].append(product)
                exponent = setting_a * (setting_b if state == "psi_minus" else setting_b + 1)
                state_wins[state] += int(((-1) ** exponent) * product == 1)
                trials.append({"state": state, "setting_a": setting_a, "setting_b": setting_b,
                               "outcome_a": outcome_a, "outcome_b": outcome_b,
                               "day": day, "run": run, "detector_file": file_name})
    state_results = {}
    all_products = {key: [] for key in ("00", "01", "10", "11")}
    for state, products in states.items():
        stats = _hensen_2016_state_statistics(products, state_wins[state])
        e = stats["correlations"]
        if state == "psi_minus":
            chsh = e["00"] + e["01"] + e["10"] - e["11"]
        else:
            chsh = e["00"] + e["01"] - e["10"] + e["11"]
        chsh_se = math.sqrt(sum(value * value for value in stats["correlation_standard_errors"].values()))
        n_state = sum(stats["setting_counts"].values())
        state_results[state] = {**stats, "valid_trials": n_state, "chsh_s": chsh,
                                "chsh_standard_error": chsh_se,
                                "chsh_95_percent_interval": [chsh - 1.96 * chsh_se, chsh + 1.96 * chsh_se]}
        for key in all_products:
            all_products[key].extend(products[key])
    total = sum(len(v) for v in all_products.values())
    setting_counts = {key: len(values) for key, values in all_products.items()}
    correlations = {key: sum(values) / len(values) for key, values in all_products.items()}
    errors = {key: math.sqrt(max(0.0, 1.0 - correlations[key] ** 2) / setting_counts[key]) for key in correlations}
    weights = {state: state_results[state]["valid_trials"] / total for state in state_results}
    chsh = sum(weights[state] * state_results[state]["chsh_s"] for state in state_results)
    chsh_se = math.sqrt(sum((weights[state] * state_results[state]["chsh_standard_error"]) ** 2 for state in state_results))
    wins = sum(state_wins.values())
    tau = 2 * 5.4e-6
    q_bound = 0.75 + 3.0 * (tau + tau * tau)
    p_value = _binomial_upper_tail(total, wins, q_bound)
    result = {"source_sha256": digests, "source_rows": source_rows, "valid_trials": total,
              "setting_counts": setting_counts, "correlations": correlations,
              "correlation_standard_errors": errors, "states": state_results,
              "chsh_s": chsh, "chsh_standard_error": chsh_se,
              "chsh_95_percent_interval": [chsh - 1.96 * chsh_se, chsh + 1.96 * chsh_se],
              "chsh_winning_trials": wins, "complete_p_value_trials": (wins, total),
              "local_realist_win_probability_bound": q_bound, "complete_p_value": p_value,
              "published_complete_p_value": 0.061, "published_conventional_p_value": 0.029,
              "analysis_status": "", "model_validation_status": "NOT IMPLEMENTED",
              "trials": trials}
    result["analysis_status"] = assess_hensen_2016_reproduction(result)
    return result


def combine_hensen_results(result_2015: dict, result_2016: dict) -> dict:
    """Combine separate raw-data scores by trial-count weighting and score sum."""
    n15, n16 = result_2015["valid_trials"], result_2016["valid_trials"]
    n = n15 + n16
    s = (n15 * result_2015["chsh_s"] + n16 * result_2016["chsh_s"]) / n
    se = math.sqrt((n15 * result_2015["chsh_standard_error"]) ** 2
                   + (n16 * result_2016["chsh_standard_error"]) ** 2) / n
    wins = result_2015["chsh_winning_trials"] + result_2016["chsh_winning_trials"]
    q = max(result_2015["local_realist_win_probability_bound"],
            result_2016["local_realist_win_probability_bound"])
    return {"per_experiment": {"2015": result_2015, "2016": result_2016},
            "total_trials": n, "chsh_s": s, "chsh_standard_error": se,
            "chsh_95_percent_interval": [s - 1.96 * se, s + 1.96 * se],
            "complete_p_value_trials": (wins, n),
            "complete_p_value": _binomial_upper_tail(n, wins, q),
            "published_complete_p_value": 0.0080,
            "published_conventional_p_value": 0.0026,
            "published_fisher_independent_runs_p_value": 0.017,
            "interpretation": "Weighted descriptive CHSH; complete single-test score is recomputed from summed author-score wins."
            }


def _fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact test by probability ordering for a 2x2 table."""
    cells = (a, b, c, d)
    if any(value < 0 for value in cells):
        raise ValueError("contingency counts cannot be negative")
    row1, row2, col1 = a + b, c + d, a + c
    total = row1 + row2
    lo, hi = max(0, col1 - row2), min(row1, col1)
    denominator = math.comb(total, row1)
    observed = math.comb(col1, a) * math.comb(total - col1, row1 - a) / denominator
    p = 0.0
    for x in range(lo, hi + 1):
        probability = math.comb(col1, x) * math.comb(total - col1, row1 - x) / denominator
        if probability <= observed + 1e-12:
            p += probability
    return min(1.0, p)


def _wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        return [float("nan"), float("nan")]
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def _holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    adjusted = [1.0] * len(p_values)
    running = 0.0
    m = len(order)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def analyze_no_signaling(trials: list[dict], family_alpha: float = 0.05) -> dict:
    """Test local outcome vs remote setting conditional on local setting.

    Uses two-sided Fisher exact tests and Holm family-wise correction. This
    fixed-sample method assumes independent trial records; sequence-memory
    robustness is not established, so non-rejection is reported INCONCLUSIVE.
    """
    if not 0 < family_alpha < 1:
        raise ValueError("family_alpha must be between zero and one")
    if not trials:
        raise ValueError("no valid trials supplied")
    states = sorted({row["state"] for row in trials})
    raw_tests = []
    for state in states:
        sample = [row for row in trials if row["state"] == state]
        for party in ("A", "B"):
            for local_setting in (0, 1):
                remote_setting = "setting_b" if party == "A" else "setting_a"
                local_key = "setting_a" if party == "A" else "setting_b"
                outcome_key = "outcome_a" if party == "A" else "outcome_b"
                by_remote = []
                for remote in (0, 1):
                    chosen = [r[outcome_key] for r in sample
                              if r[local_key] == local_setting and r[remote_setting] == remote]
                    plus = sum(value == 1 for value in chosen)
                    by_remote.append({"remote_setting": remote, "n": len(chosen), "plus": plus,
                                      "plus_frequency": plus / len(chosen) if chosen else float("nan"),
                                      "wilson_95": _wilson_interval(plus, len(chosen))})
                a, b = by_remote[0]["plus"], by_remote[0]["n"] - by_remote[0]["plus"]
                c, d = by_remote[1]["plus"], by_remote[1]["n"] - by_remote[1]["plus"]
                p = _fisher_exact_two_sided(a, b, c, d) if all(x > 0 for x in (a+b, c+d)) else 1.0
                raw_tests.append({"state": state, "party": party, "local_setting": local_setting,
                                  "remote_setting_name": "b" if party == "A" else "a",
                                  "conditional_frequencies": by_remote,
                                  "contingency_table": [[a, b], [c, d]], "p_value": p})
    adjusted = _holm_adjust([item["p_value"] for item in raw_tests])
    for item, p_adj in zip(raw_tests, adjusted):
        item["holm_p_value"] = p_adj
        item["reject_at_family_alpha"] = p_adj <= family_alpha
    any_rejection = any(item["reject_at_family_alpha"] for item in raw_tests)
    return {"status": "SIGNIFICANT_DEVIATION_REQUIRES_DIAGNOSTIC" if any_rejection else "INCONCLUSIVE",
            "family_alpha": family_alpha, "tests": raw_tests,
            "test_method": "two-sided Fisher exact; Holm family-wise correction",
            "independence_assumption": "Independent fixed-sample trial records; serial memory is not modeled.",
            "heralding_note": "Tests are conditional on the supplied heralded/event-filtered trial sample.",
            "interpretation": "A rejection is an observed marginal dependence requiring systematic and sampling diagnostics; it is not evidence of controllable information transfer. Non-rejection does not prove no-signaling.",
            "communication_note": "Comparing the two observers' records requires classical communication; each local marginal is available without it."}
