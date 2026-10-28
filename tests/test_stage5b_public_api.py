import unittest


class Stage5BPublicAPITests(unittest.TestCase):
    def test_stage5b_entry_points_are_exported_without_ui_imports(self):
        import quantum_lab as ql

        for name in ("apply_subsystem_kraus", "prepare_dynamic_receiver_state",
                     "run_dynamic_receiver_experiment", "trace_distance",
                     "exact_observable_summary", "sample_observable",
                     "sequential_measurement_distribution", "sample_sequential_measurements",
                     "fisher_exact_two_sided", "holm_adjust", "estimate_joint_power",
                     "analyze_secondary_family", "lock_quantum_domino_protocol",
                     "run_quantum_domino_primary_sampling", "run_stage5b_experiment",
                     "load_stage5b_configuration"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(ql, name, None)))


if __name__ == "__main__":
    unittest.main()
