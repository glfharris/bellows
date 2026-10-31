"""Tests for the local browser server."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from bellows.config import build_simulation_config
from bellows.web.server import create_app


class WebServerTests(unittest.TestCase):
    def test_pause_requires_a_boolean_and_preserves_state_on_invalid_input(self) -> None:
        client = TestClient(create_app(build_simulation_config()))
        for payload in ({}, {"paused": None}, {"paused": "false"}, {"paused": 1}):
            with self.subTest(payload=payload):
                response = client.post("/api/pause", json=payload)

                self.assertEqual(response.status_code, 422)
                self.assertFalse(client.get("/api/state").json()["paused"])

        for paused in (True, False):
            response = client.post("/api/pause", json={"paused": paused})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["paused"], paused)

    def test_rejects_malformed_updates_without_changing_state(self) -> None:
        client = TestClient(create_app(build_simulation_config()))
        initial = client.get("/api/state").json()
        cases = (
            ("/api/settings", {"rr_bpm": None}),
            ("/api/settings", {"rr_bpm": "NaN"}),
            ("/api/settings", {"rr_bpm": "14"}),
            ("/api/settings", {"rr_bpm": True}),
            ("/api/settings", {"mode": "NOPE"}),
            ("/api/settings", {"rr_typo": 14}),
            ("/api/patient", {"resistance_cm_h2o_s_per_l": None}),
            ("/api/patient", {"resistance_cm_h2o_s_per_l": []}),
            ("/api/patient", {"compliance_ml_per_cm_h2o": "Infinity"}),
            ("/api/patient", {"lung_model": 42}),
            ("/api/patient", {"preset_typo": "Normal"}),
        )
        for path, payload in cases:
            with self.subTest(path=path, payload=payload):
                self.assertEqual(client.post(path, json=payload).status_code, 422)
                self.assertEqual(client.get("/api/state").json(), initial)

    def test_rejects_invalid_domain_values_without_changing_state(self) -> None:
        client = TestClient(create_app(build_simulation_config()))
        initial = client.get("/api/state").json()
        for path, payload in (
            ("/api/settings", {"rr_bpm": 0}),
            ("/api/settings", {"p_low_cm_h2o": 30}),
            ("/api/patient", {"compliance_ml_per_cm_h2o": 0}),
            ("/api/patient", {"lung_model": "Venegas", "slope_width_cm_h2o": 0}),
            ("/api/patient", {"preset": "NOPE"}),
        ):
            with self.subTest(path=path, payload=payload):
                self.assertEqual(client.post(path, json=payload).status_code, 400)
                self.assertEqual(client.get("/api/state").json(), initial)

    def test_rejects_invalid_sample_queries_even_while_paused(self) -> None:
        client = TestClient(create_app(build_simulation_config()))
        client.post("/api/pause", json={"paused": True})
        for query in (
            "seconds=-1", "seconds=nan", "seconds=inf",
            "dt_s=0", "dt_s=nan", "dt_s=inf",
        ):
            with self.subTest(query=query):
                self.assertEqual(client.get(f"/api/samples?{query}").status_code, 422)
        self.assertEqual(client.get("/api/state").json()["sample"]["time_s"], 0.0)

    def test_root_serves_frontend(self) -> None:
        client = TestClient(create_app(build_simulation_config()))

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("uPlot", response.text)
        self.assertIn("Bellows", response.text)
        self.assertNotIn('id="co2"', response.text)
        self.assertNotIn("EtCO2", response.text)

    def test_state_and_samples_endpoints_return_simulation_payloads(self) -> None:
        client = TestClient(create_app(build_simulation_config()))

        state = client.get("/api/state")
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["settings"]["mode"], "VCV")
        self.assertEqual(state.json()["sample"]["time_s"], 0.0)

        samples = client.get("/api/samples?seconds=0.02&dt_s=0.01")

        self.assertEqual(samples.status_code, 200)
        self.assertEqual(len(samples.json()["samples"]), 2)
        self.assertAlmostEqual(samples.json()["state"]["sample"]["time_s"], 0.02)

        completed = client.get("/api/samples?seconds=5.0&dt_s=0.02")
        self.assertIn(
            "mean_pressure_cm_h2o",
            completed.json()["state"]["last_breath_summary"],
        )
        self.assertIn("previous_breath_summary", completed.json()["state"])

    def test_settings_endpoint_queues_updates(self) -> None:
        client = TestClient(create_app(build_simulation_config()))

        response = client.post(
            "/api/settings",
            json={"mode": "PCV", "pinsp_cm_h2o": 20.0},
        )
        state = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(state["settings"]["mode"], "VCV")
        self.assertEqual(state["pending_settings"]["mode"], "PCV")
        self.assertEqual(state["pending_settings"]["pinsp_cm_h2o"], 20.0)

    def test_patient_endpoint_updates_lung_model_parameters(self) -> None:
        client = TestClient(create_app(build_simulation_config()))

        model = client.post("/api/patient", json={"lung_model": "Venegas+H"}).json()
        self.assertEqual(model["patient"]["lung_model"], "Venegas+H")
        self.assertIn("hysteresis_offset_cm_h2o", model["patient"]["lung_parameters"])

        response = client.post(
            "/api/patient",
            json={
                "inflection_cm_h2o": 24.0,
                "slope_width_cm_h2o": 4.0,
                "recruitable_volume_ml": 1000.0,
                "hysteresis_offset_cm_h2o": 6.0,
                "resistance_cm_h2o_s_per_l": 18.0,
            },
        )
        state = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(state["patient"]["preset"], "Custom")
        self.assertEqual(state["patient"]["resistance_cm_h2o_s_per_l"], 18.0)
        self.assertEqual(
            state["patient"]["lung_parameters"]["inflection_cm_h2o"],
            24.0,
        )
        self.assertEqual(
            state["patient"]["lung_parameters"]["hysteresis_offset_cm_h2o"],
            6.0,
        )


if __name__ == "__main__":
    unittest.main()
