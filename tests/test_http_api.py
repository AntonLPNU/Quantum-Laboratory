import http.client
import json
import shutil
import threading
import unittest
from pathlib import Path

import numpy as np

from quantum_lab import http_api
from quantum_lab.http_api import create_server, dispatch


class HttpApiTests(unittest.TestCase):
    def test_server_factory_binds_loopback_to_an_available_ephemeral_port(self):
        server = create_server(port=0)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertGreater(server.server_address[1], 0)
        finally:
            server.server_close()

    def test_http_server_rejects_overlapping_post_work_without_allocating_another_job(self):
        server = create_server(port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        self.assertTrue(http_api._POST_REQUEST_SLOTS.acquire(blocking=False))
        try:
            worker.start()
            connection = http.client.HTTPConnection(*server.server_address, timeout=5)
            body = json.dumps({"n_spins": 2, "pair": [0, 1], "bell": "singlet"})
            connection.request("POST", "/api/state", body=body,
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 503)
            self.assertEqual(result["error"]["code"], "server_busy")
            connection.close()
        finally:
            http_api._POST_REQUEST_SLOTS.release()
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_health_and_capabilities_report_backend_and_data_provenance(self):
        status, health = dispatch("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")
        status, capabilities = dispatch("GET", "/api/capabilities")
        self.assertEqual(status, 200)
        self.assertTrue(capabilities["features"]["tfim"]["available"])
        self.assertEqual(capabilities["features"]["hensen_2015"]["kind"], "published_data_reanalysis")
        self.assertEqual(capabilities["features"]["hensen_2015"]["available"], http_api.HENSEN_2015.is_file())

    def test_state_route_returns_python_density_matrix_and_measurement_kind(self):
        status, result = dispatch("POST", "/api/run/state", {"state_name": "singlet", "shots": 0})
        self.assertEqual(status, 400)
        status, result = dispatch("POST", "/api/run/state", {"state_name": "singlet", "shots": 32, "seed": 10})
        self.assertEqual(status, 200)
        self.assertEqual(result["kind"], "sampled_measurement_and_exact_prediction")
        matrix = result["result"]["density_matrix"]
        self.assertEqual(len(matrix), 4)
        self.assertAlmostEqual(matrix[0][0]["real"], 0.0)
        self.assertTrue(result["provenance"]["engine"].startswith("quantum_lab"))

    def test_phase_damping_uses_core_sweep_and_returns_independent_grids(self):
        status, payload = dispatch("POST", "/api/run/phase-damping", {"values_a": [0, 1], "values_b": [0, 1]})
        self.assertEqual(status, 200)
        result = payload["result"]
        np.testing.assert_allclose(result["concurrence"], [[1.0, 0.0], [0.0, 0.0]], atol=1e-14)
        np.testing.assert_allclose(result["chsh_maximal"], [[2 * np.sqrt(2), 2.0], [2.0, 2.0]], atol=1e-14)

    def test_tfim_route_builds_schedule_and_calls_core(self):
        status, payload = dispatch("POST", "/api/run/tfim", {
            "n_spins": 2, "J": 1.0,
            "h_schedule": {"kind": "constant", "parameters": [0.0], "edges_s": [], "values": []},
            "initial_state": [1, 0, 0, 0], "times_s": [0.0, 0.1],
            "solver_options": {"save_states_at": [0, 1]},
        })
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["result"]["results"]["completed"])

    def test_multispin_operations_partial_trace_and_analysis_use_core_apis(self):
        status, prepared = dispatch("POST", "/api/state", {"n_spins": 3, "pair": [0, 2], "bell": "singlet"})
        self.assertEqual(status, 200)
        rho = prepared["result"]["density_matrix"]
        self.assertEqual(len(rho), 8)
        status, reduced = dispatch("POST", "/api/state/reduce", {"density_matrix": rho, "keep": [2, 0]})
        self.assertEqual(status, 200)
        self.assertEqual(reduced["result"]["keep_order"], [2, 0])
        status, rotated = dispatch("POST", "/api/state/operation", {"density_matrix": rho, "site": 2, "axis": [0, 1, 0], "angle_rad": 0.4})
        self.assertEqual(status, 200)
        status, stats = dispatch("POST", "/api/analyze/observable", {"density_matrix": rotated["result"]["density_matrix"], "site": 2, "pauli": "sigma_x", "shots": 100, "seed": 2})
        self.assertEqual(status, 200)
        self.assertEqual(stats["result"]["sample"]["independent_preparations"], 100)

    def test_stage5b_and_hensen_endpoints_keep_science_provenance(self):
        config = {"n_spins": 3, "J": 1e5,
                  "h_schedule": {"kind": "constant", "parameters": [2e5], "edges_s": [], "values": []},
                  "times_s": [0.0, 1e-6],
                  "sources": [f"SRC-{i:03d}" for i in range(20, 27)]}
        status, response = dispatch("POST", "/api/run/stage5b", config)
        self.assertEqual(status, 200, response)
        self.assertEqual(response["kind"], "stage5b_analysis")
        status, hensen = dispatch("POST", "/api/run/hensen-2015", {})
        if http_api.HENSEN_2015.is_file():
            self.assertEqual(status, 200, hensen)
            self.assertEqual(hensen["kind"], "published_data_reanalysis")
            self.assertNotIn("trials", hensen["result"])
        else:
            self.assertEqual(status, 404, hensen)
            self.assertEqual(hensen["error"]["code"], "source_data_missing")

    def test_spectrum_and_explicit_fit_routes_dispatch_to_deviation_core(self):
        times = [0.0, 1e-6, 2e-6, 3e-6, 4e-6, 5e-6]
        values = [0.0, 1.0, 0.0, -1.0, 0.0, 1.0]
        status, spectrum = dispatch("POST", "/api/analyze/spectrum", {"times_s": times, "values": values, "window": "hann"})
        self.assertEqual(status, 200, spectrum)
        status, fit = dispatch("POST", "/api/analyze/sinusoid", {"times_s": times, "values": values, "model": "sinusoid", "initial_parameters": {"omega_rad_s": 1e6}})
        self.assertEqual(status, 200, fit)
        self.assertEqual(fit["kind"], "explicit_model_fit")

    def test_record_api_round_trips_only_inside_the_experiment_directory(self):
        folder = Path(__file__).parent / ".http_api_tmp"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir()
        try:
            status, payload = dispatch("POST", "/api/experiments/save", {
                "configuration": {"protocol": "state_measurement", "state_name": "singlet", "shots": 12},
                "results": {"model": "test", "value": 1.0},
            }, records_dir=folder)
            self.assertEqual(status, 200, payload)
            name = payload["files"]["json"].split("/")[-1]
            status, records = dispatch("GET", "/api/experiments", records_dir=folder)
            self.assertEqual(status, 200)
            self.assertIn(name, records["records"])
            status, loaded = dispatch("GET", f"/api/experiments/{name}", records_dir=folder)
            self.assertEqual(status, 200)
            self.assertEqual(loaded["configuration"]["state_name"], "singlet")
            csv_name = name[:-5] + ".csv"
            status, csv_data = dispatch("GET", f"/api/experiments/csv/{csv_name}", records_dir=folder)
            self.assertEqual(status, 200)
            self.assertIn("experiment_id", csv_data["csv"])
            self.assertEqual(dispatch("GET", "/api/experiments/../../AGENTS.md", records_dir=folder)[0], 400)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_saved_record_comparison_returns_descriptive_shared_scalar_differences(self):
        folder = Path(__file__).parent / ".http_api_tmp"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir()
        try:
            status, left = dispatch("POST", "/api/experiments/save", {
                "configuration": {"protocol": "sampled_measurement", "shots": 100, "seed": 7},
                "results": {"metrics": {"probability": 0.2}, "ignored_array": [1.0, 2.0]},
            }, records_dir=folder)
            self.assertEqual(status, 200, left)
            status, right = dispatch("POST", "/api/experiments/save", {
                "configuration": {"protocol": "sampled_measurement", "shots": 100, "seed": 8},
                "results": {"metrics": {"probability": 0.25}, "ignored_array": [3.0, 4.0]},
            }, records_dir=folder)
            self.assertEqual(status, 200, right)

            status, comparison = dispatch("POST", "/api/experiments/compare", {
                "left": left["files"]["json"], "right": right["files"]["json"],
            }, records_dir=folder)
            self.assertEqual(status, 200, comparison)
            self.assertEqual(comparison["kind"], "descriptive_record_comparison")
            difference = comparison["result"]["comparison"]["numeric_differences"]
            self.assertEqual(len(difference), 1)
            self.assertEqual(difference[0]["path"], "results.metrics.probability")
            self.assertAlmostEqual(difference[0]["difference"], 0.05)
            self.assertFalse(comparison["result"]["comparison"]["configurations_match"])
            self.assertEqual(dispatch("POST", "/api/experiments/compare", {
                "left": "..\\secret.json", "right": right["files"]["json"],
            }, records_dir=folder)[0], 400)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_unknown_route_and_invalid_method_are_structured_errors(self):
        self.assertEqual(dispatch("POST", "/api/not-implemented", {})[0], 404)
        status, error = dispatch("GET", "/api/run/state")
        self.assertEqual(status, 405)
        self.assertEqual(error["error"]["code"], "method_not_allowed")

    def test_sequential_measurement_builds_static_tfim_propagator_in_python(self):
        status, prepared = dispatch("POST", "/api/state", {"n_spins": 2, "pair": [0, 1], "bell": "singlet"})
        self.assertEqual(status, 200)
        status, result = dispatch("POST", "/api/analyze/sequential", {
            "state_at_t1": prepared["result"]["density_matrix"], "site_1": 0, "site_2": 1,
            "pauli_1": "sigma_z", "pauli_2": "sigma_z", "J": 1.0e5, "h": 2.0e5,
            "delta_time_s": 1.0e-7, "shots": 200, "seed": 11,
        })
        self.assertEqual(status, 200, result)
        self.assertEqual(result["result"]["back_action"], "Lüders projection after first measurement")
        self.assertTrue(result["result"]["observations_are_paired"])
        self.assertEqual(sum(row["count"] for row in result["result"]["sample"]["joint_counts"]), 200)
        self.assertEqual(result["result"]["propagator_model"], "static_open_tfim")

    def test_locked_stage5b_report_is_read_only_and_exposes_original_statistics(self):
        status, report = dispatch("GET", "/api/stage5b/locked-result")
        if status == 404:
            self.assertEqual(report["error"]["code"], "record_not_found")
            return
        self.assertEqual(status, 200, report)
        self.assertEqual(report["kind"], "saved_stage5b_confirmatory_analysis")
        self.assertEqual(report["result"]["statistical_criteria"]["shots_per_group"], 14000)
        self.assertEqual(report["result"]["sampling_analysis"]["test"], "two-sided Fisher exact with Holm adjustment across two primary contrasts")
        self.assertEqual(len(report["result"]["preregistration_hash"]), 64)
        self.assertIn("does not rerun sampling", report["result"]["interpretation"])


if __name__ == "__main__":
    unittest.main()
