import math
import unittest
from pathlib import Path

from quantum_lab.scientific_validation import (
    analyze_hensen_2015,
    analyze_hensen_2016,
    analyze_no_signaling,
    combine_hensen_results,
    hensen_ideal_model_baseline,
    _fisher_exact_two_sided,
    _holm_adjust,
)
from quantum_lab.apparatus import apply_binary_assignment_noise, assignment_channel_expectation, simulate_binary_readout_correlations

ROOT = Path(__file__).resolve().parents[1]
DATA_2015 = ROOT / "data" / "references" / "hensen_2015" / "original_files" / "bell_open_data.txt"
DATA_2016 = ROOT / "data" / "references" / "hensen_2016" / "original_files"
HENSEN_2015_AVAILABLE = DATA_2015.is_file()
HENSEN_2016_AVAILABLE = all(
    (DATA_2016 / name).is_file()
    for name in ("bell_open_data_2_old_detector.txt", "bell_open_data_2_new_detector.txt")
)


class HensenStage3Tests(unittest.TestCase):
    @unittest.skipUnless(HENSEN_2016_AVAILABLE, "Hensen 2016 source data are not included; see docs/source-register.md")
    def test_hensen_2016_reanalysis_uses_two_apd_files_and_reproduces_paper(self):
        result = analyze_hensen_2016(
            DATA_2016 / "bell_open_data_2_old_detector.txt",
            DATA_2016 / "bell_open_data_2_new_detector.txt",
        )
        self.assertEqual(result["source_rows"], 3918)
        self.assertEqual(result["valid_trials"], 300)
        self.assertEqual(result["setting_counts"], {"00": 69, "01": 69, "10": 78, "11": 84})
        self.assertEqual(result["states"]["psi_minus"]["valid_trials"], 228)
        self.assertEqual(result["states"]["psi_plus"]["valid_trials"], 72)
        self.assertAlmostEqual(result["states"]["psi_minus"]["chsh_s"], 2.308954698785207, places=10)
        self.assertAlmostEqual(result["states"]["psi_plus"]["chsh_s"], 2.4651039363113667, places=10)
        self.assertEqual(result["states"]["psi_minus"]["wins"], 179)
        self.assertEqual(result["states"]["psi_plus"]["wins"], 58)
        no_signal = analyze_no_signaling(result["trials"])
        self.assertEqual(no_signal["status"], "INCONCLUSIVE")
        self.assertAlmostEqual(min(test["p_value"] for test in no_signal["tests"]), 0.3568189252347234, places=10)
        self.assertAlmostEqual(result["chsh_s"], 2.3464305157914853, places=10)
        self.assertAlmostEqual(result["chsh_standard_error"], 0.18416242025166854, places=10)
        self.assertEqual(result["complete_p_value_trials"], (237, 300))
        self.assertAlmostEqual(result["complete_p_value"], 0.060727644566032656, places=10)
        self.assertEqual(result["analysis_status"], "VALIDATED")

    def test_ideal_baselines_preserve_heralded_state_identity(self):
        singlet = hensen_ideal_model_baseline("singlet")
        psi_plus = hensen_ideal_model_baseline("psi+")
        self.assertEqual(singlet["state"], "singlet")
        self.assertEqual(psi_plus["state"], "psi+")
        self.assertAlmostEqual(singlet["correlations"]["00"], -psi_plus["correlations"]["00"], places=12)
        self.assertEqual(psi_plus["model_comparison_status"], "NOT IMPLEMENTED")

    @unittest.skipUnless(HENSEN_2015_AVAILABLE and HENSEN_2016_AVAILABLE, "Hensen source data are not included; see docs/source-register.md")
    def test_combined_analysis_keeps_years_separate_and_reports_weighted_score(self):
        h15 = analyze_hensen_2015(DATA_2015)
        h16 = analyze_hensen_2016(
            DATA_2016 / "bell_open_data_2_old_detector.txt",
            DATA_2016 / "bell_open_data_2_new_detector.txt",
        )
        result = combine_hensen_results(h15, h16)
        self.assertEqual(result["total_trials"], 545)
        self.assertAlmostEqual(result["chsh_s"], 2.3806268311935437, places=10)
        self.assertAlmostEqual(result["chsh_standard_error"], 0.13664708511691795, places=10)
        self.assertEqual(result["complete_p_value_trials"], (433, 545))
        self.assertAlmostEqual(result["complete_p_value"], 0.008446211313835446, places=10)

    def test_exact_fisher_and_holm_adjustment_match_hand_checkable_references(self):
        self.assertAlmostEqual(_fisher_exact_two_sided(1, 9, 11, 3), 0.0027594561852200836, places=12)
        self.assertEqual(_holm_adjust([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])

    @unittest.skipUnless(HENSEN_2015_AVAILABLE, "Hensen 2015 source data are not included; see docs/source-register.md")
    def test_hensen_2015_no_signaling_is_analyzed_separately(self):
        result = analyze_hensen_2015(DATA_2015)
        no_signal = analyze_no_signaling(result["trials"])
        self.assertEqual(len(no_signal["tests"]), 4)
        self.assertEqual(no_signal["status"], "INCONCLUSIVE")
        self.assertAlmostEqual(min(test["p_value"] for test in no_signal["tests"]), 0.48112039371576926, places=10)
        self.assertTrue(all(test["holm_p_value"] == 1.0 for test in no_signal["tests"]))

    def test_no_signaling_reports_conditional_tests_holm_and_inconclusive_status(self):
        trials = []
        # Balanced local outcomes at each local setting, repeated identically
        # for both remote settings, for each heralded state.
        for state in ("psi_minus", "psi_plus"):
            for a in (0, 1):
                for b in (0, 1):
                    for outcome_a, outcome_b in ((1, 1), (1, -1), (-1, 1), (-1, -1)) * 5:
                        trials.append({"state": state, "setting_a": a, "setting_b": b,
                                       "outcome_a": outcome_a, "outcome_b": outcome_b})
        result = analyze_no_signaling(trials)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(len(result["tests"]), 8)
        self.assertTrue(all(test["holm_p_value"] == 1.0 for test in result["tests"]))
        self.assertEqual(result["family_alpha"], 0.05)
        self.assertTrue(all("wilson_95" in cell for test in result["tests"] for cell in test["conditional_frequencies"]))

    def test_readout_component_attenuates_correlations_analytically_without_validation_claim(self):
        result = simulate_binary_readout_correlations({"00": -1.0, "01": 0.5}, 0.8, 0.9)
        self.assertAlmostEqual(result["attenuation"], 0.48)
        self.assertAlmostEqual(result["correlations"]["00"], -0.48)
        self.assertAlmostEqual(result["correlations"]["01"], 0.24)
        self.assertEqual(result["status"], "COMPONENT ONLY - NOT APPARATUS VALIDATION")
        self.assertIsNone(result["seed"])

    def test_assignment_channel_matches_binary_symmetric_channel_expectation(self):
        self.assertEqual(assignment_channel_expectation(1, 1.0), 1.0)
        self.assertEqual(assignment_channel_expectation(-1, 0.5), 0.0)
        self.assertAlmostEqual(assignment_channel_expectation(-1, 0.8), -0.6)

    def test_binary_assignment_error_is_seeded_and_preserves_perfect_fidelity(self):
        values = [1, -1, 1, -1] * 100
        self.assertEqual(apply_binary_assignment_noise(values, 1.0, seed=5), values)
        first = apply_binary_assignment_noise(values, 0.8, seed=13)
        second = apply_binary_assignment_noise(values, 0.8, seed=13)
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(values))
        self.assertTrue(set(first) <= {-1, 1})
        with self.assertRaises(ValueError):
            apply_binary_assignment_noise(values, 1.1, seed=5)


if __name__ == "__main__":
    unittest.main()
