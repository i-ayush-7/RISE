import unittest
import os
import re
from rise.alerts import Alert, get_provider

class TestAlerts(unittest.TestCase):
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
        self.assertIn("Fixture file not found", str(ctx.exception))
        
    def test_unknown_scenario(self):
        os.environ["RISE_ALERT_SOURCE"] = "fixture"
        os.environ["RISE_FIXTURE_SCENARIO"] = "unknown"
        provider = get_provider()
        with self.assertRaises(ValueError) as ctx:
            provider.get_alerts()
        self.assertIn("Fixture file not found", str(ctx.exception))
        
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

if __name__ == "__main__":
    unittest.main()
