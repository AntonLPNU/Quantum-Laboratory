import unittest

import numpy as np


class Stage5BExperimentTests(unittest.TestCase):
    def test_wrapper_keeps_full_and_reduced_states_and_adds_exact_predictions(self):
        from quantum_lab import run_stage5b_experiment
        from quantum_lab.tfim import FieldSchedule

        result = run_stage5b_experiment({"n_spins": 3, "J": 1e5,
                                         "h_schedule": FieldSchedule.constant(2e5),
                                         "times_s": [0.0, 1e-6]})
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["scenarios"]["reference"]["full_states"]), 2)
        self.assertEqual(result["scenarios"]["reference"]["full_states"][0].shape, (8,))
        self.assertEqual(result["scenarios"]["reference"]["receiver_states"][0].shape, (4, 4))
        self.assertEqual(len(result["analysis"]["scenarios"]["reference"]["primary_observable"]["exact_by_time"]), 2)
        self.assertEqual(result["analysis"]["sampling_is_separate"], True)
        self.assertAlmostEqual(result["metrics"]["sender_trace_distance"][-1], 0.0, places=10)

    def test_saved_configuration_reloads_and_reproduces_exact_physics(self):
        import tempfile
        from pathlib import Path
        from quantum_lab import load_stage5b_configuration, run_stage5b_experiment, save_stage5b_experiment
        from quantum_lab.tfim import FieldSchedule

        config = {"n_spins": 3, "J": 1e5, "h_schedule": FieldSchedule.constant(2e5),
                  "times_s": [0.0, 1e-6], "primary_observable": {"site": 2, "pauli": "sigma_x"}}
        original = run_stage5b_experiment(config)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            paths = save_stage5b_experiment(original, original["configuration"], folder)
            restored = load_stage5b_configuration(paths["json"])
            repeated = run_stage5b_experiment(restored)
        np.testing.assert_array_equal(repeated["scenarios"]["reference"]["full_states"][1],
                                      original["scenarios"]["reference"]["full_states"][1])
        self.assertEqual(restored["h_schedule"].kind, "constant")
        self.assertEqual(restored["primary_observable"], {"site": 2, "pauli": "sigma_x"})


if __name__ == "__main__":
    unittest.main()
