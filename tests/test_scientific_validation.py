import unittest
from pathlib import Path

from quantum_lab.scientific_validation import (
    analyze_hensen_2015,
    assess_hensen_2015_reproduction,
    sha256_file,
    hensen_ideal_model_baseline,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "references" / "hensen_2015"
RAW_DATA = REFERENCE / "original_files" / "bell_open_data.txt"
HENSEN_DATA_AVAILABLE = RAW_DATA.is_file()


class ScientificValidationTests(unittest.TestCase):
    @unittest.skipUnless(HENSEN_DATA_AVAILABLE, "Hensen 2015 source data are not included; see docs/source-register.md")
    def test_hensen_2015_reanalysis_reproduces_published_statistics(self):
        result = analyze_hensen_2015(RAW_DATA)
        self.assertEqual(result["valid_trials"], 245)
        self.assertEqual(result["setting_counts"], {"00": 53, "01": 79, "10": 62, "11": 51})
        self.assertAlmostEqual(result["chsh_s"], 2.4224998704613703, places=10)
        self.assertAlmostEqual(result["chsh_standard_error"], 0.20382659825201987, places=10)
        self.assertAlmostEqual(result["local_realist_p_value"], 0.039174643558790107, places=10)
        self.assertEqual(result["analysis_status"], "VALIDATED")

    @unittest.skipUnless(HENSEN_DATA_AVAILABLE, "Hensen 2015 source data are not included; see docs/source-register.md")
    def test_hensen_2015_status_is_based_on_predeclared_rounded_report_tolerances(self):
        result = analyze_hensen_2015(RAW_DATA)
        self.assertEqual(assess_hensen_2015_reproduction(result), "VALIDATED")
        changed = dict(result, chsh_s=result["chsh_s"] + 0.02)
        self.assertEqual(assess_hensen_2015_reproduction(changed), "FAILED")

    def test_ideal_model_baseline_uses_experimental_angles_but_does_not_claim_device_validation(self):
        baseline = hensen_ideal_model_baseline()
        self.assertAlmostEqual(baseline["chsh_s"], 2 * 2**0.5, places=12)
        self.assertEqual(baseline["model_comparison_status"], "NOT IMPLEMENTED")
        self.assertEqual(len(baseline["correlations"]), 4)
    @unittest.skipUnless(HENSEN_DATA_AVAILABLE, "Hensen 2015 source data are not included; see docs/source-register.md")
    def test_original_hensen_data_integrity_matches_versioned_manifest(self):
        expected = "5A6B1853554AD508D35C795415D64922ED9E5BC0469F6052AD222486AD3566FF"
        self.assertEqual(sha256_file(RAW_DATA), expected)


if __name__ == "__main__":
    unittest.main()
