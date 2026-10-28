import unittest

import numpy as np

from quantum_lab.multispin import partial_trace_subsystems, prepare_bell_pair_state
from quantum_lab.tfim import FieldSchedule


class DynamicReceiverTests(unittest.TestCase):
    def receiver_module(self):
        import importlib.util

        self.assertIsNotNone(importlib.util.find_spec("quantum_lab.dynamic_receiver"))
        import quantum_lab.dynamic_receiver as receiver
        return receiver

    def test_receiver_preparation_entangles_selected_nonadjacent_site_and_keeps_spectators(self):
        receiver = self.receiver_module()
        self.assertTrue(hasattr(receiver, "prepare_dynamic_receiver_state"))
        spectator = np.array([1, 1j], dtype=complex) / np.sqrt(2)
        ket = receiver.prepare_dynamic_receiver_state(4, entangled_receiver_site=2,
                                                       spectator_states={1: spectator, 3: np.array([1, 0])})
        np.testing.assert_allclose(partial_trace_subsystems(ket, [0, 2]),
                                   partial_trace_subsystems(prepare_bell_pair_state(4, [0, 2]), [0, 2]),
                                   atol=1e-12, rtol=0)
        np.testing.assert_allclose(partial_trace_subsystems(ket, [1]),
                                   np.outer(spectator, spectator.conj()), atol=1e-12, rtol=0)
        self.assertAlmostEqual(np.linalg.norm(ket), 1.0, places=12)

    def test_sender_operation_does_not_change_receiver_reduced_state_during_dynamics(self):
        receiver = self.receiver_module()
        self.assertTrue(hasattr(receiver, "run_dynamic_receiver_experiment"))
        initial = prepare_bell_pair_state(4, [0, 1])
        sigma_x = np.array([[0, 1], [1, 0]], dtype=complex)
        result = receiver.run_dynamic_receiver_experiment({
            "n_spins": 4,
            "J": .7,
            "h_schedule": FieldSchedule.constant(.4),
            "times_s": [0, .2, .7],
            "initial_state": initial,
            "sender_kraus_operators": [sigma_x],
            "local_controls": {},
            "solver_options": {"rtol": 1e-10, "atol": 1e-12},
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["configuration"]["receiver_sites"], [1, 2, 3])
        self.assertEqual(len(result["scenarios"]["reference"]["full_states"]), 3)
        self.assertEqual(len(result["scenarios"]["sender_operation"]["receiver_states"]), 3)
        self.assertGreater(np.linalg.norm(result["scenarios"]["reference"]["full_states"][-1]
                                          - result["scenarios"]["sender_operation"]["full_states"][-1]), 0.1)
        self.assertLess(max(result["metrics"]["sender_trace_distance"]), 1e-8)

    def test_positive_receiver_pulse_changes_exact_local_prediction_without_changing_sender_marginal(self):
        receiver = self.receiver_module()
        self.assertTrue(hasattr(receiver, "run_dynamic_receiver_experiment"))
        from quantum_lab.multispin import partial_trace_subsystems

        initial = prepare_bell_pair_state(4, [0, 1])
        pulse = FieldSchedule.gaussian(amplitude=.08, center_s=.4, width_s=.15)
        result = receiver.run_dynamic_receiver_experiment({
            "n_spins": 4,
            "J": .7,
            "h_schedule": FieldSchedule.constant(.4),
            "times_s": [0, .3, .5, .8],
            "initial_state": initial,
            "sender_kraus_operators": [np.eye(2)],
            "local_controls": {2: pulse},
            "solver_options": {"rtol": 1e-10, "atol": 1e-12},
        })
        self.assertEqual(result["status"], "success")
        baseline = result["scenarios"]["reference"]["receiver_observables"]["sigma_z"]
        controlled = result["scenarios"]["positive_control"]["receiver_observables"]["sigma_z"]
        self.assertGreater(np.max(np.abs(baseline[:, 1] - controlled[:, 1])), 1e-7)
        for branch in ("reference", "positive_control"):
            full = result["scenarios"][branch]["full_states"][-1]
            sender = partial_trace_subsystems(full, [0])
            np.testing.assert_allclose(sender, np.eye(2) / 2, atol=1e-10, rtol=0)

    def test_no_signaling_covers_entangled_product_correlated_and_mixed_inputs(self):
        receiver = self.receiver_module()
        self.assertTrue(hasattr(receiver, "run_dynamic_receiver_experiment"))
        sigma_x = np.array([[0, 1], [1, 0]], dtype=complex)
        sigma_z = np.diag([1, -1]).astype(complex)
        p0, p1 = np.diag([1, 0]), np.diag([0, 1])
        states = [
            prepare_bell_pair_state(4, [0, 1]),
            np.eye(16, dtype=complex)[3],
            .5 * (np.outer(np.eye(16)[0], np.eye(16)[0]) + np.outer(np.eye(16)[15], np.eye(16)[15])),
            .8 * np.outer(prepare_bell_pair_state(4, [0, 2]), prepare_bell_pair_state(4, [0, 2]).conj()) + .2 * np.eye(16) / 16,
        ]
        channels = ([sigma_x], [np.sqrt(.7) * np.eye(2), np.sqrt(.3) * sigma_z], [p0, p1])
        for state_index, state in enumerate(states):
            for channel_index, channel in enumerate(channels):
                with self.subTest(state=state_index, channel=channel_index):
                    result = receiver.run_dynamic_receiver_experiment({
                        "n_spins": 4,
                        "J": .3,
                        "h_schedule": FieldSchedule.constant(.5),
                        "times_s": [0, .15, .4],
                        "initial_state": state,
                        "sender_kraus_operators": channel,
                        "local_controls": {},
                    })
                    self.assertEqual(result["status"], "success")
                    self.assertLess(max(result["metrics"]["sender_trace_distance"]), 1e-8)

    def test_no_signaling_remains_below_tolerance_for_three_and_six_spin_registers(self):
        receiver = self.receiver_module()
        sigma_y = np.array([[0, -1j], [1j, 0]], dtype=complex)
        for n_spins, selected in ((3, 2), (6, 4)):
            state = prepare_bell_pair_state(n_spins, [0, selected])
            result = receiver.run_dynamic_receiver_experiment({
                "n_spins": n_spins,
                "J": .2,
                "h_schedule": FieldSchedule.sinusoidal(.3, .1, .05),
                "times_s": [0, .2, .6],
                "initial_state": state,
                "sender_kraus_operators": [sigma_y],
                "local_controls": {},
                "solver_options": {"rtol": 1e-10, "atol": 1e-12},
            })
            self.assertEqual(result["status"], "success")
            self.assertLess(max(result["metrics"]["sender_trace_distance"]), 1e-8)

    def test_trace_distance_rejects_nonphysical_density_input(self):
        receiver = self.receiver_module()
        self.assertAlmostEqual(receiver.trace_distance(np.diag([.8, .2]), np.diag([.5, .5])), .3, places=12)
        with self.assertRaises(ValueError):
            receiver.trace_distance(np.diag([1.2, -.2]), np.diag([1, 0]))


if __name__ == "__main__":
    unittest.main()
