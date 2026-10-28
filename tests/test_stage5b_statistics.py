import unittest


class Stage5BStatisticsTests(unittest.TestCase):
    def statistics(self):
        import importlib.util

        self.assertIsNotNone(importlib.util.find_spec("quantum_lab.stage5b_statistics"))
        import quantum_lab.stage5b_statistics as statistics
        return statistics

    def test_fisher_exact_matches_hand_checkable_tables_and_boundaries(self):
        statistics = self.statistics()
        self.assertAlmostEqual(statistics.fisher_exact_two_sided(5, 10, 0, 10), .0325077399380805, places=12)
        self.assertEqual(statistics.fisher_exact_two_sided(1, 1, 0, 1), 1.0)
        self.assertEqual(statistics.fisher_exact_two_sided(0, 20, 0, 20), 1.0)
        with self.assertRaises(ValueError):
            statistics.fisher_exact_two_sided(21, 20, 0, 20)

    def test_holm_adjustment_preserves_input_order_and_monotonicity(self):
        statistics = self.statistics()
        self.assertEqual(statistics.holm_adjust([.01, .04, .03]), [.03, .06, .06])
        self.assertEqual(statistics.holm_adjust([.5, .5]), [1.0, 1.0])
        with self.assertRaises(ValueError):
            statistics.holm_adjust([-.1])

    def test_newcombe_wilson_interval_has_correct_orientation_and_bounds(self):
        statistics = self.statistics()
        lower, upper = statistics.newcombe_wilson_interval(70, 100, 50, 100, .995)
        self.assertLess(lower, .2)
        self.assertGreater(upper, .2)
        self.assertGreater(lower, -1)
        self.assertLess(upper, 1)
        reversed_interval = statistics.newcombe_wilson_interval(50, 100, 70, 100, .995)
        self.assertAlmostEqual(reversed_interval[0], -upper, places=12)
        self.assertAlmostEqual(reversed_interval[1], -lower, places=12)

    def test_shared_control_power_is_deterministic_and_reports_mc_uncertainty(self):
        statistics = self.statistics()
        result = statistics.estimate_joint_power([.5, .65, .62], 1200, alpha=.01, simulations=2000, seed=3107)
        repeated = statistics.estimate_joint_power([.5, .65, .62], 1200, alpha=.01, simulations=2000, seed=3107)
        self.assertEqual(result, repeated)
        self.assertEqual(result["simulations"], 2000)
        self.assertGreater(result["familywise_power"], .8)
        self.assertIn("familywise_power_95_percent_wilson_interval", result)
        self.assertLessEqual(result["familywise_power_95_percent_wilson_interval"][0], result["familywise_power"])
        self.assertGreaterEqual(result["familywise_power_95_percent_wilson_interval"][1], result["familywise_power"])

    def test_joint_power_means_both_holm_comparisons_reject(self):
        statistics = self.statistics()
        result = statistics.estimate_joint_power([.5, .54, .54], 100, alpha=.01, simulations=2000, seed=3107)
        self.assertIn("joint_power", result)
        self.assertLessEqual(result["joint_power"], result["familywise_power"])
        self.assertLess(result["joint_power"], result["familywise_power"])
        self.assertLessEqual(result["joint_power"], min(result["primary_power"]))
        self.assertIn("joint_power_95_percent_wilson_interval", result)
        self.assertEqual(result["joint_power_event"], "both_primary_hypotheses_rejected_after_holm")

    def test_secondary_family_reports_separately_holm_adjusted_results(self):
        statistics = self.statistics()
        result = statistics.analyze_secondary_family({"late_sigma_z": .01, "fft_peak": .04})
        self.assertEqual(result["family_size"], 2)
        self.assertEqual(result["method"], "Holm adjustment; exploratory family")
        self.assertEqual(result["results"]["late_sigma_z"]["holm_adjusted_p_value"], .02)
        self.assertEqual(result["results"]["fft_peak"]["holm_adjusted_p_value"], .04)
        with self.assertRaises(ValueError):
            statistics.analyze_secondary_family({})


if __name__ == "__main__":
    unittest.main()
