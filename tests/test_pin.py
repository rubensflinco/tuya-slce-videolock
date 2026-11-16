"""Unit tests for unlock PIN hashing (no network / no Home Assistant)."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_pin():
    package_name = "custom_components.slce_videolock"
    root = Path(__file__).resolve().parents[1] / "custom_components" / "slce_videolock"

    cc = types.ModuleType("custom_components")
    cc.__path__ = [str(root.parent)]
    sys.modules.setdefault("custom_components", cc)

    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.pin",
        root / "pin.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestUnlockPin(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pin = _load_pin()

    def test_valid_format(self) -> None:
        self.assertTrue(self.pin.is_valid_unlock_pin("1234"))
        self.assertFalse(self.pin.is_valid_unlock_pin("123"))
        self.assertFalse(self.pin.is_valid_unlock_pin("12345"))
        self.assertFalse(self.pin.is_valid_unlock_pin("12a4"))
        self.assertFalse(self.pin.is_valid_unlock_pin(None))

    def test_hash_and_verify(self) -> None:
        salt, digest = self.pin.hash_unlock_pin("4821")
        self.assertTrue(self.pin.verify_unlock_pin("4821", salt, digest))
        self.assertFalse(self.pin.verify_unlock_pin("4822", salt, digest))
        self.assertFalse(self.pin.verify_unlock_pin("4821", salt, "deadbeef"))
        self.assertFalse(self.pin.verify_unlock_pin("4821", None, digest))

    def test_same_pin_different_salts(self) -> None:
        salt_a, digest_a = self.pin.hash_unlock_pin("9999")
        salt_b, digest_b = self.pin.hash_unlock_pin("9999")
        self.assertNotEqual(salt_a, salt_b)
        self.assertNotEqual(digest_a, digest_b)
        self.assertTrue(self.pin.verify_unlock_pin("9999", salt_a, digest_a))
        self.assertTrue(self.pin.verify_unlock_pin("9999", salt_b, digest_b))

    def test_rejects_invalid_pin_on_hash(self) -> None:
        with self.assertRaises(ValueError):
            self.pin.hash_unlock_pin("abcd")


if __name__ == "__main__":
    unittest.main()
