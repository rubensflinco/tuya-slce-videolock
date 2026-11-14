"""Tuya Cloud OpenAPI client (token, ticket lock, status, stream allocate).

Signing follows the public Tuya Cloud HMAC-SHA256 scheme also used by
MIT-licensed tuya-smart-lock / community stream helpers. Camera allocate uses
the documented endpoint POST /v1.0/devices/{id}/stream/actions/allocate —
behaviour observed in the ecosystem; no GPL code is copied.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_REGIONS,
    DEFAULT_REGION,
    DEVICE_ENDPOINT,
    DOOR_OPERATE_ENDPOINT,
    DP_AUTO_LOCK_TIME,
    DP_AUTOMATIC_LOCK,
    DP_LOCK_MOTOR_STATE,
    REMOTE_UNLOCKS_ENDPOINT,
    STATUS_ENDPOINT,
    STREAM_ALLOCATE_ENDPOINT,
    STREAM_TYPE_PREFERENCE,
    TICKET_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


def resolve_api_host(region: str) -> str:
    """Map region code or hostname to OpenAPI host."""
    key = (region or DEFAULT_REGION).strip().lower()
    if key in API_REGIONS:
        return API_REGIONS[key]
    if key.startswith("openapi."):
        return key
    if "://" in key:
        return key.split("://", 1)[1].rstrip("/")
    return API_REGIONS.get(DEFAULT_REGION, API_REGIONS["us"])


def parse_status_list(result: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Convert Tuya status array into code→value map."""
    out: dict[str, Any] = {}
    for item in result or []:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if code is None:
            continue
        out[str(code)] = item.get("value")
    return out


class TuyaCloudApi:
    """Async Tuya Cloud client shared by lock, sensors and camera."""

    def __init__(
        self,
        access_id: str,
        access_secret: str,
        region: str = DEFAULT_REGION,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._access_id = access_id
        self._access_secret = access_secret
        self._base_url = f"https://{resolve_api_host(region)}"
        self._session = session
        self._owns_session = session is None
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._uid: str | None = None

    async def async_close(self) -> None:
        """Close owned aiohttp session if any."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def _ensure_token(self) -> None:
        if self._token and time.time() < self._token_expiry:
            return

        path = "/v1.0/token?grant_type=1"
        url = f"{self._base_url}{path}"
        t = str(int(time.time() * 1000))
        string_to_sign = (
            "GET\n" + hashlib.sha256(b"").hexdigest() + "\n\n" + path
        )
        sign_str = self._access_id + t + string_to_sign
        sign = (
            hmac.new(
                self._access_secret.encode(),
                sign_str.encode(),
                hashlib.sha256,
            )
            .hexdigest()
            .upper()
        )
        headers = {
            "client_id": self._access_id,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
        }

        session = self._get_session()
        async with session.get(url, headers=headers) as resp:
            data = await resp.json(content_type=None)

        if not data.get("success"):
            raise ConnectionError(f"Tuya token error: {data.get('msg')}")

        result = data["result"]
        self._token = result["access_token"]
        self._token_expiry = time.time() + float(result.get("expire_time", 7200)) - 60
        self._uid = result.get("uid")

    def _sign_request(self, method: str, path: str, body: str = "") -> dict[str, str]:
        assert self._token is not None
        t = str(int(time.time() * 1000))
        content_hash = hashlib.sha256(body.encode()).hexdigest()
        string_to_sign = f"{method}\n{content_hash}\n\n{path}"
        sign_str = self._access_id + self._token + t + string_to_sign
        sign = (
            hmac.new(
                self._access_secret.encode(),
                sign_str.encode(),
                hashlib.sha256,
            )
            .hexdigest()
            .upper()
        )
        return {
            "client_id": self._access_id,
            "access_token": self._token,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json",
        }

    async def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        await self._ensure_token()
        url = f"{self._base_url}{path}"
        body_str = json.dumps(body) if body is not None else ""
        headers = self._sign_request(method, path, body_str)
        session = self._get_session()

        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json(content_type=None)
        async with session.post(url, headers=headers, data=body_str) as resp:
            return await resp.json(content_type=None)

    async def async_test_credentials(self) -> bool:
        """Validate Access ID/Secret by obtaining a token."""
        try:
            self._token = None
            self._token_expiry = 0.0
            await self._ensure_token()
            return True
        except (ConnectionError, aiohttp.ClientError, KeyError, TypeError, ValueError):
            return False

    async def async_get_device(self, device_id: str) -> dict[str, Any] | None:
        """Fetch device metadata (name, online, product_name)."""
        resp = await self._request("GET", DEVICE_ENDPOINT.format(device_id=device_id))
        if not resp.get("success"):
            _LOGGER.warning("Device info failed: %s", resp.get("msg"))
            return None
        result = resp.get("result")
        return result if isinstance(result, dict) else None

    async def async_get_status(self, device_id: str) -> dict[str, Any]:
        """Return DP code→value map."""
        resp = await self._request("GET", STATUS_ENDPOINT.format(device_id=device_id))
        if not resp.get("success"):
            raise ConnectionError(f"Status error: {resp.get('msg')}")
        raw = resp.get("result")
        if isinstance(raw, list):
            return parse_status_list(raw)
        return {}

    async def async_get_auto_lock_time(self, device_id: str) -> int | None:
        status = await self.async_get_status(device_id)
        value = status.get(DP_AUTO_LOCK_TIME)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    async def async_get_lock_state(self, device_id: str) -> bool | None:
        """True if unlocked, False if locked, None if unknown."""
        status = await self.async_get_status(device_id)
        if status.get(DP_AUTOMATIC_LOCK) is True:
            return False
        motor = status.get(DP_LOCK_MOTOR_STATE)
        if isinstance(motor, bool):
            return motor
        return None

    async def async_check_remote_unlock(self, device_id: str) -> bool:
        path = REMOTE_UNLOCKS_ENDPOINT.format(device_id=device_id)
        resp = await self._request("GET", path)
        if not resp.get("success"):
            return True
        for unlock_type in resp.get("result", []) or []:
            if unlock_type.get("remote_unlock_type") == "remoteUnlockWithoutPwd":
                return bool(unlock_type.get("open", False))
        return False

    async def _ticket_operate(self, device_id: str, open_door: bool) -> bool:
        ticket_resp = await self._request(
            "POST", TICKET_ENDPOINT.format(device_id=device_id)
        )
        if not ticket_resp.get("success"):
            _LOGGER.error("Ticket failed: %s", ticket_resp.get("msg"))
            return False
        ticket_id = ticket_resp["result"]["ticket_id"]
        op_resp = await self._request(
            "POST",
            DOOR_OPERATE_ENDPOINT.format(device_id=device_id),
            {"ticket_id": ticket_id, "open": open_door},
        )
        if not op_resp.get("success"):
            _LOGGER.error("Door operate failed: %s", op_resp.get("msg"))
            return False
        return True

    async def async_unlock(self, device_id: str) -> bool:
        return await self._ticket_operate(device_id, True)

    async def async_lock(self, device_id: str) -> bool:
        return await self._ticket_operate(device_id, False)

    async def async_allocate_stream(
        self, device_id: str, stream_type: str = "hls"
    ) -> str | None:
        """Allocate a live stream URL (hls/rtsp/…).

        Tuya docs: POST /v1.0/devices/{device_id}/stream/actions/allocate
        Body: {"type": "hls"|"rtsp"|...}
        """
        stype = (stream_type or "hls").strip().lower()
        path = STREAM_ALLOCATE_ENDPOINT.format(device_id=device_id)
        resp = await self._request("POST", path, {"type": stype})
        if not resp.get("success"):
            _LOGGER.warning(
                "Stream allocate (%s) failed for %s: %s",
                stype,
                device_id,
                resp.get("msg"),
            )
            return None
        result = resp.get("result") or {}
        url = result.get("url") if isinstance(result, dict) else None
        return str(url) if url else None

    async def async_allocate_stream_preferred(
        self,
        device_id: str,
        preferred: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Try preferred type then fallbacks; return (url, type_used)."""
        order: list[str] = []
        if preferred:
            order.append(preferred.strip().lower())
        for item in STREAM_TYPE_PREFERENCE:
            if item not in order:
                order.append(item)

        for stype in order:
            url = await self.async_allocate_stream(device_id, stype)
            if url:
                return url, stype
        return None, None
