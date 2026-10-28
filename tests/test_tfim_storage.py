import csv
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import numpy as np

from quantum_lab import experiments, tfim
from quantum_lab.storage import load_configuration, save_experiment


class TFIMStorageTests(unittest.TestCase):
    def runner(self, **overrides):
        self.assertTrue(callable(getattr(experiments, 'run_tfim_experiment', None)),
                        'run_tfim_experiment is not implemented')
        options = dict(n_spins=2, J=0.6, h_schedule=tfim.FieldSchedule.constant(0.2),
                       initial_state=np.array([1, 0, 0, 0], dtype=complex),
                       times_s=np.linspace(0, 1, 5), seed=123)
        options.update(overrides)
        return experiments.run_tfim_experiment(**options)

    def estimator(self, *args):
        self.assertTrue(callable(getattr(tfim, 'estimate_tfim_memory', None)),
                        'estimate_tfim_memory is not implemented')
        return tfim.estimate_tfim_memory(*args)

    def save(self, run, directory):
        paths = save_experiment(run['results'], run['configuration'], directory)
        record = json.loads(paths['json'].read_text(encoding='utf-8'))
        with paths['csv'].open(newline='', encoding='utf-8-sig') as handle:
            rows = {row['field']: row['value'] for row in csv.DictReader(handle)}
        return paths, record, rows

    def test_tfim_record_round_trips_exact_grid_schedule_and_solver_diagnostics(self):
        run = self.runner()
        with tempfile.TemporaryDirectory() as directory:
            paths, record, rows = self.save(run, directory)
            self.assertEqual(load_configuration(paths['json']), run['configuration'])
        self.assertEqual(record['schema_version'], 1)
        self.assertEqual(record['configuration']['h_schedule'], run['configuration']['h_schedule'])
        self.assertEqual(record['results']['diagnostics'], run['results']['diagnostics'])
        np.testing.assert_array_equal(record['results']['times_s'], run['results']['times_s'])
        self.assertEqual(record['results']['status'], 'success')
        self.assertTrue(record['results']['completed'])
        self.assertEqual(record['sources'], ['SRC-015', 'SRC-016', 'SRC-017', 'SRC-018', 'SRC-019'])
        self.assertIn('spectral', record['metadata']['method'])
        self.assertNotIn('Kraus', record['metadata']['method'])
        uuid.UUID(record['metadata']['experiment_id'])
        self.assertTrue(record['metadata']['code_version'])
        self.assertIn('numpy', record['metadata']['dependency_versions'])

    def test_records_model_units_basis_observable_selection_and_exact_complex_input(self):
        initial = np.array([1, 1j, 0, 0], dtype=complex)/np.sqrt(2)
        run = self.runner(initial_state=initial)
        config = run['configuration']
        self.assertEqual(config['n_spins'], 2)
        self.assertEqual(config['J'], 0.6)
        self.assertEqual(config['boundary_conditions'], 'OBC')
        self.assertEqual(config['bonds'], [[0, 1]])
        self.assertIn('big-endian', config['basis_order'])
        self.assertEqual(config['units']['time'], 's')
        self.assertEqual(config['units']['J'], 's^-1')
        restored = np.array(config['initial_state']['real'])+1j*np.array(config['initial_state']['imag'])
        np.testing.assert_array_equal(restored, initial)
        self.assertEqual(config['initial_state']['kind'], 'ket')
        self.assertEqual(set(config['observables']), set(run['results']['observables']))
        self.assertEqual(config['seed'], 123)
        np.testing.assert_array_equal(config['times_s'], np.linspace(0, 1, 5))

    def test_smooth_schedule_local_controls_and_tolerances_are_reproducible(self):
        schedule = tfim.FieldSchedule.sinusoidal(0.2, 0.4, 0.6)
        local = tfim.FieldSchedule.gaussian(0.3, 0.5, 0.2)
        run = self.runner(h_schedule=schedule, solver_options={
            'local_controls': {1: local}, 'rtol': 1e-5, 'atol': 1e-8,
            'max_steps': 1000, 'save_states_at': [0, 4]})
        with tempfile.TemporaryDirectory() as directory:
            _, record, _ = self.save(run, directory)
        self.assertIn('exponential_midpoint', record['metadata']['method'])
        config = record['configuration']
        self.assertEqual(tfim.FieldSchedule.from_dict(config['h_schedule']), schedule)
        self.assertEqual(tfim.FieldSchedule.from_dict(config['local_controls']['1']), local)
        self.assertEqual(config['solver_options']['rtol'], 1e-5)
        self.assertEqual(config['solver_options']['atol'], 1e-8)
        self.assertEqual(config['solver_options']['max_steps'], 1000)
        self.assertEqual(config['solver_options']['save_states_at'], [0, 4])
        self.assertEqual(set(record['results']['snapshots']), {'0', '4'})
        self.assertIn('maximum_scaled_local_error', record['results']['diagnostics'])
        self.assertIn('unitary_defect', record['results']['diagnostics'])

    def test_csv_preserves_large_arrays_and_complex_states_exactly(self):
        initial = np.array([1, 1j, 0, 0], dtype=complex)/np.sqrt(2)
        run = self.runner(initial_state=initial, times_s=np.linspace(0, 1, 1100),
                          solver_options={'save_states_at': [0, 1099]})
        with tempfile.TemporaryDirectory() as directory:
            _, record, rows = self.save(run, directory)
        for name, values in run['results']['observables'].items():
            np.testing.assert_array_equal(json.loads(rows['observables.'+name]), values)
        np.testing.assert_array_equal(json.loads(rows['times_s']), run['results']['times_s'])
        for field, values in [('final_state', run['results']['final_state']),
                              ('snapshots.0', run['results']['snapshots'][0])]:
            encoded = json.loads(rows[field])
            restored = np.array([complex(v['real'], v['imag']) for v in encoded])
            np.testing.assert_array_equal(restored, values)
        encoded = record['results']['final_state']
        np.testing.assert_array_equal([complex(v['real'], v['imag']) for v in encoded],
                                      run['results']['final_state'])

    def test_failed_and_cancelled_runs_preserve_partial_trajectory_and_reason(self):
        for options, status, reason in [({'max_steps': 1}, 'failed', 'max_steps'),
                                        ({'cancel_check': lambda: True}, 'cancelled', 'cancelled')]:
            with self.subTest(status=status):
                run = self.runner(solver_options=options)
                self.assertEqual(run['results']['status'], status)
                self.assertEqual(run['results']['error'], reason)
                self.assertFalse(run['results']['completed'])
                self.assertLess(len(run['results']['times_s']), len(run['configuration']['times_s']))
                with tempfile.TemporaryDirectory() as directory:
                    _, record, _ = self.save(run, directory)
                self.assertEqual(record['results']['status'], status)
                self.assertEqual(record['results']['error'], reason)
                self.assertFalse(record['results']['completed'])
                self.assertEqual(record['configuration'], run['configuration'])

    def test_memory_estimate_density_boundary_and_buffers(self):
        at_limit = self.estimator(6, 4096, 'density', True)
        self.assertEqual(at_limit['snapshot_bytes'], 256*1024**2)
        self.assertEqual(at_limit['state_bytes'], 16*4**6)
        self.assertEqual(at_limit['hamiltonian_bytes'], 16*4**6)
        self.assertGreater(at_limit['total_bytes'], at_limit['snapshot_bytes'])
        self.assertFalse(at_limit['exceeds_snapshot_limit'])
        self.assertTrue(self.estimator(6, 4097, 'density', True)['exceeds_snapshot_limit'])
        self.assertEqual(self.estimator(6, 4097, 'density', False)['snapshot_bytes'], 0)

    def test_memory_estimate_ket_boundary_and_validation(self):
        at_limit = self.estimator(6, 262144, 'ket', True)
        self.assertEqual(at_limit['snapshot_bytes'], 256*1024**2)
        self.assertEqual(at_limit['state_bytes'], 16*2**6)
        self.assertFalse(at_limit['exceeds_snapshot_limit'])
        self.assertTrue(self.estimator(6, 262145, 'ket', True)['exceeds_snapshot_limit'])
        for args in [(True, 1, 'ket', True), (7, 1, 'ket', True),
                     (2, -1, 'ket', True), (2, True, 'ket', True),
                     (2, 1, 'vector', True), (2, 1, 'ket', 1)]:
            with self.subTest(args=args), self.assertRaises((TypeError, ValueError)):
                tfim.estimate_tfim_memory(*args)

    def test_runner_rejects_over_budget_snapshots_before_evolve(self):
        state = np.eye(64, dtype=complex)/64
        with patch.object(tfim, 'evolve_tfim', side_effect=AssertionError('evolution allocated')) as evolve:
            with self.assertRaisesRegex(ValueError, '256 MiB'):
                self.runner(n_spins=6, initial_state=state, times_s=np.zeros(4097),
                            solver_options={'save_states_at': list(range(4097))})
            evolve.assert_not_called()

    def test_direct_evolution_rejects_over_budget_before_operator_allocation(self):
        with patch.object(tfim, '_observable_operators', side_effect=AssertionError('operators allocated')):
            with self.assertRaisesRegex(ValueError, '256 MiB'):
                tfim.evolve_tfim(np.eye(64)/64, 6, .6, tfim.FieldSchedule.constant(.2),
                                 np.zeros(4097), save_states_at=list(range(4097)))

    def test_solver_option_and_seed_validation(self):
        for options in [{'unknown': 1}, {'save_states_at': [0, 0]},
                        {'save_states_at': [5]}, {'local_controls': {'1': tfim.FieldSchedule.constant(1)}},
                        {'cancel_check': 1}, {'rtol': -1}]:
            with self.subTest(options=options), self.assertRaises((TypeError, ValueError)):
                self.runner(solver_options=options)
        for seed in [-1, True, 1.2]:
            with self.subTest(seed=seed), self.assertRaises((TypeError, ValueError)):
                self.runner(seed=seed)
        self.assertIsNone(self.runner(seed=None)['configuration']['seed'])

    def test_direct_evolution_accepts_exact_snapshot_budget(self):
        # Stop at the first operator allocation rather than allocating 256 MiB.
        with patch.object(tfim, '_observable_operators', side_effect=RuntimeError('budget accepted')):
            with self.assertRaisesRegex(RuntimeError, 'budget accepted'):
                tfim.evolve_tfim(np.eye(64)/64, 6, .6, tfim.FieldSchedule.constant(.2),
                                 np.zeros(4096), save_states_at=list(range(4096)))

    def test_budget_counts_selected_snapshots_instead_of_grid_length(self):
        run = self.runner(n_spins=6, initial_state=np.eye(64)/64,
                          times_s=np.zeros(4097), solver_options={'save_states_at': [0, 4096]})
        self.assertEqual(run['results']['status'], 'success')
        self.assertEqual(run['configuration']['memory_estimate']['snapshot_bytes'], 2*16*4**6)
        self.assertEqual(set(run['results']['snapshots']), {0, 4096})

    def test_complex_density_json_and_csv_restore_all_entries(self):
        ket = np.array([1, 1j, 0, 0])/np.sqrt(2)
        density = np.outer(ket, ket.conj())
        run = self.runner(initial_state=density, solver_options={'save_states_at': [0]})
        with tempfile.TemporaryDirectory() as directory:
            _, record, rows = self.save(run, directory)
        for encoded, original in [(json.loads(rows['snapshots.0']), density),
                                  (record['results']['final_state'], run['results']['final_state'])]:
            restored = np.array([[complex(v['real'], v['imag']) for v in row] for row in encoded])
            np.testing.assert_array_equal(restored, original)

    def test_piecewise_method_and_saved_source_ids_are_validated(self):
        run = self.runner(h_schedule=tfim.FieldSchedule.piecewise_constant([0, .4, 1], [.2, .3]))
        with tempfile.TemporaryDirectory() as directory:
            _, record, _ = self.save(run, directory)
            self.assertIn('piecewise_spectral', record['metadata']['method'])
            run['configuration']['sources'].append('SRC-FAKE')
            with self.assertRaisesRegex(ValueError, 'validated'):
                self.save(run, directory)
            run['configuration']['sources'].pop()
            run['results']['diagnostics']['method'] = 'fake_solver'
            with self.assertRaisesRegex(ValueError, 'supported propagation method'):
                self.save(run, directory)

    def test_callback_mutation_cannot_change_propagated_or_saved_inputs(self):
        state = np.array([1, 1j, 0, 0], dtype=complex)/np.sqrt(2)
        original_state = state.copy()
        schedule = tfim.FieldSchedule.constant(.15)
        controls = {0: schedule}
        expected = self.runner(initial_state=original_state.copy(),
                               solver_options={'local_controls': dict(controls)})
        calls = []

        def mutate_caller_inputs():
            calls.append(True)
            state[:] = [0, 0, 1, 0]
            controls.clear()
            controls[1] = tfim.FieldSchedule.constant(2)
            return False

        run = self.runner(initial_state=state, solver_options={
            'local_controls': controls, 'cancel_check': mutate_caller_inputs})
        self.assertTrue(calls)
        self.assertEqual(run['results']['status'], 'success')
        np.testing.assert_array_equal(state, [0, 0, 1, 0])
        self.assertEqual(set(controls), {1})
        np.testing.assert_array_equal(run['results']['final_state'], expected['results']['final_state'])
        for name in expected['results']['observables']:
            np.testing.assert_array_equal(run['results']['observables'][name],
                                          expected['results']['observables'][name])
        with tempfile.TemporaryDirectory() as directory:
            _, record, _ = self.save(run, directory)
        config = record['configuration']
        restored = np.array(config['initial_state']['real'])+1j*np.array(config['initial_state']['imag'])
        with self.subTest(record='initial_state'):
            np.testing.assert_array_equal(restored, original_state)
        with self.subTest(record='local_controls'):
            self.assertEqual(config['local_controls'], {'0': schedule.to_dict()})

    def test_static_rejects_over_budget_before_eigendecomposition(self):
        with patch.object(tfim.np.linalg, 'eigh', side_effect=AssertionError('spectral allocation')) as eigh:
            with self.assertRaisesRegex(ValueError, '256 MiB'):
                tfim.evolve_static(np.eye(64)/64, np.zeros((64, 64)), np.zeros(4097),
                                   save_states_at=list(range(4097)))
            eigh.assert_not_called()

    def test_static_accepts_exact_snapshot_budget_before_eigendecomposition(self):
        with patch.object(tfim.np.linalg, 'eigh', side_effect=RuntimeError('budget accepted')):
            with self.assertRaisesRegex(RuntimeError, 'budget accepted'):
                tfim.evolve_static(np.eye(64)/64, np.zeros((64, 64)), np.zeros(4096),
                                   save_states_at=list(range(4096)))

    def test_density_state_and_empty_snapshot_selection(self):
        state = np.eye(4, dtype=complex)/4
        run = self.runner(initial_state=state)
        self.assertEqual(run['configuration']['initial_state']['kind'], 'density')
        self.assertEqual(run['results']['snapshots'], {})
        np.testing.assert_allclose(run['results']['final_state'], state, atol=1e-14)
        self.assertEqual(run['configuration']['memory_estimate']['snapshot_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
