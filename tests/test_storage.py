import json
import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from quantum_lab.experiments import run_signaling_experiment
from quantum_lab.storage import load_configuration, save_experiment


class StorageTests(unittest.TestCase):
    def test_experiment_export_writes_json_csv_and_reloadable_configuration(self):
        result = run_signaling_experiment(shots=40, seed=123)
        config = {"protocol": "signaling", "shots": 40, "seed": 123}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            paths = save_experiment(result, config, Path(temp))
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(load_configuration(paths["json"]), config)
            self.assertTrue(paths["csv"].is_file())
            self.assertIn("receiver_counts", payload["results"])
            self.assertEqual(payload["results"]["initial_state"], "singlet")
            self.assertIn("code_version", payload["metadata"])
            self.assertIn("kaleido", payload["metadata"]["dependency_versions"])
            self.assertIn("SRC-003", payload["sources"])
            self.assertIn("SRC-002", payload["sources"])
            self.assertIn("SRC-006", payload["sources"])

    def test_phase_sweep_record_round_trips_parameters_results_and_plot_artifacts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            root = Path(temp)
            configuration = {
                "protocol": "phase_damping_sweep", "state_name": "singlet",
                "lambda_a": [0.0, 0.5, 1.0], "lambda_b": [0.0, 0.25, 1.0], "seed": 123,
            }
            results = {
                "model": "local_phase_damping_on_full_two_spin_density_matrix",
                "concurrence": np.array([[1.0, 0.75], [0.5, 0.0]]),
                "plotly_figures": {"concurrence": "{\"data\":[]}"},
            }
            paths = save_experiment(
                results, configuration, root / "experiments",
                artifacts={"concurrence": ["plots/concurrence.html"]},
            )

            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["configuration"], configuration)
            self.assertEqual(payload["results"]["concurrence"], [[1.0, 0.75], [0.5, 0.0]])
            self.assertEqual(payload["results"]["plotly_figures"]["concurrence"], "{\"data\":[]}")
            self.assertEqual(payload["artifacts"], {"concurrence": ["plots/concurrence.html"]})
            self.assertIn("Kraus", payload["metadata"]["method"])
            self.assertEqual(payload["metadata"]["model"], results["model"])
            self.assertEqual(load_configuration(paths["json"]), configuration)
            self.assertIn("SRC-010", payload["sources"])
            self.assertIn("SRC-013", payload["sources"])
            self.assertIn("SRC-014", payload["sources"])

    def test_phase_sweep_csv_preserves_full_maximum_grid_arrays(self):
        grid = np.arange(51 * 51, dtype=float).reshape(51, 51)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            paths = save_experiment(
                {"concurrence": grid},
                {"protocol": "phase_damping_sweep"},
                temp,
            )
            with paths["csv"].open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))

        serialized = next(row["value"] for row in rows if row["field"] == "concurrence")
        restored = np.asarray(json.loads(serialized))
        np.testing.assert_array_equal(restored, grid)


if __name__ == "__main__":
    unittest.main()
