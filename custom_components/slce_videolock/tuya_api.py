"""Tuya Cloud API client for SL-CE videolock (ticket unlock + status).

Ticket unlock / lock flow adapted from nicolasglg/tuya-smart-lock (MIT).
Device status / info polling patterns adapted from crestall/ha-tuya-lock-monitor (MIT).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any

import aiohttp

from .const import (
    API_REGIONS,
    DEFAULT_REGION,
    DEVICE_INFO_ENDPOINT,
    DOOR_OPERATE_ENDPOINT,
    DP_AUTO_LOCK_TIME,
    DP_AUTOMATIC_LOCK,
    DP_LOCK_MOTOR,
    REMOTE_UNLOCKS_ENDPOINT,
    STATUS_ENDPOINT,
    TICKET_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class TuyaApiError(Exception):
    """Raised when the Tuya Cloud API returns an error."""

    def __init__(self, message: str, *, code: Any = None) -> None:
        super().__init__(message)
        self.code = code


class TuyaCloudApi:
    """Async client for Tuya OpenAPI (token + smart-lock ticket + status)."""

    def __init__(
        self,
        access_id: str,
        access_secret: str,
        region: str = DEFAULT_REGION,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._access_id = access_id
        self._access_secret = access_secret
        region_key = (region or DEFAULT_REGION).strip().lower()
        host = API_REGIONS.get(region_key)
        if not host:
            raise ValueError(f"Unknown Tuya region: {region}")
        self._base_url = f"https://{host}"
        self._session = session
        self._owns_session = session is None
        self._token: str | None = None
        self._token_expiry: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def async_close(self) -> None:
        """Close the aiohttp session if we created it."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _sign(
        self,
        method: str,
        path: str,
        *,
        token: str = "",
        body: str = "",
        ts: str | None = None,
        nonce: str | None = None,
    ) -> tuple[dict[str, str], str, str]:
        """Build signed headers (HMAC-SHA256 with nonce).

        Returns (headers, ts, nonce).
        """
        ts = ts or str(int(time.time() * 1000))
        nonce = nonce or uuid.uuid4().hex
        content_hash = hashlib.sha256(body.encode()).hexdigest()
        string_to_sign = f"{method}\n{content_hash}\n\n{path}"
        sign_str = self._access_id + token + ts + nonce + string_to_sign
        sign = hmac.new(
            self._access_secret.encode(),
            sign_str.encode(),
            hashlib.sha256,
        ).hexdigest().upper()

        headers: dict[str, str] = {
            "client_id": self._access_id,
            "sign": sign,
            "t": ts,
            "sign_method": "HMAC-SHA256",
            "nonce": nonce,
        }
        if token:
            headers["access_token"] = token
        if body:
            headers["Content-Type"] = "application/json"
        return headers, ts, nonce

    async def _ensure_token(self) -> str:
        """Get or refresh the access token."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        path_with_query = "/v1.0/token?grant_type=1"
        headers, _, _ = self._sign("GET", path_with_query)
        session = await self._get_session()
        url = f"{self._base_url}{path_with_query}"

        async with session.get(url, headers=headers) as resp:
            data = await resp.json(content_type=None)

        if not data.get("success"):
            msg = data.get("msg", "unknown")
            code = data.get("code")
            _LOGGER.error("Tuya token failed: code=%s msg=%s", code, msg)
            raise TuyaApiError(f"Tuya token error: {msg}", code=code)

        result = data["result"]
        self._token = result["access_token"]
        self._token_expiry = time.time() + float(result.get("expire_time", 7200)) - 60
        return self._token

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a signed request to the Tuya API."""
        token = await self._ensure_token()
        body_str = json.dumps(body) if body is not None else ""
        headers, _, _ = self._sign(method, path, token=token, body=body_str)
        session = await self._get_session()
        url = f"{self._base_url}{path}"

        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json(content_type=None)
        async with session.request(method, url, headers=headers, data=body_str) as resp:
            return await resp.json(content_type=None)

    async def async_test_credentials(self) -> bool:
        """Return True if Access ID/Secret can obtain a token."""
        try:
            self._token = None
            self._token_expiry = 0.0
            await self._ensure_token()
            return True
        except (TuyaApiError, aiohttp.ClientError, TimeoutError, OSError):
            return False

    async def async_get_device_info(self, device_id: str) -> dict[str, Any]:
        """Fetch device metadata (name, online, product_name, …)."""
        path = DEVICE_INFO_ENDPOINT.format(device_id=device_id)
        resp = await self._request("GET", path)
        if not resp.get("success"):
            raise TuyaApiError(
                f"device info: {resp.get('msg')}",
                code=resp.get("code"),
            )
        return resp.get("result") or {}

    async def async_get_status(self, device_id: str) -> dict[str, Any]:
        """Return status DPs as {code: value}."""
        path = STATUS_ENDPOINT.format(device_id=device_id)
        resp = await self._request("GET", path)
        if not resp.get("success"):
            raise TuyaApiError(
                f"device status: {resp.get('msg')}",
                code=resp.get("code"),
            )
        result = resp.get("result") or []
        return {
            item["code"]: item["value"]
            for item in result
            if isinstance(item, dict) and "code" in item
        }

    async def async_check_remote_unlock(self, device_id: str) -> bool:
        """Check if remote unlock without password is enabled."""
        path = REMOTE_UNLOCKS_ENDPOINT.format(device_id=device_id)
        resp = await self._request("GET", path)
        if not resp.get("success"):
            _LOGGER.warning(
                "Could not check remote unlock for %s: %s",
                device_id,
                resp.get("msg"),
            )
            return True  # assume OK if API unavailable

        for unlock_type in resp.get("result") or []:
            if unlock_type.get("remote_unlock_type") == "remoteUnlockWithoutPwd":
                return bool(unlock_type.get("open", False))
        return False

    async def async_get_auto_lock_time(self, device_id: str) -> int | None:
        """Get auto-lock delay in seconds from device status."""
        status = await self.async_get_status(device_id)
        value = status.get(DP_AUTO_LOCK_TIME)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    async def _async_ticket_operate(self, device_id: str, *, open_door: bool) -> bool:
        """Password-free door operate via ticket (unlock if open_door else lock)."""
        ticket_path = TICKET_ENDPOINT.format(device_id=device_id)
        ticket_resp = await self._request("POST", ticket_path)
        if not ticket_resp.get("success"):
            _LOGGER.error(
                "Failed to get password ticket for %s: %s",
                device_id,
                ticket_resp.get("msg"),
            )
            return False

        ticket_id = (ticket_resp.get("result") or {}).get("ticket_id")
        if not ticket_id:
            _LOGGER.error("Ticket response missing ticket_id: %s", ticket_resp)
            return False

        operate_path = DOOR_OPERATE_ENDPOINT.format(device_id=device_id)
        operate_resp = await self._request(
            "POST",
            operate_path,
            {"ticket_id": ticket_id, "open": open_door},
        )
        if not operate_resp.get("success"):
            _LOGGER.error(
                "Door operate (open=%s) failed for %s: %s",
                open_door,
                device_id,
                operate_resp.get("msg"),
            )
            return False

        _LOGGER.info(
            "Door %s %s successfully",
            device_id,
            "unlocked" if open_door else "locked",
        )
        return True

    async def async_unlock(self, device_id: str) -> bool:
        """Unlock via Smart Lock Cloud ticket API."""
        return await self._async_ticket_operate(device_id, open_door=True)

    async def async_lock(self, device_id: str) -> bool:
        """Lock via Smart Lock Cloud ticket API."""
        return await self._async_ticket_operate(device_id, open_door=False)

    async def async_get_lock_state(self, device_id: str) -> bool | None:
        """Return True if unlocked, False if locked, None if unknown.

        When automatic_lock is enabled, treat as locked outside the short
        auto-lock window (Wi-Fi videolocks often freeze lock_motor_state).
        """
        try:
            status = await self.async_get_status(device_id)
        except TuyaApiError as err:
            _LOGGER.error("Failed to get lock state for %s: %s", device_id, err)
            return None

        if status.get(DP_AUTOMATIC_LOCK) is True:
            return False

        motor = status.get(DP_LOCK_MOTOR)
        if motor is None:
            return None
        return bool(motor)


def parse_status_list(result: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Convert a Tuya status list into a code→value map (pure, testable)."""
    if not result:
        return {}
    out: dict[str, Any] = {}
    for item in result:
        if isinstance(item, dict) and "code" in item:
            out[item["code"]] = item.get("value")
    return out


def infer_is_locked(status: dict[str, Any]) -> bool | None:
    """Infer locked state from status DPs. True=locked, False=unlocked, None=unknown."""
    if status.get(DP_AUTOMATIC_LOCK) is True:
        return True
    motor = status.get(DP_LOCK_MOTOR)
    if motor is None:
        return None
    # lock_motor_state True typically means unlocked/open on Tuya locks
    return not bool(motor)
