from __future__ import annotations

import unittest

from scripts.stage5_validation_common import comparison_report


class ValidationReportTests(unittest.TestCase):
    def test_validation_report_identifies_equivalent_boundary_and_units(self):
        project = {"n_spins": 3, "boundary": "open", "pauli_normalization": "sigma_eigenvalues_pm1",
                   "time_unit": "s", "coupling_unit": "s^-1", "hamiltonian_convention": "H/hbar=-J*ZZ-h*X",
                   "J_s^-1": 1.0, "h_s^-1": 0.5, "times_s": [0.0, 0.2]}
        report = comparison_report(project, dict(project), {"max_state_error": 0.0})
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["equivalent_model"])
        self.assertEqual(report["project_model"]["boundary"], "open")
        self.assertEqual(report["reference_model"]["pauli_normalization"], "sigma_eigenvalues_pm1")
        self.assertEqual(report["reference_model"]["time_unit"], "s")

    def test_report_fails_when_boundary_or_units_differ(self):
        project = {"boundary": "open", "coupling_unit": "s^-1"}
        reference = {"boundary": "periodic", "coupling_unit": "rad/s"}
        report = comparison_report(project, reference, {"max_hamiltonian_error": 0.0})
        self.assertEqual(report["status"], "fail")
        self.assertEqual(set(report["model_mismatches"]), {"boundary", "coupling_unit"})

    def test_report_does_not_accept_missing_model_metadata(self):
        report = comparison_report({}, {}, {"max_state_error": 0.0})
        self.assertEqual(report["status"], "fail")
        self.assertIn("boundary", report["missing_metadata"]["project"])

    def test_report_rejects_invalid_error_numbers(self):
        with self.assertRaises(ValueError):
            comparison_report({}, {}, {"max_state_error": float("nan")})


if __name__ == "__main__":
    unittest.main()
