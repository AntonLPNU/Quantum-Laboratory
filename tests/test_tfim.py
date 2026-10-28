"""Independent analytic and explicit-Kronecker references for the open TFIM."""
import unittest
import tracemalloc
import warnings

import numpy as np

from quantum_lab.tfim import local_pauli, open_tfim_hamiltonian

I = np.eye(2, dtype=np.complex128)
PAULI = {
    "x": np.array([[0, 1], [1, 0]], dtype=np.complex128),
    "y": np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
    "z": np.diag([1, -1]).astype(np.complex128),
}


def kron_operator(n_spins, assignments):
    result = np.array([[1]], dtype=np.complex128)
    for site in range(n_spins):
        result = np.kron(result, assignments.get(site, I))
    return result


def reference_hamiltonian(n_spins, J, h):
    result = np.zeros((2 ** n_spins,) * 2, dtype=np.complex128)
    for site in range(n_spins - 1):
        result -= J * kron_operator(n_spins, {site: PAULI["z"], site + 1: PAULI["z"]})
    for site in range(n_spins):
        result -= h * kron_operator(n_spins, {site: PAULI["x"]})
    return result


class TFIMHamiltonianTests(unittest.TestCase):
    def test_two_spin_open_tfim_spectrum_is_analytic(self):
        for J, h in ((0.7, -0.3), (-0.7, 0.3), (0.0, 0.3), (0.7, 0.0), (0.0, 0.0)):
            with self.subTest(J=J, h=h):
                actual = np.linalg.eigvalsh(open_tfim_hamiltonian(2, J, h))
                root = np.sqrt(J * J + 4 * h * h)
                np.testing.assert_allclose(actual, np.sort([-root, -J, J, root]), atol=1e-12, rtol=0)

    def test_open_chain_has_no_last_to_first_bond(self):
        actual = open_tfim_hamiltonian(3, J=1.0, h=0.0)
        expected = -np.kron(np.kron(PAULI["z"], PAULI["z"]), I) - np.kron(np.kron(I, PAULI["z"]), PAULI["z"])
        np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)

    def test_signed_and_zero_parameters_match_independent_matrices(self):
        for n_spins in range(2, 7):
            for J, h in ((0.7, 0.3), (-0.7, 0.3), (0.7, -0.3), (-0.7, -0.3), (0.0, 0.3), (0.7, 0.0), (0.0, 0.0)):
                with self.subTest(n_spins=n_spins, J=J, h=h):
                    actual = open_tfim_hamiltonian(n_spins, J, h)
                    expected = reference_hamiltonian(n_spins, J, h)
                    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)
                    np.testing.assert_allclose(np.linalg.eigvalsh(actual), np.linalg.eigvalsh(expected), atol=1e-12, rtol=0)

    def test_shape_dtype_and_hermiticity(self):
        for n_spins in range(2, 7):
            with self.subTest(n_spins=n_spins):
                actual = open_tfim_hamiltonian(n_spins, -0.9, 0.4)
                self.assertEqual(actual.shape, (2 ** n_spins,) * 2)
                self.assertEqual(actual.dtype, np.dtype(np.complex128))
                np.testing.assert_array_equal(actual, actual.conj().T)

    def test_zero_field_has_exactly_n_minus_one_bonds(self):
        for n_spins in range(2, 7):
            actual = open_tfim_hamiltonian(n_spins, 1.0, 0.0)
            self.assertEqual(actual[0, 0], -(n_spins - 1))
            np.testing.assert_array_equal(actual, np.diag(np.diag(actual)))

    def test_zero_coupling_spectrum_is_sum_of_independent_spin_energies(self):
        for n_spins in range(2, 7):
            h = -0.3
            expected = sorted(-h * sum(1 if (bits >> site) & 1 else -1 for site in range(n_spins)) for bits in range(2 ** n_spins))
            np.testing.assert_allclose(np.linalg.eigvalsh(open_tfim_hamiltonian(n_spins, 0.0, h)), expected, atol=1e-12, rtol=0)

    def test_reversing_both_signs_negates_hamiltonian(self):
        np.testing.assert_array_equal(open_tfim_hamiltonian(4, -0.7, -0.3), -open_tfim_hamiltonian(4, 0.7, 0.3))

    def test_rejects_nonfinite_or_nonreal_parameters(self):
        for invalid in (np.nan, np.inf, -np.inf, 1j, 0.3 + 0j, "0.3", True, np.bool_(False), [0.3], None):
            for parameter in ("J", "h"):
                with self.subTest(invalid=invalid, parameter=parameter):
                    kwargs = {"J": 0.7, "h": 0.3, parameter: invalid}
                    with self.assertRaises((TypeError, ValueError)):
                        open_tfim_hamiltonian(2, **kwargs)

    def test_rejects_finite_coefficients_when_output_overflows(self):
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            for J in (1e308, -1e308):
                with self.subTest(J=J), self.assertRaisesRegex(ValueError, "representable.*complex128"):
                    open_tfim_hamiltonian(6, J, 0.0)
        self.assertEqual(emitted, [])

    def test_large_representable_coefficients_remain_supported(self):
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            for n_spins, J, h in ((2, 1e308, 0.0), (6, 1e307, 0.0), (6, 0.0, 1e308)):
                with self.subTest(n_spins=n_spins, J=J, h=h):
                    actual = open_tfim_hamiltonian(n_spins, J, h)
                    self.assertTrue(np.all(np.isfinite(actual)))
                    np.testing.assert_array_equal(actual, actual.conj().T)
        self.assertEqual(emitted, [])

    def test_accepts_real_numpy_scalars_and_integer_parameters(self):
        np.testing.assert_array_equal(open_tfim_hamiltonian(np.int64(2), np.float64(0.7), np.float32(0.3)), reference_hamiltonian(2, 0.7, float(np.float32(0.3))))
        np.testing.assert_array_equal(open_tfim_hamiltonian(2, 1, 0), reference_hamiltonian(2, 1, 0))

    def test_rejects_unsupported_or_noninteger_register_sizes(self):
        for invalid in (0, 1, 7, -1, 2.0, True, np.bool_(False), "2", None):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                open_tfim_hamiltonian(invalid, 0.7, 0.3)


class LocalPauliTests(unittest.TestCase):
    def test_all_sites_and_components_match_explicit_kronecker(self):
        for n_spins in range(2, 7):
            for site in range(n_spins):
                for component in PAULI:
                    with self.subTest(n_spins=n_spins, site=site, component=component):
                        actual = local_pauli(n_spins, site, component)
                        np.testing.assert_array_equal(actual, kron_operator(n_spins, {site: PAULI[component]}))
                        np.testing.assert_array_equal(actual @ actual, np.eye(2 ** n_spins))

    def test_site_zero_is_leftmost_tensor_factor(self):
        ket = np.zeros(8, dtype=complex)
        ket[0] = 1
        self.assertEqual(np.argmax(abs(local_pauli(3, 0, "x") @ ket)), 4)
        self.assertEqual(np.argmax(abs(local_pauli(3, 2, "x") @ ket)), 1)

    def test_rejects_invalid_component_site_or_size(self):
        for component in ("X", "q", "", None, ["x"]):
            with self.subTest(component=component), self.assertRaises((TypeError, ValueError)):
                local_pauli(3, 0, component)
        for site in (-1, 3, 1.0, True, np.bool_(False), "0", None):
            with self.subTest(site=site), self.assertRaises((TypeError, ValueError)):
                local_pauli(3, site, "x")
        for n_spins in (1, 7, 3.0, True):
            with self.subTest(n_spins=n_spins), self.assertRaises((TypeError, ValueError)):
                local_pauli(n_spins, 0, "x")

class TFIMStaticEvolutionTests(unittest.TestCase):
    def setUp(self):
        from quantum_lab import tfim
        self.api = tfim
        self.assertTrue(hasattr(tfim, 'EvolutionResult'), 'EvolutionResult is required')
        self.assertTrue(hasattr(tfim, 'evolve_static'), 'evolve_static is required')
        self.assertTrue(hasattr(tfim, 'tfim_observables'), 'tfim_observables is required')
        self.assertTrue(hasattr(tfim, 'unitary_from_hermitian'), 'spectral propagator is required')

    def test_one_spin_free_precession_matches_cosine_reference(self):
        times = np.linspace(0, 2, 17)
        measured = []
        for t in times:
            U = self.api.unitary_from_hermitian(-0.8 * PAULI['x'], t)
            psi = U @ np.array([1, 0], complex)
            measured.append(np.vdot(psi, PAULI['z'] @ psi).real)
            np.testing.assert_allclose(U.conj().T @ U, I, atol=1e-12, rtol=0)
        np.testing.assert_allclose(measured, np.cos(1.6 * times), atol=1e-12, rtol=0)

    def test_two_spin_analytic_independent_precession_and_final_state(self):
        h, t = 0.3, 1.7
        ket = np.array([1, 0, 0, 0], complex)
        single = np.array([np.cos(h*t), 1j*np.sin(h*t)])
        result = self.api.evolve_static(ket, reference_hamiltonian(2, 0, h), [0, t], [1])
        self.assertIsInstance(result, self.api.EvolutionResult)
        self.assertEqual(result.status, 'success')
        self.assertIsNone(result.error)
        np.testing.assert_allclose(result.final_state, np.kron(single, single), atol=1e-12, rtol=0)
        self.assertEqual(result.final_state.ndim, 1)
        self.assertEqual(set(result.snapshots), {1})
        np.testing.assert_allclose(result.observables['mean_sigma_z'], [1, np.cos(2*h*t)], atol=1e-12)
        result.snapshots[1][0] = 99
        self.assertNotEqual(result.final_state[0], 99)
        np.testing.assert_array_equal(ket, [1, 0, 0, 0])

    def test_interacting_two_spin_analytic_spectral_projectors(self):
        J, h, t = 0.7, 0.3, 0.8
        H = reference_hamiltonian(2, J, h)
        roots = [-np.sqrt(J*J+4*h*h), -J, J, np.sqrt(J*J+4*h*h)]
        expected = np.zeros((4,4), complex)
        for value in roots:
            projector = np.eye(4, dtype=complex)
            for other in roots:
                if value != other:
                    projector = projector @ (H-other*np.eye(4))/(value-other)
            expected += np.exp(-1j*value*t)*projector
        np.testing.assert_allclose(self.api.unitary_from_hermitian(H, t), expected, atol=1e-12, rtol=0)

    def test_mixed_state_invariants_energy_and_requested_snapshots(self):
        rho = np.diag([0.6, 0.3, 0.1, 0]).astype(complex)
        H = reference_hamiltonian(2, 0.7, -0.3)
        times = np.linspace(0, 5, 13)
        result = self.api.evolve_static(rho, H, times, [0, 5, 12])
        self.assertEqual(set(result.snapshots), {0, 5, 12})
        self.assertEqual(result.final_state.ndim, 2)
        for index, state in result.snapshots.items():
            U = self.api.unitary_from_hermitian(H, times[index])
            np.testing.assert_allclose(state, U @ rho @ U.conj().T, atol=1e-12, rtol=0)
            np.testing.assert_allclose(state, state.conj().T, atol=1e-12, rtol=0)
            self.assertAlmostEqual(np.trace(state).real, 1, places=12)
            self.assertGreaterEqual(np.linalg.eigvalsh(state).min(), -1e-12)
        np.testing.assert_allclose(result.observables['energy_over_hbar'], np.trace(rho @ H).real, atol=1e-12, rtol=0)
        self.assertLess(result.diagnostics['unitary_defect'], 1e-12)
        self.assertLess(result.diagnostics['trace_error'], 1e-12)
        self.assertLess(result.diagnostics['hermiticity_error'], 1e-12)
        self.assertGreaterEqual(result.diagnostics['minimum_eigenvalue'], -1e-12)
        self.assertLess(result.diagnostics['energy_drift_over_hbar'], 1e-12)
        self.assertGreaterEqual(result.diagnostics['memory_estimate_bytes'], 3*rho.nbytes)
        np.testing.assert_array_equal(rho, np.diag([0.6, 0.3, 0.1, 0]))

    def test_ket_norm_energy_and_no_implicit_snapshots(self):
        ket = np.array([1, 1j, 2, -1], complex) / np.sqrt(7)
        H = reference_hamiltonian(2, 0.7, 0.3)
        result = self.api.evolve_static(ket, H, [0.2, 0.5, 1.0])
        self.assertEqual(result.snapshots, {})
        self.assertLess(result.diagnostics['norm_error'], 1e-12)
        np.testing.assert_allclose(result.observables['energy_over_hbar'], np.vdot(ket, H @ ket).real, atol=1e-12)
        np.testing.assert_allclose(result.final_state, self.api.unitary_from_hermitian(H, 1) @ ket, atol=1e-12)

    def test_pauli_observables_sites_order_and_optional_energy(self):
        plus_y = np.array([1, 1j])/np.sqrt(2)
        ket = np.kron(np.kron([1, 0], plus_y), [0, 1])
        H = reference_hamiltonian(3, 0.7, 0.3)
        result = self.api.tfim_observables(ket, 3, [2, 0], H_over_hbar=H)
        np.testing.assert_allclose(result['sigma_z'], [-1, 1], atol=1e-12)
        np.testing.assert_allclose(result['sigma_x'], [0, 0], atol=1e-12)
        np.testing.assert_allclose(result['sigma_y'], [0, 0], atol=1e-12)
        self.assertAlmostEqual(result['mean_sigma_z'], 0)
        np.testing.assert_allclose(result['nearest_neighbor_zz'], [0, 0], atol=1e-12)
        self.assertAlmostEqual(result['energy_over_hbar'], np.vdot(ket, H @ ket).real)
        full = self.api.tfim_observables(np.outer(ket, ket.conj()), 3)
        np.testing.assert_allclose(full['sigma_y'], [0, 1, 0], atol=1e-12)
        self.assertNotIn('energy_over_hbar', full)
        self.assertEqual(self.api.tfim_observables(ket, 3, [])['sigma_z'].shape, (0,))

    def test_all_supported_register_sizes(self):
        for n in range(2, 7):
            ket = np.eye(1, 2**n, dtype=complex)[0]
            result = self.api.evolve_static(ket, np.zeros((2**n, 2**n)), [0])
            np.testing.assert_array_equal(result.final_state, ket)
            self.assertEqual(result.observables['sigma_x'].shape, (1, n))
            self.assertEqual(result.observables['nearest_neighbor_zz'].shape, (1, n-1))

    def test_times_must_be_nonempty_finite_sorted_nonnegative_real_sequence(self):
        ket = np.array([1,0,0,0], complex)
        for times in ([], [0, np.nan], [np.inf], [-0.1], [1,0], [[0]], ['0'], [True], [1j], '0'):
            with self.subTest(times=times), self.assertRaises((TypeError, ValueError)):
                self.api.evolve_static(ket, np.eye(4), times)
        result = self.api.evolve_static(ket, np.eye(4), [0, 0, 1])
        np.testing.assert_array_equal(result.times_s, [0,0,1])

    def test_snapshot_indices_are_valid_unique_integers(self):
        for indexes in ([-1], [2], [0,0], [True], [0.0], '0'):
            with self.subTest(indexes=indexes), self.assertRaises((TypeError, ValueError)):
                self.api.evolve_static([1,0,0,0], np.eye(4), [0,1], indexes)

    def test_rejects_invalid_state_register_or_generator(self):
        ket = np.array([1,0,0,0], complex)
        for state in ([1,0], [1]*4, np.diag([1.1,-0.1,0,0]), np.eye(4), [np.nan,0,0,0]):
            with self.subTest(state=state), self.assertRaises((TypeError, ValueError)):
                self.api.evolve_static(state, np.eye(len(state)), [0])
        for H in (np.eye(2), np.ones((4,3)), np.full((4,4), np.nan), np.triu(np.ones((4,4)))):
            with self.subTest(H=H), self.assertRaises((TypeError, ValueError)):
                self.api.evolve_static(ket, H, [0])
        with self.assertRaises(ValueError):
            self.api.tfim_observables(ket, 3)
        with self.assertRaises(ValueError):
            self.api.tfim_observables(ket, 2, [0,0])

    def test_unitary_rejects_invalid_generator_or_elapsed_time(self):
        for H in ([], [1,2], np.ones((2,3)), [[0,1],[0,0]], [[np.inf,0],[0,0]]):
            with self.subTest(H=H), self.assertRaises((TypeError, ValueError)):
                self.api.unitary_from_hermitian(H, 1)
        for elapsed in (np.nan, np.inf, True, '1', 1j):
            with self.subTest(elapsed=elapsed), self.assertRaises((TypeError, ValueError)):
                self.api.unitary_from_hermitian(I, elapsed)
        U = self.api.unitary_from_hermitian(PAULI['x'], -0.4)
        np.testing.assert_allclose(U, self.api.unitary_from_hermitian(PAULI['x'], 0.4).conj().T, atol=1e-12)


    def test_observables_match_independent_kronecker_expectations(self):
        ket = np.array([1, 2j, 3-1j, -2, 1j, 0.5, -1j, 2+1j], complex)
        ket /= np.linalg.norm(ket)
        for state in (ket, 0.7*np.outer(ket, ket.conj()) + 0.3*np.eye(8)/8):
            result = self.api.tfim_observables(state, 3)
            def expected(operator):
                return (np.vdot(state, operator @ state) if state.ndim == 1 else np.trace(state @ operator)).real
            for component in PAULI:
                reference = [expected(kron_operator(3, {site: PAULI[component]})) for site in range(3)]
                np.testing.assert_allclose(result['sigma_' + component], reference, atol=1e-12)
            reference_zz = [expected(kron_operator(3, {i: PAULI['z'], i+1: PAULI['z']})) for i in range(2)]
            np.testing.assert_allclose(result['nearest_neighbor_zz'], reference_zz, atol=1e-12)
            self.assertAlmostEqual(result['mean_sigma_z'], np.mean(result['sigma_z']))

    def test_unrepresentable_phases_raise_without_runtime_warnings(self):
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter('always')
            with self.assertRaisesRegex(ValueError, 'spectral phases'):
                self.api.unitary_from_hermitian(1e308*I, 1e308)
            with self.assertRaisesRegex(ValueError, 'spectral phases'):
                self.api.evolve_static([1,0,0,0], 1e308*np.eye(4), [1e308])
        self.assertEqual(emitted, [])


    def test_memory_estimate_covers_peak_phase_generation(self):
        self.assertTrue(hasattr(self.api, '_estimate_static_memory_bytes'),
                        'memory estimate must expose the storage calculation')
        n_spins, samples = 6, 10000
        ket = np.eye(1, 2**n_spins, dtype=complex)[0]
        times = np.linspace(0, 1, samples)
        values = np.linspace(-1, 1, 2**n_spins)
        tracemalloc.start()
        try:
            phases = self.api._spectral_phases(values, times)
            _, phase_peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        estimate = self.api._estimate_static_memory_bytes(ket, n_spins, samples, 0)
        self.assertGreaterEqual(estimate, phase_peak)
        self.assertGreaterEqual(estimate, 2*phases.nbytes)




class TFIMDrivenEvolutionTests(unittest.TestCase):
    def setUp(self):
        from quantum_lab import tfim
        self.api = tfim
        self.assertTrue(hasattr(tfim, 'FieldSchedule'), 'serializable FieldSchedule is required')
        self.assertTrue(hasattr(tfim, 'evolve_tfim'), 'adaptive evolve_tfim is required')
        self.F = tfim.FieldSchedule
        self.ket = np.array([1, 0, 0, 0], complex)

    @staticmethod
    def reference(ket, J, field, end, local=None, steps=12000):
        # Independent fixed-step RK4 of the Schrodinger equation, with explicit
        # Kronecker matrices; no production propagator or schedule evaluation.
        zz = np.kron(PAULI['z'], PAULI['z'])
        xs = [np.kron(PAULI['x'], I), np.kron(I, PAULI['x'])]
        def rhs(t, state):
            H = -J*zz - field(t)*(xs[0]+xs[1])
            if local is not None:
                H -= local(t)*xs[1]
            return -1j*(H @ state)
        state, dt = ket.copy(), end/steps
        for i in range(steps):
            t = i*dt
            a = rhs(t, state)
            b = rhs(t+dt/2, state+dt*a/2)
            c = rhs(t+dt/2, state+dt*b/2)
            d = rhs(t+dt, state+dt*c)
            state += dt*(a+2*b+2*c+d)/6
        return state

    def test_schedules_are_serializable_validated_and_right_continuous(self):
        import json
        schedules = [self.F.constant(-0.2), self.F.piecewise_constant([0, .3, 1], [.2, -.4]),
                     self.F.sinusoidal(.1, .3, 2, .2), self.F.gaussian(.4, .5, .1, -.2)]
        for schedule in schedules:
            rebuilt = self.F.from_dict(json.loads(json.dumps(schedule.to_dict())))
            self.assertEqual(rebuilt, schedule)
            self.assertEqual(rebuilt.value_at(.3), schedule.value_at(.3))
        piece = schedules[1]
        self.assertEqual(piece.value_at(.3), -.4)
        self.assertEqual(piece.value_at(1), -.4)
        for t in (-1, 1.01, np.nan, np.inf):
            with self.assertRaises(ValueError):
                piece.value_at(t)
        for edges, values in (([0, .5, .5], [1, 2]), ([0, 1], []), ([0, np.inf], [1])):
            with self.assertRaises(ValueError):
                self.F.piecewise_constant(edges, values)
        for width in (0, -1, np.inf):
            with self.assertRaises(ValueError):
                self.F.gaussian(1, .5, width)
        for invalid in (np.nan, np.inf, True, '1', 1j):
            with self.assertRaises((TypeError, ValueError)):
                self.F.constant(invalid)
        with self.assertRaises(ValueError):
            self.F.from_dict({'kind': 'callable'})

    def test_constant_matches_static_for_kets_and_density_matrices(self):
        for state in (self.ket, np.diag([.6, .3, .1, 0]).astype(complex)):
            H = reference_hamiltonian(2, .7, .3)
            expected = self.api.evolve_static(state, H, [.2, .2, .7], [1])
            actual = self.api.evolve_tfim(state, 2, .7, self.F.constant(.3), [.2, .2, .7], save_states_at=[1])
            self.assertEqual(actual.status, 'success')
            self.assertEqual(actual.diagnostics['method'], 'spectral')
            np.testing.assert_allclose(actual.final_state, expected.final_state, atol=1e-12, rtol=0)
            self.assertEqual(set(actual.snapshots), {1})
            for name in expected.observables:
                np.testing.assert_allclose(actual.observables[name], expected.observables[name], atol=1e-12, rtol=0)

    def test_receiver_only_active_sites_leave_sender_marginal_unchanged(self):
        from quantum_lab.multispin import partial_trace_subsystems

        rng = np.random.default_rng(204)
        ket = rng.normal(size=16) + 1j * rng.normal(size=16)
        ket /= np.linalg.norm(ket)
        result = self.api.evolve_tfim(ket, 4, .6, self.F.constant(.8), [0, .4], active_sites=[1, 2, 3],
                                      save_states_at=[1])
        self.assertEqual(result.status, "success")
        self.assertEqual(result.diagnostics["active_sites"], [1, 2, 3])
        final = result.snapshots[1]
        np.testing.assert_allclose(partial_trace_subsystems(final, [0]), partial_trace_subsystems(ket, [0]),
                                   atol=1e-12, rtol=0)
        self.assertGreater(np.linalg.norm(final - ket), 1e-5)

    def test_restricted_hamiltonian_keeps_only_physical_neighbor_bonds(self):
        from quantum_lab.multispin import embed_operator

        sigma_z = np.diag([1, -1])
        sigma_x = np.array([[0, 1], [1, 0]])
        zz = np.kron(sigma_z, sigma_z)
        expected = -.7 * embed_operator(zz, [1, 2], 4)
        expected -= .4 * (embed_operator(sigma_x, [1], 4) + embed_operator(sigma_x, [2], 4))
        actual = self.api.open_tfim_hamiltonian(4, .7, .4, sites=[1, 2])
        np.testing.assert_allclose(actual, expected, atol=0, rtol=0)
        with self.assertRaises((TypeError, ValueError)):
            self.api.open_tfim_hamiltonian(4, .7, .4, sites=[1, 1])

    def test_commuting_sinusoidal_field_matches_integrated_phase(self):
        end = 1.3
        result = self.api.evolve_tfim(self.ket, 2, 0, self.F.sinusoidal(0, .3, 2), [0, end], rtol=1e-11, atol=1e-14)
        angle = .3/2*(1-np.cos(2*end))
        single = np.array([np.cos(angle), 1j*np.sin(angle)])
        self.assertEqual(result.status, 'success')
        np.testing.assert_allclose(result.final_state, np.kron(single, single), atol=2e-8, rtol=0)
        np.testing.assert_allclose(result.observables['sigma_z'][-1], [np.cos(2*angle)]*2, atol=2e-8, rtol=0)

    def test_piecewise_segments_use_chronological_order_and_all_local_edges(self):
        uniform = self.F.piecewise_constant([0, .4, .9], [0, .5])
        local = self.F.piecewise_constant([0, .2, .6, .9], [.3, -.2, .1])
        result = self.api.evolve_tfim(self.ket, 2, .7, uniform, [0, .9], local_controls={1: local})
        expected, reverse = self.ket.copy(), self.ket.copy()
        intervals = [(0, .2, 0, .3), (.2, .4, 0, -.2), (.4, .6, .5, -.2), (.6, .9, .5, .1)]
        unitaries = []
        for a, b, h, delta in intervals:
            H = reference_hamiltonian(2, .7, h)-delta*np.kron(I, PAULI['x'])
            vals, vecs = np.linalg.eigh(H)
            unitaries.append((vecs*np.exp(-1j*(b-a)*vals)) @ vecs.conj().T)
        for U in unitaries:
            expected = U @ expected
        for U in reversed(unitaries):
            reverse = U @ reverse
        self.assertEqual(result.status, 'success')
        np.testing.assert_allclose(result.final_state, expected, atol=1e-12, rtol=0)
        self.assertGreater(np.linalg.norm(expected-reverse), .01)
        self.assertEqual(result.diagnostics['boundary_times_s'], [.2, .4, .6, .9])
        self.assertEqual(result.diagnostics['accepted_steps'], 4)

    def test_noncommuting_smooth_ordering_matches_independent_rk4(self):
        end = 1.1
        field = lambda t: .2+.6*np.sin(2.3*t+.4)
        local = lambda t: .3*np.exp(-.5*((t-.65)/.19)**2)
        expected = self.reference(self.ket, .8, field, end, local)
        # Reverse the time-dependence independently to detect wrong ordering.
        reversed_state = self.reference(self.ket, .8, lambda t: field(end-t), end, lambda t: local(end-t))
        result = self.api.evolve_tfim(self.ket, 2, .8, self.F.sinusoidal(.2, .6, 2.3, .4), [0, end],
                                    local_controls={1: self.F.gaussian(.3, .65, .19)}, rtol=1e-10, atol=1e-13)
        self.assertEqual(result.status, 'success')
        np.testing.assert_allclose(result.final_state, expected, atol=3e-7, rtol=0)
        # Ordering separation is a physical signal, with a fixed floor above solver noise.
        self.assertFalse(np.allclose(expected, reversed_state, atol=1e-3, rtol=0))
        self.assertGreater(np.linalg.norm(expected-reversed_state), 1e-3)
        self.assertEqual(result.diagnostics['global_comparison']['status'], 'not_performed')

    def test_gaussian_tolerance_convergence_is_independent_of_unitarity(self):
        field = lambda t: .1+.7*np.exp(-.5*((t-.6)/.16)**2)
        reference = self.reference(self.ket, .8, field, 1.3)
        results = [self.api.evolve_tfim(self.ket, 2, .8, self.F.gaussian(.7, .6, .16, .1), [0, .4, .9, 1.3],
                                      rtol=rtol, atol=rtol/1000, save_states_at=[1,2,3]) for rtol in (1e-6, 1e-8, 1e-10)]
        errors = [float(np.linalg.norm(r.final_state-reference)) for r in results]
        differences = [float(np.linalg.norm(results[i+1].final_state-results[i].final_state)) for i in range(2)]
        print('Gaussian independent convergence errors:', errors, 'successive differences:', differences)
        self.assertLess(errors[1], errors[0]/5)
        self.assertLess(errors[2], errors[1]/5)
        self.assertLess(differences[1], differences[0]/5)
        trajectory_differences = [max(float(np.linalg.norm(results[i+1].snapshots[k]-results[i].snapshots[k])) for k in (1,2,3)) for i in range(2)]
        observable_differences = [float(np.max(np.abs(results[i+1].observables['sigma_z']-results[i].observables['sigma_z']))) for i in range(2)]
        print('Gaussian trajectory differences:', trajectory_differences, 'observable differences:', observable_differences)
        self.assertLess(trajectory_differences[1], trajectory_differences[0]/5)
        self.assertLess(observable_differences[1], observable_differences[0]/5)
        self.assertLess(errors[2], 3e-7)
        self.assertGreater(errors[0], 1e-6)
        for result in results:
            self.assertEqual(result.status, 'success')
            self.assertLess(result.diagnostics['norm_error'], 2e-11)
            self.assertLess(result.diagnostics['unitary_defect'], 2e-11)
            self.assertLessEqual(result.diagnostics['maximum_scaled_local_error'], 1)
            self.assertEqual(result.diagnostics['attempted_steps'], result.diagnostics['accepted_steps']+result.diagnostics['rejected_steps'])

    def test_gaussian_commuting_phase_is_analytic(self):
        import math
        amp, center, width, end = .8, .6, .15, 1.2
        angle = amp*width*np.sqrt(np.pi/2)*(math.erf((end-center)/(np.sqrt(2)*width))-math.erf(-center/(np.sqrt(2)*width)))
        single = np.array([np.cos(angle), 1j*np.sin(angle)])
        result = self.api.evolve_tfim(self.ket, 2, 0, self.F.gaussian(amp, center, width), [end], rtol=1e-10, atol=1e-13)
        np.testing.assert_allclose(result.final_state, np.kron(single, single), atol=2e-7, rtol=0)

    def test_density_physicality_and_mixed_smooth_jump_controls(self):
        rho = .6*np.outer(self.ket, self.ket.conj()) + .4*np.eye(4)/4
        result = self.api.evolve_tfim(rho, 2, .7, self.F.sinusoidal(.1, .3, 2), [0, .2, .7],
                                    local_controls={0: self.F.piecewise_constant([0, .13, .51, .7], [0, .5, -.2])},
                                    save_states_at=[0, 2])
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.diagnostics['boundary_times_s'], [.13, .51, .7])
        self.assertEqual(set(result.snapshots), {0, 2})
        self.assertLess(result.diagnostics['trace_error'], 2e-11)
        self.assertLess(result.diagnostics['hermiticity_error'], 2e-11)
        self.assertGreaterEqual(result.diagnostics['minimum_eigenvalue'], -1e-12)
        for state in result.snapshots.values():
            self.assertAlmostEqual(np.trace(state).real, 1, places=11)
            self.assertGreaterEqual(np.linalg.eigvalsh(state).min(), -1e-12)
        self.assertEqual(set(result.observables), {'sigma_x','sigma_y','sigma_z','mean_sigma_z','nearest_neighbor_zz','energy_over_hbar'})

    def test_attempt_limit_returns_partial_failure_with_final_time(self):
        result = self.api.evolve_tfim(self.ket, 2, 1, self.F.sinusoidal(.1, 1, 3), [0, .1, 1], max_steps=1)
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.error, 'max_steps')
        self.assertEqual(result.diagnostics['attempted_steps'], 1)
        self.assertLess(result.diagnostics['final_time_s'], 1)
        self.assertEqual(len(result.times_s), len(result.observables['mean_sigma_z']))
        self.assertEqual(result.snapshots, {})

    def test_cancellation_is_distinct_and_checked_between_steps(self):
        calls = []
        def cancelled():
            calls.append(1)
            return len(calls) >= 3
        result = self.api.evolve_tfim(self.ket, 2, .7, self.F.piecewise_constant([0,.2,.4,.6], [0,.1,.2]), [0,.6], cancel_check=cancelled)
        self.assertEqual(result.status, 'cancelled')
        self.assertEqual(result.error, 'cancelled')
        self.assertEqual(result.diagnostics['final_time_s'], .4)
        self.assertEqual(result.diagnostics['attempted_steps'], 2)

    def test_nonfinite_hamiltonian_is_a_failed_result_without_warnings(self):
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter('always')
            result = self.api.evolve_tfim(np.eye(1,64,dtype=complex)[0], 6, 1e308, self.F.constant(0), [0, 1])
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.error, 'nonfinite_hamiltonian')
        self.assertEqual(result.diagnostics['final_time_s'], 0)
        self.assertEqual(emitted, [])

    def test_floating_point_minimum_step_and_tolerance_exhaustion(self):
        small = self.api.evolve_tfim(self.ket, 2, 0, self.F.sinusoidal(0,.3,2), [0,np.nextafter(0.,1.)])
        self.assertEqual(small.status, 'failed')
        self.assertEqual(small.error, 'minimum_step')
        exhausted = self.api.evolve_tfim(self.ket, 2, 1, self.F.sinusoidal(0,.3,2), [0,1], rtol=0, atol=1e-30)
        self.assertEqual(exhausted.status, 'failed')
        self.assertEqual(exhausted.error, 'tolerance_exhausted')

    def test_fine_half_steps_and_local_estimate_match_independent_construction(self):
        # One accepted trial followed by the attempt limit exposes the accepted
        # fine state without adding solver-only hooks or storing internal steps.
        J, end, dt = .7, 1., 1./16
        field = lambda t: .2+.5*np.sin(.4*t+.1)
        def independent_unitary(t, duration):
            H = reference_hamiltonian(2, J, field(t))
            vals, vecs = np.linalg.eigh(H)
            return (vecs*np.exp(-1j*duration*vals)) @ vecs.conj().T
        coarse = independent_unitary(dt/2, dt) @ self.ket
        fine = independent_unitary(3*dt/4, dt/2) @ independent_unitary(dt/4, dt/2) @ self.ket
        result = self.api.evolve_tfim(self.ket, 2, J, self.F.sinusoidal(.2,.5,.4,.1), [0,end],
                                    rtol=1e-2, atol=1e-5, max_steps=1)
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.error, 'max_steps')
        self.assertEqual(result.diagnostics['accepted_steps'], 1)
        self.assertEqual(result.diagnostics['final_time_s'], dt)
        np.testing.assert_allclose(result.final_state, fine, atol=1e-14, rtol=0)
        error = np.linalg.norm(fine-coarse)/3
        self.assertAlmostEqual(result.diagnostics['maximum_local_error'], error, places=15)
        self.assertAlmostEqual(result.diagnostics['maximum_scaled_local_error'], error/(1e-5+1e-2*max(np.linalg.norm(fine),np.linalg.norm(coarse))), places=13)

    def test_rk4_reference_is_stable_under_independent_step_halving(self):
        field = lambda t: .1+.7*np.exp(-.5*((t-.6)/.16)**2)
        coarse = self.reference(self.ket, .8, field, 1.3, steps=6000)
        fine = self.reference(self.ket, .8, field, 1.3, steps=12000)
        difference = float(np.linalg.norm(fine-coarse))
        print('Independent RK4 step-halving difference:', difference)
        self.assertLess(difference, 2e-11)

    def test_constant_local_controls_match_independent_spins_for_every_size(self):
        for n in range(2,7):
            ket = np.eye(1, 2**n, dtype=complex)[0]
            result = self.api.evolve_tfim(ket, n, 0, self.F.constant(.3), [0,.4],
                                        local_controls={n-1:self.F.constant(-.7)})
            expected = np.array([1], complex)
            for site in range(n):
                angle = (.3+(-.7 if site==n-1 else 0))*.4
                expected = np.kron(expected, [np.cos(angle),1j*np.sin(angle)])
            self.assertEqual(result.status, 'success')
            np.testing.assert_allclose(result.final_state, expected, atol=2e-12, rtol=0)
            self.assertLess(result.diagnostics['norm_error'], 2e-12)
            self.assertLess(result.diagnostics['unitary_defect'], 2e-12)


    def test_driven_memory_estimate_includes_midpoint_matrix_workspaces(self):
        n = 2
        result = self.api.evolve_tfim(self.ket, n, .7, self.F.sinusoidal(0,.3,2), [0,.01])
        # Three sampled generators, coarse/early/late/fine exponentials,
        # cumulative propagator, identities, eigensolver temporaries and the
        # cached local Pauli operators coexist with observable operators.
        minimum_matrix_storage = (4*n+n+24)*(2**n)**2*16
        self.assertGreaterEqual(result.diagnostics['memory_estimate_bytes'], minimum_matrix_storage)

    def test_finite_hamiltonian_observable_overflow_has_distinct_failure_reason(self):
        ket = np.full(4, .5, complex)
        H = self.api.open_tfim_hamiltonian(2, 0, 1e308)
        self.assertTrue(np.all(np.isfinite(H)))
        for state in (ket, np.outer(ket, ket.conj())):
            with self.subTest(representation=state.ndim), warnings.catch_warnings(record=True) as emitted:
                warnings.simplefilter('always')
                result = self.api.evolve_tfim(state, 2, 0, self.F.constant(1e308), [0])
                self.assertEqual(result.status, 'failed')
                self.assertEqual(result.error, 'nonfinite_observable')
                self.assertEqual(result.diagnostics['final_time_s'], 0)
                self.assertEqual(result.diagnostics['attempted_steps'], 0)
                self.assertEqual(len(result.times_s), 0)
                self.assertEqual(result.snapshots, {})
                np.testing.assert_array_equal(result.final_state, state)
                self.assertEqual(emitted, [])

    def test_invalid_run_configuration_raises_before_propagation(self):
        for kwargs in ({'rtol':-1}, {'atol':-1}, {'rtol':0,'atol':0}, {'max_steps':0}, {'max_steps':True}, {'max_steps':1.5},
                       {'local_controls':{2:self.F.constant(0)}}, {'local_controls':{True:self.F.constant(0)}},
                       {'local_controls':{0:lambda t: 0}}, {'cancel_check':5}, {'save_states_at':[1,1]}):
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                self.api.evolve_tfim(self.ket, 2, .7, self.F.constant(.3), [0,1], **kwargs)
        for times in ([], [-1], [1,0], [np.nan], [True], ['0']):
            with self.subTest(times=times), self.assertRaises((TypeError, ValueError)):
                self.api.evolve_tfim(self.ket, 2, .7, self.F.constant(.3), times)
        with self.assertRaises(ValueError):
            self.api.evolve_tfim(self.ket, 3, .7, self.F.constant(0), [0,1])
        with self.assertRaises(ValueError):
            self.api.evolve_tfim(self.ket, 2, .7, self.F.piecewise_constant([.2,1],[0]), [1])
        with self.assertRaises(ValueError):
            self.api.evolve_tfim(self.ket, 2, .7, self.F.constant(0), [1], local_controls={0:self.F.piecewise_constant([0,.5],[0])})

    def test_local_control_is_additive_on_selected_site_only(self):
        end, h, delta = .8, .3, .5
        result = self.api.evolve_tfim(self.ket, 2, 0, self.F.constant(h), [end], local_controls={1:self.F.constant(delta)})
        a = np.array([np.cos(h*end), 1j*np.sin(h*end)])
        b = np.array([np.cos((h+delta)*end), 1j*np.sin((h+delta)*end)])
        np.testing.assert_allclose(result.final_state, np.kron(a,b), atol=1e-12, rtol=0)


if __name__ == "__main__":
    unittest.main()
