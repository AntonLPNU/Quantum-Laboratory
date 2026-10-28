"""Independent big-endian basis-sum references for ordered spin subsystems."""
from __future__ import annotations

import unittest
import numpy as np

from quantum_lab import multispin

from quantum_lab.multispin import (
    apply_subsystem_unitary, embed_operator, expectation_value,
    partial_trace_subsystems, reduced_density_matrix, tensor_product_state,
)
from quantum_lab.states import bell_state, partial_trace


def reference_trace(rho, keep):
    n = rho.shape[0].bit_length() - 1
    result = np.zeros((2 ** len(keep),) * 2, complex)
    for row in range(len(rho)):
        rb = [(row >> (n - 1 - site)) & 1 for site in range(n)]
        for col in range(len(rho)):
            cb = [(col >> (n - 1 - site)) & 1 for site in range(n)]
            if all(rb[site] == cb[site] for site in range(n) if site not in keep):
                r = sum(rb[site] << (len(keep) - 1 - j) for j, site in enumerate(keep))
                c = sum(cb[site] << (len(keep) - 1 - j) for j, site in enumerate(keep))
                result[r, c] += rho[row, col]
    return result


def reference_embedding(operator, targets, n):
    # Independent column action: replace selected source bits for every local output.
    result = np.zeros((2 ** n,) * 2, complex)
    for source in range(2 ** n):
        bits = list(format(source, f"0{n}b"))
        local_source = int("".join(bits[site] for site in targets), 2) if targets else 0
        for local_output in range(len(operator)):
            output = bits.copy()
            for site, bit in zip(targets, format(local_output, f"0{len(targets)}b") if targets else ""):
                output[site] = bit
            result[int("".join(output), 2), source] = operator[local_output, local_source]
    return result


class MultispinTests(unittest.TestCase):
    def test_product_state_uses_leftmost_spin_zero(self):
        zero, one = np.array([1, 0]), np.array([0, 1])
        ket = tensor_product_state([zero, one, zero, one])
        expected = np.zeros(16, complex)
        expected[5] = 1
        np.testing.assert_array_equal(ket, expected)
        reduced = partial_trace_subsystems(ket, [3, 1])
        np.testing.assert_array_equal(reduced, np.diag([0, 0, 0, 1]))

    def test_complex_product_state_matches_kronecker_order(self):
        a = np.array([1, 2j]) / np.sqrt(5)
        b = np.array([3, 1j]) / np.sqrt(10)
        np.testing.assert_allclose(tensor_product_state([a, b]), np.kron(a, b), atol=1e-12, rtol=0)

    def test_exact_nonsymmetric_complex_reduction_preserves_31_order(self):
        ket = np.zeros(16, complex)
        ket[[0, 1, 4, 5]] = np.array([1, 2j, 3, 4j]) / np.sqrt(30)
        # Global q1,q3 amplitudes [1,2j,3,4j] reorder to q3,q1 [1,3,2j,4j].
        kept = np.array([1, 3, 2j, 4j]) / np.sqrt(30)
        expected = np.outer(kept, kept.conj())
        rho = np.outer(ket, ket.conj())
        np.testing.assert_allclose(partial_trace_subsystems(rho, [3, 1]), expected, atol=1e-12, rtol=0)
        np.testing.assert_allclose(reference_trace(rho, [3, 1]), expected, atol=1e-12, rtol=0)

    def test_random_complex_reductions_match_basis_sums_for_all_sizes(self):
        rng = np.random.default_rng(17)
        for n in range(2, 7):
            ket = rng.normal(size=2 ** n) + 1j * rng.normal(size=2 ** n)
            ket /= np.linalg.norm(ket)
            factor = rng.normal(size=(2 ** n, 2 ** n)) + 1j * rng.normal(size=(2 ** n, 2 ** n))
            mixed = factor @ factor.conj().T
            mixed /= np.trace(mixed)
            for rho in (np.outer(ket, ket.conj()), mixed):
                for keep in ([], [1, 0], [n - 1, 1] if n > 2 else [1], list(reversed(range(n)))):
                    with self.subTest(n=n, keep=keep):
                        np.testing.assert_allclose(partial_trace_subsystems(rho, keep), reference_trace(rho, keep), atol=1e-12, rtol=0)
            np.testing.assert_allclose(partial_trace_subsystems(ket, [1, 0]), reference_trace(np.outer(ket, ket.conj()), [1, 0]), atol=1e-12, rtol=0)

    def test_empty_keep_preserves_trace_of_unnormalized_operator(self):
        rho = np.arange(16).reshape(4, 4) + 2j * np.eye(4)
        actual = partial_trace_subsystems(rho, [])
        self.assertEqual(actual.shape, (1, 1))
        np.testing.assert_allclose(actual, [[np.trace(rho)]], atol=1e-12, rtol=0)

    def test_partial_trace_agrees_with_legacy_two_spin_api(self):
        rho = bell_state()
        for keep in (0, 1):
            np.testing.assert_allclose(partial_trace_subsystems(rho, [keep]), partial_trace(rho, keep))

    def test_invalid_kept_indices_and_unordered_containers_are_rejected(self):
        for keep in ([0, 0], [-1], [2], [True], [False], [0.0], ["0"], {0, 1}, "01", 0):
            with self.subTest(keep=keep), self.assertRaises((ValueError, TypeError)):
                partial_trace_subsystems(np.eye(4), keep)
        np.testing.assert_allclose(partial_trace_subsystems(np.eye(4), np.array([np.int64(1)])), 2 * np.eye(2))

    def test_invalid_register_shapes_and_nonfinite_entries_are_rejected(self):
        for state in (np.ones(2), np.ones(3), np.ones(128), np.ones((4, 3)), np.ones((2, 2, 2)), np.full(4, np.nan), np.full((4, 4), np.inf)):
            with self.subTest(shape=state.shape), self.assertRaises(ValueError):
                partial_trace_subsystems(state, [])
        with self.assertRaises(ValueError):
            partial_trace_subsystems(np.ones(4), [])

    def test_product_state_validates_local_kets_and_register_bounds(self):
        zero = np.array([1, 0])
        for kets in ([], [zero], [zero] * 7, [zero, [1, 1]], [zero, [1, 0, 0]], [zero, [np.nan, 0]], [zero, [[1], [0]]], {0, 1}):
            with self.subTest(kets=kets), self.assertRaises((ValueError, TypeError)):
                tensor_product_state(kets)
        for n in range(2, 7):
            self.assertEqual(tensor_product_state([zero] * n).shape, (2 ** n,))

    def test_embedding_matches_single_spin_kronecker_products(self):
        x = np.array([[0, 1], [1, 0]])
        np.testing.assert_array_equal(embed_operator(x, [0], 3), np.kron(np.kron(x, np.eye(2)), np.eye(2)))
        np.testing.assert_array_equal(embed_operator(x, [2], 3), np.kron(np.kron(np.eye(2), np.eye(2)), x))

    def test_ordered_arbitrary_embedding_matches_independent_column_action(self):
        rng = np.random.default_rng(29)
        for n, targets in ((2, [1, 0]), (4, [3, 1]), (5, [4, 0, 2]), (6, [5, 1])):
            d = 2 ** len(targets)
            operator = rng.normal(size=(d, d)) + 1j * rng.normal(size=(d, d))
            np.testing.assert_allclose(embed_operator(operator, targets, n), reference_embedding(operator, targets, n), atol=1e-12, rtol=0)

    def test_empty_target_operator_is_scalar_identity(self):
        np.testing.assert_array_equal(embed_operator(np.array([[2j]]), [], 3), 2j * np.eye(8))

    def test_embedding_rejects_invalid_operator_targets_and_register_size(self):
        for targets in ([0, 0], [-1], [4], [True], [1.5], {0}, 0):
            with self.subTest(targets=targets), self.assertRaises((ValueError, TypeError)):
                embed_operator(np.eye(2), targets, 4)
        for n in (1, 7, True, 2.0):
            with self.subTest(n=n), self.assertRaises((ValueError, TypeError)):
                embed_operator(np.eye(2), [0], n)
        for operator in (np.eye(3), np.ones((2, 3)), np.ones(2), np.full((2, 2), np.nan)):
            with self.subTest(operator=operator), self.assertRaises(ValueError):
                embed_operator(operator, [0], 3)

    def test_ordered_unitary_on_nonadjacent_targets_preserves_spectators(self):
        rng = np.random.default_rng(42)
        ket = rng.normal(size=16) + 1j * rng.normal(size=16)
        ket /= np.linalg.norm(ket)
        rho = np.outer(ket, ket.conj())
        raw = rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))
        unitary, _ = np.linalg.qr(raw)
        full = reference_embedding(unitary, [3, 1], 4)
        result_ket = apply_subsystem_unitary(ket, unitary, [3, 1])
        result_rho = apply_subsystem_unitary(rho, unitary, [3, 1])
        self.assertEqual(result_ket.shape, ket.shape)
        self.assertEqual(result_rho.shape, rho.shape)
        np.testing.assert_allclose(result_ket, full @ ket, atol=1e-12, rtol=0)
        np.testing.assert_allclose(result_rho, full @ rho @ full.conj().T, atol=1e-12, rtol=0)
        np.testing.assert_allclose(partial_trace_subsystems(result_rho, [2, 0]), partial_trace_subsystems(rho, [2, 0]), atol=1e-12, rtol=0)
        np.testing.assert_allclose(np.outer(result_ket, result_ket.conj()), result_rho, atol=1e-12, rtol=0)

    def test_reduction_and_complex_expectation_use_ordered_targets(self):
        ket = np.array([1, 2j, 3, 4j]) / np.sqrt(30)
        rho = np.outer(ket, ket.conj())
        operator = np.array([[1j, 2, 0, 1], [0, 3, 4j, 0], [0, 0, 1, 0], [2, 0, 0, -1]])
        full = reference_embedding(operator, [1, 0], 2)
        expected = complex(np.vdot(ket, full @ ket))
        for state in (ket, rho):
            np.testing.assert_allclose(reduced_density_matrix(state, [1, 0]), reference_trace(rho, [1, 0]), atol=1e-12, rtol=0)
            self.assertIsInstance(expectation_value(state, operator, [1, 0]), complex)
            self.assertAlmostEqual(expectation_value(state, operator, [1, 0]), expected, places=12)

    def test_physical_state_apis_reject_invalid_density_operators(self):
        for rho in (np.eye(4), np.diag([1.1, -0.1, 0, 0]), np.diag([1, 0, 0, 0]) + np.eye(4, k=1), np.full((4, 4), np.nan)):
            for operation in (lambda: reduced_density_matrix(rho, [0]), lambda: expectation_value(rho, np.eye(2), [0]), lambda: apply_subsystem_unitary(rho, np.eye(2), [0])):
                with self.subTest(rho=rho), self.assertRaises(ValueError):
                    operation()

    def test_unitary_application_rejects_nonunitary_and_invalid_kets(self):
        ket = np.array([1, 0, 0, 0])
        with self.assertRaises(ValueError):
            apply_subsystem_unitary(ket, np.array([[1, 0], [0, 2]]), [0])
        for operation in (lambda: apply_subsystem_unitary(2 * ket, np.eye(2), [0]), lambda: expectation_value(2 * ket, np.eye(2), [0]), lambda: reduced_density_matrix(2 * ket, [0])):
            with self.assertRaises(ValueError):
                operation()

    def test_local_kraus_channel_matches_explicit_cptp_action_and_keeps_spectators(self):
        import quantum_lab.multispin as multispin

        self.assertTrue(hasattr(multispin, "apply_subsystem_kraus"))
        rng = np.random.default_rng(101)
        ket = rng.normal(size=32) + 1j * rng.normal(size=32)
        ket /= np.linalg.norm(ket)
        rho = np.outer(ket, ket.conj())
        phase_flip_probability = 0.23
        kraus = [np.sqrt(1 - phase_flip_probability) * np.eye(2),
                 np.sqrt(phase_flip_probability) * np.array([[1, 0], [0, -1]])]
        actual = multispin.apply_subsystem_kraus(rho, kraus, [3])
        expected = sum(reference_embedding(operator, [3], 5) @ rho @ reference_embedding(operator, [3], 5).conj().T
                       for operator in kraus)
        np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)
        self.assertAlmostEqual(np.trace(actual).real, 1.0, places=12)
        np.testing.assert_allclose(actual, actual.conj().T, atol=1e-12, rtol=0)
        self.assertGreaterEqual(np.linalg.eigvalsh(actual).min(), -1e-12)
        np.testing.assert_allclose(partial_trace_subsystems(actual, [0, 1, 2, 4]),
                                   partial_trace_subsystems(rho, [0, 1, 2, 4]), atol=1e-12, rtol=0)

    def test_local_kraus_channel_converts_ket_and_rejects_invalid_maps(self):
        import quantum_lab.multispin as multispin

        self.assertTrue(hasattr(multispin, "apply_subsystem_kraus"))
        ket = np.zeros(8, dtype=complex)
        ket[0] = 1 / np.sqrt(2)
        ket[7] = 1 / np.sqrt(2)
        projectors = [np.diag([1, 0]), np.diag([0, 1])]
        result = multispin.apply_subsystem_kraus(ket, projectors, [1])
        self.assertEqual(result.shape, (8, 8))
        self.assertAlmostEqual(np.trace(result).real, 1.0, places=12)
        self.assertAlmostEqual(np.linalg.eigvalsh(result).min(), 0.0, places=12)
        for operators, targets in (([np.eye(2) / np.sqrt(2)], [1]), (projectors, [1, 1]), ([np.eye(4)], [1])):
            with self.subTest(targets=targets, operators=operators), self.assertRaises((ValueError, TypeError)):
                multispin.apply_subsystem_kraus(ket, operators, targets)


class MultispinStateTests(unittest.TestCase):
    def setUp(self):
        for name in ("prepare_bell_pair_state", "density_matrix_from_ket"):
            self.assertTrue(callable(getattr(multispin, name, None)), f"missing required API: {name}")

    # Analytic Bell amplitudes in the public pair order (SRC-006).
    bells = {
        "phi+": np.array([1, 0, 0, 1], complex) / np.sqrt(2),
        "phi-": np.array([1, 0, 0, -1], complex) / np.sqrt(2),
        "psi+": np.array([0, 1, 1, 0], complex) / np.sqrt(2),
        "singlet": np.array([0, 1, -1, 0], complex) / np.sqrt(2),
    }

    def test_non_neighbor_bell_pair_preserves_default_spectator_reduction(self):
        ket = multispin.prepare_bell_pair_state(4, pair=[3, 1])
        rho = np.outer(ket, ket.conj())
        singlet = self.bells["singlet"]
        np.testing.assert_allclose(reference_trace(rho, [3, 1]), np.outer(singlet, singlet.conj()), atol=1e-12, rtol=0)
        np.testing.assert_allclose(reference_trace(rho, [0, 2]), np.diag([1, 0, 0, 0]), atol=1e-12, rtol=0)
        expected = np.zeros(16, complex)
        expected[4], expected[1] = 1 / np.sqrt(2), -1 / np.sqrt(2)
        np.testing.assert_allclose(ket, expected, atol=1e-12, rtol=0)

    def test_all_bell_labels_and_pair_orders_have_analytic_reductions(self):
        for n in range(2, 7):
            for pair in ([0, n - 1], [n - 1, 0]):
                for label, bell in self.bells.items():
                    with self.subTest(n=n, pair=pair, bell=label):
                        ket = multispin.prepare_bell_pair_state(n, pair, label)
                        self.assertEqual(ket.shape, (2 ** n,))
                        self.assertAlmostEqual(np.vdot(ket, ket).real, 1.0, places=12)
                        rho = np.outer(ket, ket.conj())
                        np.testing.assert_allclose(reference_trace(rho, pair), np.outer(bell, bell.conj()), atol=1e-12, rtol=0)
                        spectators = [site for site in range(n) if site not in pair]
                        expected = np.zeros((2 ** len(spectators),) * 2, complex)
                        expected[0, 0] = 1
                        np.testing.assert_allclose(reference_trace(rho, spectators), expected, atol=1e-12, rtol=0)
        np.testing.assert_allclose(multispin.prepare_bell_pair_state(2, [0, 1], "PHI+"), self.bells["phi+"], atol=1e-12, rtol=0)

    def test_swapping_singlet_targets_changes_only_global_ket_phase(self):
        spectators = {0: np.array([1, 2j]) / np.sqrt(5), 2: np.array([3j, 1]) / np.sqrt(10)}
        forward = multispin.prepare_bell_pair_state(4, [1, 3], spectator_kets=spectators)
        reverse = multispin.prepare_bell_pair_state(4, [3, 1], spectator_kets=spectators)
        np.testing.assert_allclose(reverse, -forward, atol=1e-12, rtol=0)
        np.testing.assert_allclose(np.outer(reverse, reverse.conj()), np.outer(forward, forward.conj()), atol=1e-12, rtol=0)

    def test_nonsymmetric_complex_spectators_have_exact_global_amplitudes(self):
        a = np.array([1, 2j]) / np.sqrt(5)
        b = np.array([3j, 1]) / np.sqrt(10)
        for n in range(3, 7):
            pair = [n - 1, 1] if n > 3 else [2, 1]
            spectators = [site for site in range(n) if site not in pair]
            supplied = {site: (a if j % 2 == 0 else b) for j, site in enumerate(spectators)}
            ket = multispin.prepare_bell_pair_state(n, pair, "phi-", supplied)
            expected = np.zeros(2 ** n, complex)
            for index in range(len(expected)):
                bits = [int(bit) for bit in format(index, f"0{n}b")]
                amplitude = self.bells["phi-"][2 * bits[pair[0]] + bits[pair[1]]]
                for site, local in supplied.items():
                    amplitude *= local[bits[site]]
                expected[index] = amplitude
            np.testing.assert_allclose(ket, expected, atol=1e-12, rtol=0)
            local = np.array([1], complex)
            for site in reversed(spectators):
                local = np.kron(local, supplied[site])
            np.testing.assert_allclose(reference_trace(np.outer(ket, ket.conj()), list(reversed(spectators))), np.outer(local, local.conj()), atol=1e-12, rtol=0)

    def test_unspecified_spectators_remain_zero_with_partial_mapping(self):
        a = np.array([1, 2j]) / np.sqrt(5)
        ket = multispin.prepare_bell_pair_state(5, [4, 1], spectator_kets={2: a})
        expected = np.kron(np.kron([1, 0], a), [1, 0])
        np.testing.assert_allclose(reference_trace(np.outer(ket, ket.conj()), [0, 2, 3]), np.outer(expected, expected.conj()), atol=1e-12, rtol=0)

    def test_target_unitary_changes_pair_and_preserves_spectators(self):
        a, b = np.array([1, 2j]) / np.sqrt(5), np.array([3j, 1]) / np.sqrt(10)
        ket = multispin.prepare_bell_pair_state(4, [3, 1], spectator_kets={0: a, 2: b})
        rho = np.outer(ket, ket.conj())
        unitary = np.kron(np.diag([1, 1j]), np.array([[0, 1], [1, 0]]))
        bell = unitary @ self.bells["singlet"]
        for state in (ket, rho):
            changed = apply_subsystem_unitary(state, unitary, [3, 1])
            changed_rho = np.outer(changed, changed.conj()) if changed.ndim == 1 else changed
            np.testing.assert_allclose(reference_trace(changed_rho, [3, 1]), np.outer(bell, bell.conj()), atol=1e-12, rtol=0)
            self.assertFalse(np.allclose(reference_trace(changed_rho, [3, 1]), reference_trace(rho, [3, 1])))
            np.testing.assert_allclose(reference_trace(changed_rho, [2, 0]), reference_trace(rho, [2, 0]), atol=1e-12, rtol=0)

    def test_bell_preparation_rejects_invalid_pairs_counts_and_labels(self):
        for pair in ([], [0], [0, 1, 2], [1, 1], [-1, 0], [0, 4], [True, 1], [0.0, 1], {0, 1}, "01", None):
            with self.subTest(pair=pair), self.assertRaises((TypeError, ValueError)):
                multispin.prepare_bell_pair_state(4, pair)
        for n in (1, 7, True, 2.0):
            with self.subTest(n=n), self.assertRaises((TypeError, ValueError)):
                multispin.prepare_bell_pair_state(n, [0, 1])
        for label in ("unknown", "", None, 1, []):
            with self.subTest(label=label), self.assertRaises((TypeError, ValueError)):
                multispin.prepare_bell_pair_state(4, [3, 1], label)

    def test_bell_preparation_rejects_invalid_spectator_mappings_and_kets(self):
        for supplied in ({1: [1, 0]}, {3: [1, 0]}, {-1: [1, 0]}, {4: [1, 0]}, {True: [1, 0]}, {0.0: [1, 0]}, {"0": [1, 0]}, [], [(0, [1, 0])], {0: [1, 1]}, {0: [0, 0]}, {0: [1, 0, 0]}, {0: [[1], [0]]}, {0: [np.nan, 0]}, {0: [np.inf, 0]}):
            with self.subTest(supplied=supplied), self.assertRaises((TypeError, ValueError)):
                multispin.prepare_bell_pair_state(4, [3, 1], spectator_kets=supplied)

    def test_density_matrix_from_ket_preserves_complex_phase_and_register_sizes(self):
        for n in range(2, 7):
            ket = np.zeros(2 ** n, complex)
            ket[0], ket[-1] = 1 / np.sqrt(5), 2j / np.sqrt(5)
            expected = np.zeros((2 ** n,) * 2, complex)
            expected[0, 0], expected[-1, -1] = 0.2, 0.8
            expected[0, -1], expected[-1, 0] = -0.4j, 0.4j
            np.testing.assert_allclose(multispin.density_matrix_from_ket(ket), expected, atol=1e-12, rtol=0)
            np.testing.assert_allclose(multispin.density_matrix_from_ket(1j * ket), expected, atol=1e-12, rtol=0)

    def test_density_matrix_from_ket_rejects_invalid_shapes_norm_and_entries(self):
        for ket in (np.ones(2), np.ones(3), np.ones(128), np.eye(4), np.ones((4, 1)), np.ones(4), np.zeros(4), np.array([np.nan, 0, 0, 0]), np.array([np.inf, 0, 0, 0])):
            with self.subTest(ket=ket), self.assertRaises(ValueError):
                multispin.density_matrix_from_ket(ket)


if __name__ == "__main__":
    unittest.main()
