import json
import tempfile
import unittest
from pathlib import Path

import numpy as np


class Stage5BStorageTests(unittest.TestCase):
    def test_code_provenance_hash_identifies_python_working_tree(self):
        from quantum_lab.provenance import code_provenance

        provenance = code_provenance(Path(__file__).resolve().parents[1])
        self.assertEqual(len(provenance["git_revision"]), 40)
        self.assertEqual(len(provenance["python_source_sha256"]), 64)
        self.assertIn("quantum_lab/stage5b_sampling.py", provenance["hashed_python_files"])

    def test_stage5b_record_roundtrips_full_precision_results_and_metadata(self):
        from quantum_lab.storage import save_experiment

        value = np.float64(0.12345678901234566)
        results = {
            "status": "success", "full_states": [np.array([[value, 1e-17j], [-1e-17j, 1-value]])],
            "configuration": {"n_spins": 3},
            "scenarios": {name: {"status": "success"} for name in
                           ("reference", "sender_operation", "positive_control")},
            "receiver_states": [np.array([[0.5, .125j], [-.125j, .5]])],
            "raw_outcomes": np.array([-1, 1, -1, 1]),
            "contrasts": {"a": {"confidence_interval": (-.12345678901234566, .2345678901234567)}},
            "power": {"wilson_interval": (.9012345678901234, .95)},
            "plot_data": {"times_s": np.array([0., 1.2345678901234567]), "series": [value, .5]},
            "seed_streams": {"children": [[0, 1], [0, 2]]},
        }
        configuration = {"protocol": "stage5b_quantum_domino", "sources": [f"SRC-{i:03d}" for i in range(20, 27)],
                         "preregistration_hash": "a" * 64,
                         "code_provenance": {"git_revision": "abc123", "python_source_sha256": "b" * 64}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            paths = save_experiment(results, configuration, directory)
            record = json.loads(paths["json"].read_text(encoding="utf-8"))
            encoded_density = record["results"]["full_states"][0]
            self.assertEqual(encoded_density[0][0], {"real": float(value), "imag": 0.0})
            self.assertEqual(encoded_density[0][1], {"real": 0.0, "imag": 1e-17})
            self.assertEqual(record["results"]["plot_data"]["times_s"][1], 1.2345678901234567)
            self.assertEqual(record["configuration"], configuration)
            self.assertIn("SRC-020", record["sources"])
            self.assertIn("preregistration_hash", record["metadata"])
            self.assertEqual(record["metadata"]["code_provenance"]["python_source_sha256"], "b" * 64)
            self.assertIn("stage5b", record["metadata"]["method"])
            self.assertTrue(paths["csv"].exists())

    def test_failed_stage5b_result_is_not_serialized_as_success(self):
        from quantum_lab.storage import save_experiment

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            with self.assertRaises(ValueError):
                save_experiment({"status": "failed", "error": "solver tolerance unmet"},
                                {"protocol": "stage5b_quantum_domino"}, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
