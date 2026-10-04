import unittest
import os
import json
from pathlib import Path
from unittest.mock import patch
from rise.alerts import Alert, get_provider

class TestAlerts(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_invalid_hazard(self):
        with self.assertRaises(ValueError) as ctx:
            Alert("1", "zombie", "warning", "Head", "Area", "2026", "Src")
        self.assertIn("hazard must be one of", str(ctx.exception))
        
    def test_invalid_severity(self):
        with self.assertRaises(ValueError) as ctx:
            Alert("1", "flood", "bad", "Head", "Area", "2026", "Src")
        self.assertIn("severity must be one of", str(ctx.exception))
        
    def test_malformed_fixture_file(self):
        os.environ["RISE_ALERT_SOURCE"] = "fixture"
        os.environ["RISE_FIXTURE_SCENARIO"] = "missing"
        provider = get_provider()
        with self.assertRaises(ValueError) as ctx:
            provider.get_alerts()
        self.assertIn("Fixture file not found: alerts_missing.json", str(ctx.exception))
        
    def test_scenario_with_path_traversal(self):
        os.environ["RISE_ALERT_SOURCE"] = "fixture"
        os.environ["RISE_FIXTURE_SCENARIO"] = "../secret"
        with self.assertRaises(ValueError) as ctx:
            get_provider()
        self.assertIn("Invalid scenario name", str(ctx.exception))
        
    def test_unknown_source(self):
        os.environ["RISE_ALERT_SOURCE"] = "api"
        with self.assertRaises(ValueError) as ctx:
            get_provider()
        self.assertIn("Unknown alert source", str(ctx.exception))

    def test_real_malformed_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alerts_bad.json"
            p.write_text("{bad json")
            os.environ["RISE_ALERT_SOURCE"] = "fixture"
            os.environ["RISE_FIXTURE_SCENARIO"] = "bad"
            provider = get_provider()
            provider.fixtures_dir = Path(d)
            with self.assertRaises(ValueError) as ctx:
                provider.get_alerts()
            self.assertEqual("Fixture file is invalid: invalid JSON", str(ctx.exception))

    def test_not_a_list(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alerts_not_list.json"
            p.write_text('{"id": 1}')
            os.environ["RISE_ALERT_SOURCE"] = "fixture"
            os.environ["RISE_FIXTURE_SCENARIO"] = "not_list"
            provider = get_provider()
            provider.fixtures_dir = Path(d)
            with self.assertRaises(ValueError) as ctx:
                provider.get_alerts()
            self.assertEqual("Fixture file is invalid: not a list", str(ctx.exception))

    def test_item_missing_field(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alerts_missing.json"
            p.write_text('[{"id": "1", "hazard": "flood"}]')
            os.environ["RISE_ALERT_SOURCE"] = "fixture"
            os.environ["RISE_FIXTURE_SCENARIO"] = "missing"
            provider = get_provider()
            provider.fixtures_dir = Path(d)
            with self.assertRaises(ValueError) as ctx:
                provider.get_alerts()
            self.assertTrue(str(ctx.exception).startswith("Fixture file is invalid: missing field"))

    def test_unknown_field(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alerts_unknown.json"
            # Add all required, plus "zombie"
            obj = {
                "id": "1", "hazard": "flood", "severity": "warning", "headline": "A",
                "area_description": "B", "issued_at": "C", "source": "D", "zombie": "E"
            }
            p.write_text(json.dumps([obj]))
            os.environ["RISE_ALERT_SOURCE"] = "fixture"
            os.environ["RISE_FIXTURE_SCENARIO"] = "unknown"
            provider = get_provider()
            provider.fixtures_dir = Path(d)
            with self.assertRaises(ValueError) as ctx:
                provider.get_alerts()
            self.assertEqual("Fixture file is invalid: unknown field zombie", str(ctx.exception))

    def test_all_shipped_fixtures(self):
        os.environ["RISE_ALERT_SOURCE"] = "fixture"
        for scenario in ["flood_warning", "heatwave_warning", "none"]:
            os.environ["RISE_FIXTURE_SCENARIO"] = scenario
            provider = get_provider()
            alerts = provider.get_alerts()
            for a in alerts:
                self.assertTrue(a.headline.startswith("SIMULATED:"), f"{scenario} headline didn't start with SIMULATED")

if __name__ == "__main__":
    unittest.main()
