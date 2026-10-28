import unittest

import numpy as np


class DeviationAnalyzerTests(unittest.TestCase):
    def analyzer(self):
        import importlib.util

        self.assertIsNotNone(importlib.util.find_spec("quantum_lab.deviation"))
        import quantum_lab.deviation as deviation
        return deviation

    def test_exact_mean_variance_distribution_and_seeded_samples_are_separate(self):
        deviation = self.analyzer()
        ket = np.array([1, 1], dtype=complex) / np.sqrt(2)
        sigma_z = np.diag([1, -1])
        exact = deviation.exact_observable_summary(ket, sigma_z)
        self.assertEqual(exact["kind"], "exact")
        self.assertAlmostEqual(exact["mean"], 0.0, places=12)
        self.assertAlmostEqual(exact["variance"], 1.0, places=12)
        self.assertEqual(set(exact["distribution"]), {-1.0, 1.0})
        for probability in exact["distribution"].values():
            self.assertAlmostEqual(probability, .5, places=12)
        sample = deviation.sample_observable(ket, sigma_z, 2000, np.random.default_rng(771))
        self.assertEqual(sample["kind"], "sample")
        self.assertEqual(sum(sample["counts"].values()), 2000)
        self.assertEqual(sample["born_distribution"], exact["distribution"])
        repeated = deviation.sample_observable(ket, sigma_z, 2000, np.random.default_rng(771))
        np.testing.assert_array_equal(sample["outcomes"], repeated["outcomes"])

    def test_explicit_sinusoid_fit_reports_phase_uncertainty_and_residuals(self):
        deviation = self.analyzer()
        times = np.linspace(0, 8, 161)
        values = .7 * np.sin(1.5 * times + .3) + .2
        result = deviation.fit_explicit_model(times, values, "sinusoid", {"omega_rad_s": 1.5})
        self.assertAlmostEqual(result["parameters"]["amplitude"], .7, places=12)
        self.assertAlmostEqual(result["parameters"]["phase_rad"], .3, places=12)
        self.assertAlmostEqual(result["parameters"]["offset"], .2, places=12)
        self.assertLess(max(np.abs(result["residuals"])), 1e-12)
        with self.assertRaises(ValueError):
            deviation.fit_explicit_model(times, values, "automatic_sine_guess", {})

    def test_spectrum_records_grid_window_normalization_and_rejects_nonuniform_time(self):
        deviation = self.analyzer()
        times = np.arange(128) * .1
        frequency = 5 / (128 * .1)
        values = np.cos(2 * np.pi * frequency * times)
        result = deviation.spectrum_uniform_grid(times, values, "rectangular")
        self.assertAlmostEqual(result["peak_frequency_hz"], frequency, places=12)
        self.assertAlmostEqual(result["frequency_resolution_hz"], 1 / (128 * .1), places=12)
        self.assertEqual(result["window"], "rectangular")
        self.assertIn("normalization", result)
        with self.assertRaises(ValueError):
            deviation.spectrum_uniform_grid([0, .1, .25, .3], [0, 1, 2, 3], "hann")

    def test_sequential_measurements_include_luders_back_action_and_sample_as_pairs(self):
        deviation = self.analyzer()
        ket0 = np.array([1, 0], dtype=complex)
        sigma_x = np.array([[0, 1], [1, 0]], dtype=complex)
        sigma_z = np.diag([1, -1])
        result = deviation.sequential_measurement_distribution(ket0, sigma_x, np.eye(2), sigma_z)
        rows = result["joint_outcomes"]
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertAlmostEqual(row["probability"], .25, places=12)
        sampled = deviation.sample_sequential_measurements(ket0, sigma_x, np.eye(2), sigma_z, 500, np.random.default_rng(18))
        self.assertEqual(sampled["outcomes"].shape, (500, 2))
        self.assertEqual(sum(item["count"] for item in sampled["joint_counts"]), 500)
        self.assertEqual(sampled["independent_preparations"], 500)


if __name__ == "__main__":
    unittest.main()
