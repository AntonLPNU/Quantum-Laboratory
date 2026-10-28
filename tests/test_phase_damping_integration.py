import unittest
import gc
import warnings
from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

from quantum_lab.experiments import run_chsh_experiment, run_phase_damping_sweep, run_state_experiment
from quantum_lab.metrics import chsh_value, concurrence, maximal_chsh_value
from quantum_lab.noise import apply_local_phase_damping
from quantum_lab.operations import local_rotation, apply_local_unitary, measurement_probabilities
from quantum_lab.states import bell_state, partial_trace


class PhaseDampingIntegrationTests(unittest.TestCase):
    def test_singlet_concurrence_and_optimized_chsh_follow_two_sided_analytic_formulas(self):
        values_a = np.array([0.0, 0.2, 0.7, 1.0])
        values_b = np.array([0.0, 0.4, 1.0])
        sweep = run_phase_damping_sweep(values_a=values_a, values_b=values_b)
        q = (1.0 - values_a[:, None]) * (1.0 - values_b[None, :])

        np.testing.assert_allclose(sweep["concurrence"], q, atol=1e-10)
        np.testing.assert_allclose(sweep["chsh_maximal"], 2.0 * np.sqrt(1.0 + q**2), atol=1e-10)

    def test_fixed_axis_chsh_is_separate_from_optimized_chsh(self):
        sweep = run_phase_damping_sweep(values_a=[0.0, 0.5], values_b=[0.0, 0.5])
        self.assertIn("chsh_fixed", sweep)
        self.assertIn("chsh_maximal", sweep)
        self.assertAlmostEqual(sweep["chsh_maximal"][1, 1], 2.0 * np.sqrt(1.0 + 0.25**2))
        self.assertAlmostEqual(sweep["chsh_fixed"][1, 1], 2.0 * np.sqrt(2.0) * 0.25)
        self.assertNotAlmostEqual(sweep["chsh_fixed"][1, 1], sweep["chsh_maximal"][1, 1])

    def test_local_diagnostics_and_joint_probabilities_come_from_correct_states(self):
        sweep = run_phase_damping_sweep(values_a=[0.0, 0.6], values_b=[0.0, 0.3])
        self.assertIn("local_probabilities_a", sweep)
        self.assertIn("local_probabilities_b", sweep)
        self.assertIn("joint_probabilities", sweep)
        self.assertIn("density_matrices", sweep)
        rho = np.asarray(sweep["density_matrices"][1][1], dtype=complex)
        self.assertEqual(rho.shape, (4, 4))
        self.assertAlmostEqual(np.trace(rho).real, 1.0)
        expected = apply_local_phase_damping(apply_local_phase_damping(bell_state("singlet"), 0.6, 0), 0.3, 1)
        np.testing.assert_allclose(rho, expected, atol=1e-12)
        self.assertAlmostEqual(sum(sweep["joint_probabilities"]["zz"][1][1].values()), 1.0)
        self.assertAlmostEqual(sum(sweep["local_probabilities_b"][1][1].values()), 1.0)

    def test_single_run_applies_independent_a_and_b_controls_in_core(self):
        run = run_state_experiment(dephasing_a=0.2, dephasing_b=0.6)
        q = 0.8 * 0.4
        self.assertAlmostEqual(run["concurrence"], q, places=10)
        self.assertAlmostEqual(run["chsh_maximal"], 2.0 * np.sqrt(1.0 + q**2), places=10)
        self.assertEqual(run["dephasing_fractions"], {"a": 0.2, "b": 0.6})
        self.assertEqual(np.asarray(run["density_matrix"]).shape, (4, 4))

    def test_sweep_is_deterministic_and_records_exact_grid_and_seed(self):
        first = run_phase_damping_sweep(values_a=[0.0, 0.4, 1.0], values_b=[0.0, 0.7], seed=314)
        second = run_phase_damping_sweep(values_a=[0.0, 0.4, 1.0], values_b=[0.0, 0.7], seed=314)
        self.assertEqual(first["seed"], 314)
        np.testing.assert_array_equal(first["lambdas_a"], [0.0, 0.4, 1.0])
        np.testing.assert_array_equal(first["lambdas_b"], [0.0, 0.7])
        np.testing.assert_array_equal(first["concurrence"], second["concurrence"])
        np.testing.assert_array_equal(first["chsh_maximal"], second["chsh_maximal"])

    def test_sweep_composes_existing_local_rotations_before_the_noise_channels(self):
        rotations = {
            "a": {"axis": [1, 0, 0], "angle_rad": 0.31},
            "b": {"axis": [0, 1, 0], "angle_rad": -0.27},
        }
        sweep = run_phase_damping_sweep(values_a=[0.2], values_b=[0.4], rotations=rotations)
        expected = bell_state("singlet")
        for subsystem, key in ((0, "a"), (1, "b")):
            operation = rotations[key]
            expected = apply_local_unitary(expected, local_rotation(operation["axis"], operation["angle_rad"]), subsystem)
        expected = apply_local_phase_damping(apply_local_phase_damping(expected, 0.2, 0), 0.4, 1)
        np.testing.assert_allclose(sweep["density_matrices"][0][0], expected, atol=1e-12)
        self.assertEqual(sweep["rotations"], rotations)
        self.assertFalse(sweep["analytic_reference_applies"])

    def test_chsh_sampling_applies_two_local_channels_and_labels_fixed_axes_result(self):
        result = run_chsh_experiment(shots_per_setting=200, seed=9, dephasing_a=0.2, dephasing_b=0.5)
        q = 0.8 * 0.5
        self.assertAlmostEqual(result["theoretical_chsh"], 2.0 * np.sqrt(2.0) * q, places=10)
        self.assertEqual(result["dephasing_fractions"], {"a": 0.2, "b": 0.5})
        self.assertIn("fixed_axes", result)
        self.assertAlmostEqual(result["chsh_maximal"], 2.0 * np.sqrt(1.0 + q**2), places=10)

    def test_chsh_sampling_applies_selected_local_rotations_before_channels(self):
        rotations = {
            "a": {"axis": [1, 0, 0], "angle_rad": 0.31},
            "b": {"axis": [0, 1, 0], "angle_rad": -0.27},
        }
        result = run_chsh_experiment(shots_per_setting=100, seed=9, dephasing_a=0.2, dephasing_b=0.4, rotations=rotations)
        rho = bell_state("singlet")
        for subsystem, key in ((0, "a"), (1, "b")):
            op = rotations[key]
            rho = apply_local_unitary(rho, local_rotation(op["axis"], op["angle_rad"]), subsystem)
        rho = apply_local_phase_damping(apply_local_phase_damping(rho, 0.2, 0), 0.4, 1)
        a, a_prime = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
        b, b_prime = np.array([1.0, 1.0, 0.0]) / np.sqrt(2), np.array([1.0, -1.0, 0.0]) / np.sqrt(2)
        self.assertAlmostEqual(result["chsh_fixed"], chsh_value(rho, a, a_prime, b, b_prime), places=12)
        self.assertEqual(result["rotations"], rotations)

    def test_remote_local_operations_leave_untouched_party_state_and_probabilities_unchanged(self):
        zero = np.array([1.0, 0.0], dtype=complex)
        one = np.array([0.0, 1.0], dtype=complex)
        plus = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
        nonmax = np.cos(0.31) * np.kron(zero, zero) + np.sin(0.31) * np.kron(one, one)
        rho_nonmax = np.outer(nonmax, nonmax.conj())
        rho_product = np.outer(np.kron(plus, zero), np.kron(plus, zero).conj())
        rho_mixed_product = np.kron(np.eye(2) / 2.0, np.diag([0.8, 0.2]))
        states = {
            "singlet": bell_state("singlet"),
            "nonmax_entangled": rho_nonmax,
            "pure_product": rho_product,
            "mixed_product": rho_mixed_product,
        }
        self.assertGreater(concurrence(rho_nonmax), 0.0)
        self.assertLess(concurrence(rho_nonmax), 1.0)
        self.assertAlmostEqual(concurrence(rho_product), 0.0)
        rotation = local_rotation([1, 1, 0], 0.73)

        for name, rho in states.items():
            for remote, untouched in ((0, 1), (1, 0)):
                before = partial_trace(rho, untouched)
                operated = apply_local_unitary(rho, rotation, remote)
                operated = apply_local_phase_damping(operated, 0.37, remote)
                after = partial_trace(operated, untouched)
                with self.subTest(state=name, remote=remote):
                    np.testing.assert_allclose(after, before, atol=1e-10)
                    for axis in ([1, 0, 0], [0, 1, 0], [0, 0, 1]):
                        np.testing.assert_allclose(
                            list(measurement_probabilities(after, axis).values()),
                            list(measurement_probabilities(before, axis).values()),
                            atol=1e-10,
                        )

    def test_streamlit_exposes_independent_dephasing_controls_and_passes_them_to_core(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
            gc.collect()
        self.assertFalse([warning for warning in caught if issubclass(warning.category, ResourceWarning)])
        self.assertEqual(len(app.exception), 0)
        app.slider(key="lambda_a").set_value(0.25)
        app.slider(key="lambda_b").set_value(0.75)
        app.button[0].click().run()
        result = app.session_state["current_result"]
        self.assertEqual(result["dephasing_fractions"], {"a": 0.25, "b": 0.75})
        self.assertTrue(any("Фазове затухання" in tab.label for tab in app.tabs))
        self.assertEqual(len(app.selectbox(key="damping_plot").options), 16)


if __name__ == "__main__":
    unittest.main()
