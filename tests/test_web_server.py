"""Tests for the local browser server."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from bellows.config import build_simulation_config
from bellows.web.server import create_app


class WebServerTests(unittest.TestCase):
    def test_root_serves_frontend(self) -> None:
        client = TestClient(create_app(build_simulation_config()))

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("uPlot", response.text)
        self.assertIn("Bellows", response.text)

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


if __name__ == "__main__":
    unittest.main()
