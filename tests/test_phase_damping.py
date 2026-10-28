"""Independent phase-damping references: Choi Kraus maps and GKS/Lindblad generators (SRC-010–013)."""
from __future__ import annotations

import unittest

import numpy as np

from quantum_lab.experiments import run_signaling_experiment
from quantum_lab.metrics import concurrence, correlator
from quantum_lab.noise import apply_local_phase_damping, phase_damping
from quantum_lab.states import bell_state, validate_density_matrix


class PhaseDampingTests(unittest.TestCase):
    @staticmethod
    def _valid_state(dimension: int) -> np.ndarray:
        values = np.arange(1, dimension * dimension + 1, dtype=float).reshape(dimension, dimension)
        matrix = values + 1j * np.flipud(values)
        density = matrix @ matrix.conj().T
        return density / np.trace(density)

    @staticmethod
    def _kraus_operators(dephasing_fraction: float) -> tuple[np.ndarray, np.ndarray]:
        identity = np.eye(2, dtype=complex)
        z = np.diag([1.0, -1.0]).astype(complex)
        return (
            np.sqrt(1.0 - dephasing_fraction / 2.0) * identity,
            np.sqrt(dephasing_fraction / 2.0) * z,
        )

    def test_single_qubit_channel_matches_direct_kraus_sum(self) -> None:
        rho = self._valid_state(2)
        for fraction in (0.0, 0.17, 0.8, 1.0):
            expected = sum(k @ rho @ k.conj().T for k in self._kraus_operators(fraction))
            np.testing.assert_allclose(phase_damping(rho, fraction), expected, atol=1e-14)

    def test_local_channel_matches_kraus_sum_and_retains_full_two_spin_state(self) -> None:
        rho = self._valid_state(4)
        identity = np.eye(2, dtype=complex)
        for subsystem in (0, 1):
            for fraction in (0.0, 0.37, 1.0):
                expected = np.zeros((4, 4), dtype=complex)
                for kraus in self._kraus_operators(fraction):
                    full_kraus = np.kron(kraus, identity) if subsystem == 0 else np.kron(identity, kraus)
                    expected += full_kraus @ rho @ full_kraus.conj().T
                actual = apply_local_phase_damping(rho, fraction, subsystem)
                self.assertEqual(actual.shape, (4, 4))
                np.testing.assert_allclose(actual, expected, atol=1e-14)
                self.assertTrue(validate_density_matrix(actual))

    def test_single_qubit_channel_preserves_populations_and_scales_coherence(self) -> None:
        plus = np.array([[0.5, 0.5], [0.5, 0.5]], dtype=complex)
        for fraction in (0.0, 0.23, 1.0):
            actual = phase_damping(plus, fraction)
            np.testing.assert_allclose(np.diag(actual), np.diag(plus), atol=1e-14)
            self.assertAlmostEqual(actual[0, 1].real, (1.0 - fraction) * plus[0, 1].real, places=14)
            self.assertAlmostEqual(actual[0, 1].imag, 0.0, places=14)
            self.assertAlmostEqual(np.trace(actual).real, 1.0, places=14)
            self.assertGreaterEqual(np.linalg.eigvalsh(actual).min(), -1e-14)

    def test_one_sided_damping_of_singlet_has_linear_concurrence_and_exact_endpoints(self) -> None:
        singlet = bell_state("singlet")
        for fraction in (0.0, 0.2, 0.63, 1.0):
            actual = apply_local_phase_damping(singlet, fraction, subsystem=0)
            self.assertAlmostEqual(concurrence(actual), 1.0 - fraction, places=12)
        self.assertAlmostEqual(concurrence(apply_local_phase_damping(singlet, 0.0, 0)), 1.0, places=12)
        self.assertAlmostEqual(concurrence(apply_local_phase_damping(singlet, 1.0, 0)), 0.0, places=12)

    def test_sender_local_channel_leaves_receiver_marginal_maximally_mixed(self) -> None:
        singlet = bell_state("singlet")
        maximally_mixed = np.eye(2, dtype=complex) / 2.0
        for fraction in (0.0, 0.41, 1.0):
            actual = apply_local_phase_damping(singlet, fraction, subsystem=0)
            receiver = np.einsum("abad->bd", actual.reshape(2, 2, 2, 2))
            np.testing.assert_allclose(receiver, maximally_mixed, atol=1e-14)

    def test_both_local_channels_keep_full_state_for_joint_analysis(self) -> None:
        rho = bell_state("singlet")
        after_a = apply_local_phase_damping(rho, 0.2, subsystem=0)
        after_a_and_b = apply_local_phase_damping(after_a, 0.3, subsystem=1)
        self.assertEqual(after_a_and_b.shape, (4, 4))
        self.assertTrue(validate_density_matrix(after_a_and_b))
        self.assertLess(concurrence(after_a_and_b), concurrence(after_a))
        fraction = 0.2
        one_sided = apply_local_phase_damping(bell_state("singlet"), fraction, subsystem=0)
        self.assertAlmostEqual(correlator(one_sided, [1, 0, 0], [1, 0, 0]), -(1.0 - fraction), places=12)
        self.assertAlmostEqual(correlator(one_sided, [0, 0, 1], [0, 0, 1]), -1.0, places=12)

    def test_independent_rk4_lindblad_solution_converges_to_kraus_channel(self) -> None:
        z = np.diag([1.0, -1.0]).astype(complex)
        plus = np.array([[0.5, 0.5], [0.5, 0.5]], dtype=complex)

        def integrate(fraction: float, steps: int) -> np.ndarray:
            # Unit-time generator from GKS/Lindblad (SRC-011, SRC-012); λ=1 uses its analytic limit below.
            gamma = -np.log1p(-fraction)
            dt = 1.0 / steps

            def derivative(state: np.ndarray) -> np.ndarray:
                return 0.5 * gamma * (z @ state @ z - state)

            state = plus.copy()
            for _ in range(steps):
                k1 = derivative(state)
                k2 = derivative(state + 0.5 * dt * k1)
                k3 = derivative(state + 0.5 * dt * k2)
                k4 = derivative(state + dt * k3)
                state = state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
            return state

        for fraction in (0.2, 0.75):
            coarse_error = np.linalg.norm(integrate(fraction, 10) - phase_damping(plus, fraction))
            fine_error = np.linalg.norm(integrate(fraction, 20) - phase_damping(plus, fraction))
            self.assertLess(fine_error, coarse_error / 10.0)
            self.assertLess(fine_error, 1e-7)

        complete_dephasing_limit = np.diag(np.diag(plus)).astype(complex)
        np.testing.assert_allclose(phase_damping(plus, 1.0), complete_dephasing_limit, atol=1e-14)

    def test_signaling_run_samples_only_receiver_marginals_with_local_damping(self) -> None:
        result = run_signaling_experiment(
            shots=5000,
            seed=18,
            receiver_axis=[1, 0, 0],
            sender_dephasing=0.43,
            receiver_dephasing=0.7,
        )
        self.assertEqual(result["model"], "two_spin_projective_with_local_phase_damping")
        self.assertEqual(result["apparatus_calibration_status"], "NOT_CALIBRATED")
        self.assertFalse(result["sender_outcomes_exposed_to_receiver"])
        self.assertTrue(result["sender_setting_labels_are_analysis_only"])
        self.assertNotIn("rho_ab", result)
        self.assertNotIn("density_matrix", result)
        self.assertEqual(sum(result["receiver_counts"]["0"].values()), 5000)
        self.assertEqual(sum(result["receiver_counts"]["1"].values()), 5000)
        for distribution in result["receiver_local_distribution"].values():
            self.assertAlmostEqual(distribution["-1"], 0.5, places=12)
            self.assertAlmostEqual(distribution["+1"], 0.5, places=12)

    def test_dephasing_fraction_and_subsystem_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            phase_damping(np.eye(2) / 2, -0.01)
        with self.assertRaises(ValueError):
            phase_damping(np.eye(2) / 2, 1.01)
        with self.assertRaises(ValueError):
            phase_damping(np.eye(3), 0.2)
        with self.assertRaises(ValueError):
            apply_local_phase_damping(np.eye(4) / 4, 0.2, 2)


if __name__ == "__main__":
    unittest.main()
