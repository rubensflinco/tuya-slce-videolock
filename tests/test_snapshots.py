"""Unit tests for doorbell snapshot helpers."""

from __future__ import annotations

import unittest

from custom_components.slce_videolock.const import (
    DEFAULT_SNAPSHOT_RETENTION_DAYS,
    MAX_SNAPSHOT_RETENTION_DAYS,
    MIN_SNAPSHOT_RETENTION_DAYS,
    clamp_retention_days,
)


class TestClampRetentionDays(unittest.TestCase):
    def test_default_on_invalid(self) -> None:
        self.assertEqual(clamp_retention_days(None), DEFAULT_SNAPSHOT_RETENTION_DAYS)
        self.assertEqual(clamp_retention_days("x"), DEFAULT_SNAPSHOT_RETENTION_DAYS)

    def test_clamp_bounds(self) -> None:
        self.assertEqual(clamp_retention_days(0), MIN_SNAPSHOT_RETENTION_DAYS)
        self.assertEqual(clamp_retention_days(-5), MIN_SNAPSHOT_RETENTION_DAYS)
        self.assertEqual(
            clamp_retention_days(9999), MAX_SNAPSHOT_RETENTION_DAYS
        )

    def test_passthrough(self) -> None:
        self.assertEqual(clamp_retention_days(30), 30)
        self.assertEqual(clamp_retention_days("45"), 45)


if __name__ == "__main__":
    unittest.main()
