"""Unit tests for stream allocate / ticket helpers (no live credentials)."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from unittest.mock import AsyncMock, patch

# Reuse loader from parser tests (avoids importing homeassistant)
from test_tuya_parsers import api  # noqa: E402


class TestResolveHost(unittest.TestCase):
    def test_region_codes(self) -> None:
        self.assertEqual(api.resolve_api_host("us"), "openapi.tuyaus.com")
        self.assertEqual(api.resolve_api_host("EU"), "openapi.tuyaeu.com")

    def test_hostname_passthrough(self) -> None:
        self.assertEqual(
            api.resolve_api_host("openapi.tuyaus.com"), "openapi.tuyaus.com"
        )


class TestStreamAllocate(unittest.IsolatedAsyncioTestCase):
    async def test_allocate_success(self) -> None:
        client = api.TuyaCloudApi("id", "secret", region="us")
        client._token = "tok"
        client._token_expiry = 9e12
        fake = {
            "success": True,
            "result": {"url": "https://example.test/hls/stream.m3u8"},
        }
        with patch.object(client, "_request", new=AsyncMock(return_value=fake)) as req:
            url, err = await client.async_allocate_stream(
                "eba0b0f3d9b38977ed8b0a", "hls"
            )
            self.assertIsNone(err)
            self.assertEqual(url, "https://example.test/hls/stream.m3u8")
            req.assert_awaited_once()
            self.assertEqual(req.await_args.args[0], "POST")
            self.assertIn("stream/actions/allocate", req.await_args.args[1])
            self.assertEqual(req.await_args.args[2], {"type": "hls"})

    async def test_allocate_preferred_fallback(self) -> None:
        client = api.TuyaCloudApi("id", "secret", region="us")
        client._token = "tok"
        client._token_expiry = 9e12

        async def _side_effect(method, path, body=None):
            if body and body.get("type") == "hls":
                return {"success": False, "msg": "no hls"}
            if body and body.get("type") == "rtsp":
                return {"success": True, "result": {"url": "rtsps://example/x"}}
            return {"success": False}

        with patch.object(
            client, "_request", new=AsyncMock(side_effect=_side_effect)
        ):
            url, used, err = await client.async_allocate_stream_preferred(
                "eba0b0f3d9b38977ed8b0a", "hls"
            )
            self.assertIsNone(err)
            self.assertEqual(url, "rtsps://example/x")
            self.assertEqual(used, "rtsp")

    async def test_allocate_stops_on_not_subscribed(self) -> None:
        client = api.TuyaCloudApi("id", "secret", region="us")
        client._token = "tok"
        client._token_expiry = 9e12
        req = AsyncMock(
            return_value={
                "success": False,
                "msg": "No permissions. This API is not subscribed.",
                "code": 28841101,
            }
        )
        with patch.object(client, "_request", new=req):
            url, used, err = await client.async_allocate_stream_preferred(
                "eba0b0f3d9b38977ed8b0a", "hls"
            )
            self.assertIsNone(url)
            self.assertIsNone(used)
            self.assertIn("not subscribed", (err or "").lower())
            # One attempt only — subscription gate applies to all types
            self.assertEqual(req.await_count, 1)

    async def test_ticket_unlock_body(self) -> None:
        client = api.TuyaCloudApi("id", "secret", region="us")
        client._token = "tok"
        client._token_expiry = 9e12
        calls: list[tuple] = []

        async def _side_effect(method, path, body=None):
            calls.append((method, path, body))
            if "password-ticket" in path:
                return {"success": True, "result": {"ticket_id": "T1"}}
            return {"success": True, "result": True}

        with patch.object(
            client, "_request", new=AsyncMock(side_effect=_side_effect)
        ):
            ok = await client.async_unlock("dev123")
            self.assertTrue(ok)
            self.assertIn("password-ticket", calls[0][1])
            self.assertEqual(calls[1][2], {"ticket_id": "T1", "open": True})

    async def test_device_info_raises(self) -> None:
        client = api.TuyaCloudApi("id", "secret", region="us")
        client._token = "tok"
        client._token_expiry = 9e12
        with patch.object(
            client,
            "_request",
            new=AsyncMock(
                return_value={"success": False, "msg": "permission deny", "code": 1106}
            ),
        ):
            with self.assertRaises(api.TuyaApiError) as ctx:
                await client.async_get_device_info("missing")
            self.assertEqual(ctx.exception.code, 1106)


class TestSignShape(unittest.TestCase):
    def test_empty_body_sha256(self) -> None:
        empty = hashlib.sha256(b"").hexdigest()
        self.assertEqual(
            empty,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_json_body_hash(self) -> None:
        body = json.dumps({"type": "hls"})
        self.assertEqual(len(hashlib.sha256(body.encode()).hexdigest()), 64)


class TestStreamEndpointConst(unittest.TestCase):
    def test_allocate_path(self) -> None:
        const = sys.modules["custom_components.slce_videolock.const"]
        path = const.STREAM_ALLOCATE_ENDPOINT.format(device_id="abc")
        self.assertEqual(path, "/v1.0/devices/abc/stream/actions/allocate")


if __name__ == "__main__":
    unittest.main()
