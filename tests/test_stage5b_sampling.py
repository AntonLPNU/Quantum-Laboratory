import unittest


class Stage5BSamplingTests(unittest.TestCase):
    def sampling(self):
        import importlib.util

        self.assertIsNotNone(importlib.util.find_spec("quantum_lab.stage5b_sampling"))
        import quantum_lab.stage5b_sampling as sampling
        return sampling

    def preregistration(self, sampling):
        record = {"protocol": "stage5b-quantum-domino-v1", "locked": True,
                  "primary_contrasts": ["sender_operation_vs_reference", "positive_control_vs_reference"],
                  "criteria": {"familywise_alpha": .01}}
        record["preregistration_hash"] = sampling._canonical_hash(record)
        return record

    def test_seeded_blinded_ledger_is_reproducible_and_mixed_before_unblinding(self):
        sampling = self.sampling()
        probabilities = {"reference": .5, "sender_operation": .5, "positive_control": .57}
        first = sampling.sample_blinded_outcomes(probabilities, 1000, 8812, preregistration_hash="abc123")
        second = sampling.sample_blinded_outcomes(probabilities, 1000, 8812, preregistration_hash="abc123")
        self.assertEqual(first, second)
        self.assertEqual(len(first["ledger"]), 3000)
        self.assertEqual(set(first["ledger"][0]), {"shot_id", "blind_group", "outcome"})
        codes = list(first["scenario_to_blind_group"].values())
        self.assertEqual(len(set(codes)), 3)
        ordered = [row["blind_group"] for row in first["ledger"]]
        self.assertGreater(len(set(ordered[:100])), 1)

    def test_primary_analysis_uses_locked_hash_and_shared_control_holm(self):
        sampling = self.sampling()
        probabilities = {"reference": .5, "sender_operation": .5, "positive_control": .57}
        preregistration = self.preregistration(sampling)
        sample = sampling.sample_blinded_outcomes(probabilities, 5000, 773,
                                                   preregistration_hash=preregistration["preregistration_hash"])
        analysis = sampling.analyze_primary_outcomes(sample, preregistration)
        self.assertEqual(analysis["test"], "two-sided Fisher exact with Holm adjustment across two primary contrasts")
        self.assertEqual(set(analysis["contrasts"]), {"sender_operation_vs_reference", "positive_control_vs_reference"})
        self.assertEqual(analysis["shared_control_shots"], 5000)
        self.assertIn("raw_p_value", analysis["contrasts"]["sender_operation_vs_reference"])
        self.assertIn("holm_adjusted_p_value", analysis["contrasts"]["positive_control_vs_reference"])
        with self.assertRaises(ValueError):
            altered = dict(preregistration)
            altered["preregistration_hash"] = "0" * 64
            sampling.analyze_primary_outcomes(sample, altered)


if __name__ == "__main__":
    unittest.main()
