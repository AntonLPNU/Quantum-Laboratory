import tempfile
import unittest
from pathlib import Path

import numpy as np

from quantum_lab.experiments import run_tfim_experiment
from quantum_lab.storage import save_experiment
from quantum_lab.tfim import FieldSchedule


class TFIMExampleTests(unittest.TestCase):
    def test_three_spin_open_tfim_example_has_reproducible_nontrivial_dynamics(self):
        times = np.linspace(0.0, 8.0, 101)
        initial = np.eye(8, dtype=complex)[:, 0]

        first = run_tfim_experiment(
            n_spins=3,
            J=1.0,
            h_schedule=FieldSchedule.constant(0.7),
            initial_state=initial,
            times_s=times,
            seed=123,
        )
        second = run_tfim_experiment(
            n_spins=3,
            J=1.0,
            h_schedule=FieldSchedule.constant(0.7),
            initial_state=initial,
            times_s=times,
            seed=123,
        )

        configuration = first['configuration']
        results = first['results']
        self.assertTrue(results['completed'])
        self.assertEqual(configuration['boundary_conditions'], 'OBC')
        self.assertEqual(configuration['n_spins'], 3)
        self.assertEqual(configuration['J'], 1.0)
        self.assertEqual(configuration['h_schedule']['parameters'], [0.7])
        self.assertEqual(configuration['times_s'], times.tolist())
        self.assertEqual(configuration['initial_state']['real'][0], 1.0)
        self.assertEqual(configuration['initial_state']['real'][1:], [0.0] * 7)

        observables = results['observables']
        self.assertGreater(float(np.ptp(observables['mean_sigma_z'])), 0.5)
        self.assertEqual(observables['nearest_neighbor_zz'].shape, (101, 2))
        self.assertTrue(np.all(np.isfinite(observables['nearest_neighbor_zz'])))
        self.assertGreater(float(np.ptp(observables['nearest_neighbor_zz'])), 0.05)
        for name in observables:
            np.testing.assert_array_equal(observables[name], second['results']['observables'][name])

        with tempfile.TemporaryDirectory() as directory:
            paths = save_experiment(results, configuration, directory)
            self.assertTrue(paths['json'].is_file())
            self.assertTrue(paths['csv'].is_file())
            import json
            record = json.loads(paths['json'].read_text(encoding='utf-8'))
        self.assertEqual(record['configuration'], configuration)
        self.assertEqual(record['results']['status'], 'success')
        np.testing.assert_array_equal(
            record['results']['observables']['nearest_neighbor_zz'],
            observables['nearest_neighbor_zz'],
        )


if __name__ == '__main__':
    unittest.main()
