import unittest

import numpy as np

from quantum_lab.experiments import run_chsh_experiment, run_rotation_sweep, run_signaling_experiment, run_state_experiment
from quantum_lab.metrics import chsh_value, concurrence
from quantum_lab.states import bell_state, partial_trace, validate_density_matrix
from quantum_lab.operations import local_rotation, apply_local_unitary, measurement_probabilities


class PhysicsTests(unittest.TestCase):
  def test_chsh_protocol_reports_analytic_and_finite_shot_statistics(self):
    result = run_chsh_experiment(shots_per_setting=5000, seed=3)
    self.assertAlmostEqual(result["theoretical_chsh"], 2 * np.sqrt(2))
    self.assertEqual(len(result["settings"]), 4)
    self.assertGreater(result["sampled_chsh_standard_error"], 0)
    self.assertIn("standard_error", result["settings"]["ab"])
    self.assertTrue(abs(result["sampled_chsh"] - 2 * np.sqrt(2)) < 0.1)

  def test_rotation_sweep_returns_probabilities_for_each_time(self):
    result = run_rotation_sweep([0.0, 0.2, 0.4], axis=[0, 1, 0])
    self.assertEqual(len(result["times"]), 3)
    self.assertTrue(all(np.isclose(p[-1] + p[1], 1.0) for p in result["receiver_probabilities"]))

  def test_state_experiment_returns_analytic_and_sampled_joint_measurements(self):
    result = run_state_experiment("singlet", shots=3000, seed=4)
    self.assertTrue(np.isclose(sum(result["joint_probabilities"].values()), 1.0))
    self.assertEqual(sum(result["joint_counts"].values()), 3000)
    self.assertAlmostEqual(result["concurrence"], 1.0)

  def test_bell_state_is_valid_and_has_maximally_mixed_local_states(self):
    for name in ("singlet", "phi+", "phi-", "psi+"):
      with self.subTest(state=name):
        rho = bell_state(name)
        self.assertTrue(validate_density_matrix(rho))
        self.assertTrue(np.allclose(partial_trace(rho, keep=0), np.eye(2) / 2))
        self.assertTrue(np.allclose(partial_trace(rho, keep=1), np.eye(2) / 2))


  def test_local_rotation_does_not_change_remote_marginal(self):
    rho = bell_state("singlet")
    changed = apply_local_unitary(rho, local_rotation([1, 2, 3], 1.234), subsystem=0)
    self.assertTrue(np.allclose(partial_trace(changed, keep=1), partial_trace(rho, keep=1), atol=1e-12))


  def test_singlet_has_quantum_chsh_value_and_unit_concurrence(self):
    rho = bell_state("singlet")
    self.assertTrue(np.isclose(chsh_value(rho, [1, 0, 0], [0, 1, 0], [1, 1, 0], [1, -1, 0]), 2 * np.sqrt(2)))
    self.assertTrue(np.isclose(concurrence(rho), 1.0))


  def test_measurement_probabilities_are_normalized(self):
    p = measurement_probabilities(partial_trace(bell_state("singlet"), 1), [0.3, -0.4, 0.5])
    self.assertTrue(np.isclose(sum(p.values()), 1.0))
    self.assertTrue(np.allclose([p[-1], p[1]], [0.5, 0.5]))


  def test_signaling_run_is_reproducible_and_reports_local_statistics_only(self):
    first = run_signaling_experiment(shots=2000, seed=77)
    second = run_signaling_experiment(shots=2000, seed=77)
    self.assertEqual(first["receiver_counts"], second["receiver_counts"])
    self.assertEqual(first["receiver_local_distribution"], second["receiver_local_distribution"])
    self.assertEqual(first["receiver_local_distribution"]["0"], first["receiver_local_distribution"]["1"])
    self.assertFalse(first["sender_outcomes_exposed_to_receiver"])
    self.assertTrue(0.45 <= first["decoding_accuracy"] <= 0.55)

  def test_default_random_seed_makes_runs_reproducible(self):
    first = run_signaling_experiment(shots=200)
    second = run_signaling_experiment(shots=200)
    self.assertEqual(first["seed"], second["seed"])
    self.assertEqual(first["receiver_counts"], second["receiver_counts"])
    self.assertTrue(0.0 <= first["decoding_accuracy"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
