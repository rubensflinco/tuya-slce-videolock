"""Unit tests for status parsers / lock state inference (no network)."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_tuya_api():
    """Load tuya_api without importing homeassistant."""
    package_name = "custom_components.slce_videolock"
    root = Path(__file__).resolve().parents[1] / "custom_components" / "slce_videolock"

    # Minimal package stubs
    cc = types.ModuleType("custom_components")
    cc.__path__ = [str(root.parent)]
    sys.modules.setdefault("custom_components", cc)

    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package

    # Stub aiohttp so tuya_api imports cleanly
    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class ClientSession:
        pass

    aiohttp.ClientError = ClientError
    aiohttp.ClientSession = ClientSession
    sys.modules["aiohttp"] = aiohttp

    for name in ("const", "tuya_api"):
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.{name}", root / f"{name}.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{package_name}.tuya_api"]


api = _load_tuya_api()


class TestParseStatusList(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(api.parse_status_list(None), {})
        self.assertEqual(api.parse_status_list([]), {})

    def test_codes(self):
        result = api.parse_status_list(
            [
                {"code": "residual_electricity", "value": 87},
                {"code": "doorbell", "value": False},
                {"code": "unlock_fingerprint", "value": 2},
            ]
        )
        self.assertEqual(result["residual_electricity"], 87)
        self.assertIs(result["doorbell"], False)
        self.assertEqual(result["unlock_fingerprint"], 2)

    def test_skips_invalid(self):
        result = api.parse_status_list([{"value": 1}, "x", {"code": "a", "value": 1}])
        self.assertEqual(result, {"a": 1})


class TestInferIsLocked(unittest.TestCase):
    def test_automatic_lock_true_means_locked(self):
        self.assertIs(api.infer_is_locked({"automatic_lock": True}), True)

    def test_motor_unlocked(self):
        # motor True → unlocked → is_locked False
        self.assertIs(
            api.infer_is_locked({"lock_motor_state": True, "automatic_lock": False}),
            False,
        )

    def test_motor_locked(self):
        self.assertIs(api.infer_is_locked({"lock_motor_state": False}), True)

    def test_unknown(self):
        self.assertIsNone(api.infer_is_locked({}))


class TestTicketEndpoints(unittest.TestCase):
    def test_endpoint_templates(self):
        const = sys.modules["custom_components.slce_videolock.const"]
        device_id = "eba0b0f3d9b38977ed8b0a"
        self.assertIn(
            device_id,
            const.TICKET_ENDPOINT.format(device_id=device_id),
        )
        self.assertIn(
            "password-free/door-operate",
            const.DOOR_OPERATE_ENDPOINT.format(device_id=device_id),
        )


if __name__ == "__main__":
    unittest.main()
