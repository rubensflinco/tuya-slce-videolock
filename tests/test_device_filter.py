"""Tests for lock device filtering (config-flow picker)."""
from __future__ import annotations
import unittest
from test_tuya_parsers import api

class TestFilterLockDevices(unittest.TestCase):
    def test_keeps_videolock_and_ms(self):
        devices = [
            {"id": "a", "name": "Lamp", "category": "dj"},
            {"id": "b", "name": "SL-CE", "category": "videolock", "online": True},
            {"id": "c", "name": "Gate", "category": "ms"},
            {"id": "d", "name": "Broken", "category": "videolock"},  # no id skip if empty
        ]
        devices[3] = {"name": "Broken", "category": "videolock"}
        out = api.filter_lock_devices(devices)
        ids = [d["id"] for d in out]
        self.assertEqual(ids, ["c", "b"])  # sorted by name: Gate, SL-CE

    def test_format_option(self):
        label = api.format_device_option(
            {"id": "eba0", "name": "Fechadura", "category": "videolock", "online": True}
        )
        self.assertIn("Fechadura", label)
        self.assertIn("videolock", label)
        self.assertIn("eba0", label)
        self.assertIn("online", label)

if __name__ == "__main__":
    unittest.main()
