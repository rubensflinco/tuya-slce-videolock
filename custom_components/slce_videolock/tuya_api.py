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
    ALARM_LOGS_ENDPOINT,
    API_REGIONS,
    DEFAULT_REGION,
    DEVICE_ENDPOINT,
    DOOR_OPERATE_ENDPOINT,
    DP_AUTO_LOCK_TIME,
    DP_AUTOMATIC_LOCK,
    DP_LOCK_MOTOR_STATE,
    LOG_PAGE_SIZE,
    OPEN_LOGS_ENDPOINT,
    RECORDS_ENDPOINT,
    REMOTE_UNLOCKS_ENDPOINT,
    STATUS_ENDPOINT,
    STREAM_ALLOCATE_ENDPOINT,
    STREAM_TYPE_PREFERENCE,
    SUPPORTED_LOCK_CATEGORIES,
    TICKET_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class TuyaApiError(Exception):
    """Raised when the Tuya Cloud API returns an error payload."""

    def __init__(self, message: str, *, code: Any = None) -> None:
        super().__init__(message)
        self.code = code


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


def device_category(dev: dict[str, Any]) -> str:
    """Best-effort category from Cloud list / detail payloads."""
    for key in ("category", "category_code", "product_category", "device_category"):
        raw = dev.get(key)
        if raw:
            return str(raw).strip().lower()
    return ""


def filter_lock_devices(
    devices: list[dict[str, Any]],
    categories: frozenset[str] = SUPPORTED_LOCK_CATEGORIES,
) -> list[dict[str, Any]]:
    """Keep devices whose category is a supported lock / videolock type."""
    out: list[dict[str, Any]] = []
    for dev in devices:
        if not isinstance(dev, dict):
            continue
        category = device_category(dev)
        device_id = str(dev.get("id") or "").strip()
        if not device_id or category not in categories:
            continue
        out.append(dev)
    out.sort(
        key=lambda d: (
            str(d.get("name") or "").lower(),
            str(d.get("id") or ""),
        )
    )
    return out


def format_device_option(dev: dict[str, Any]) -> str:
    """Human label for config-flow dropdown: Name (category) — id."""
    name = str(dev.get("name") or "Device").strip() or "Device"
    category = device_category(dev) or "?"
    device_id = str(dev.get("id") or "").strip()
    online = dev.get("online")
    suffix = ""
    if online is False:
        suffix = " [offline]"
    elif online is True:
        suffix = " [online]"
    return f"{name} ({category}) — {device_id}{suffix}"


def build_signed_path(base: str, params: dict[str, Any]) -> str:
    """Build path?query with params sorted alphabetically (required by Tuya sign)."""
    items = [
        f"{key}={value}"
        for key, value in sorted(params.items(), key=lambda kv: str(kv[0]))
    ]
    if not items:
        return base
    return f"{base}?{'&'.join(items)}"


def _dp_keys(dps: list[Any]) -> set[str]:
    """Extract DP codes from a records `dps` list of {code: value} dicts."""
    keys: set[str] = set()
    for item in dps or []:
        if isinstance(item, dict):
            keys.update(str(k) for k in item)
    return keys


def infer_is_locked(status: dict[str, Any]) -> bool | None:
    """Infer locked state from status DPs.

    Returns True if locked, False if unlocked, None if unknown.
    When automatic_lock is enabled, treat as locked (Wi-Fi videolocks often
    freeze lock_motor_state).
    """
    if status.get(DP_AUTOMATIC_LOCK) is True:
        return True
    motor = status.get(DP_LOCK_MOTOR_STATE)
    if motor is None:
        return None
    # lock_motor_state True typically means unlocked/open on Tuya locks
    return not bool(motor)


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
        # device_id → (expires_at, error_msg) for stream allocate failures
        self._stream_fail_cache: dict[str, tuple[float, str]] = {}

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

    async def async_get_device_info(self, device_id: str) -> dict[str, Any]:
        """Fetch device metadata (name, online, product_name). Raises TuyaApiError."""
        resp = await self._request("GET", DEVICE_ENDPOINT.format(device_id=device_id))
        if not resp.get("success"):
            raise TuyaApiError(
                f"device info: {resp.get('msg')}",
                code=resp.get("code"),
            )
        result = resp.get("result")
        return result if isinstance(result, dict) else {}

    @staticmethod
    def _extract_device_list(resp: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize various Tuya list payloads into a list of device dicts."""
        if not resp.get("success"):
            return []
        result = resp.get("result")
        if isinstance(result, list):
            return [d for d in result if isinstance(d, dict)]
        if isinstance(result, dict):
            for key in ("devices", "list"):
                raw = result.get(key)
                if isinstance(raw, list):
                    return [d for d in raw if isinstance(d, dict)]
        return []

    async def async_list_devices(self) -> list[dict[str, Any]]:
        """List devices linked to the Cloud project / Smart Life app.

        Order matches working community lock integrations:
        1) ``/v1.0/iot-01/associated-users/devices`` (app-linked devices)
        2) ``/v1.0/users/{uid}/devices``
        3) ``/v1.0/iot-03/devices`` (IoT Core page)
        """
        await self._ensure_token()
        attempts: list[str] = [
            "/v1.0/iot-01/associated-users/devices",
            "/v1.0/iot-01/associated-users/devices?size=100",
        ]
        if self._uid:
            attempts.append(f"/v1.0/users/{self._uid}/devices")
        attempts.append("/v1.0/iot-03/devices?page_size=100&page_no=1")

        last_err: str | None = None
        for path in attempts:
            resp = await self._request("GET", path)
            if not resp.get("success"):
                last_err = f"{path}: {resp.get('msg')} ({resp.get('code')})"
                _LOGGER.warning("Device list attempt failed — %s", last_err)
                continue
            devices = self._extract_device_list(resp)
            cats = sorted(
                {
                    str(d.get("category") or "")
                    for d in devices
                    if isinstance(d, dict)
                }
            )
            _LOGGER.info(
                "Device list via %s → %s device(s), categories=%s",
                path.split("?")[0],
                len(devices),
                cats,
            )
            if devices:
                return devices

        if last_err:
            _LOGGER.error("All device list endpoints failed/empty. Last: %s", last_err)
        return []

    async def async_list_lock_devices(self) -> list[dict[str, Any]]:
        """List lock/videolock devices; if category filter is empty, return all.

        Returning the unfiltered list lets the user still pick the SL-CE when
        Cloud reports an unexpected category code.
        """
        all_devices = await self.async_list_devices()
        locks = filter_lock_devices(all_devices)
        if all_devices and not locks:
            cats = sorted(
                {device_category(d) or "?" for d in all_devices if isinstance(d, dict)}
            )
            _LOGGER.warning(
                "Found %s Cloud device(s) but none match lock categories %s; "
                "saw: %s — offering full list in config flow",
                len(all_devices),
                sorted(SUPPORTED_LOCK_CATEGORIES),
                cats,
            )
            return all_devices
        return locks

    async def async_get_device(self, device_id: str) -> dict[str, Any] | None:
        """Fetch device metadata; return None on soft failure (coordinator)."""
        try:
            return await self.async_get_device_info(device_id)
        except TuyaApiError as err:
            _LOGGER.warning("Device info failed: %s", err)
            return None

    async def async_get_status(self, device_id: str) -> dict[str, Any]:
        """Return DP code→value map (empty dict on soft Cloud failures)."""
        paths = (
            STATUS_ENDPOINT.format(device_id=device_id),
            f"/v1.0/devices/{device_id}/status",
        )
        last_err: str | None = None
        for path in paths:
            resp = await self._request("GET", path)
            if not resp.get("success"):
                last_err = f"{resp.get('msg')} ({resp.get('code')})"
                _LOGGER.debug("Status via %s failed: %s", path, last_err)
                continue
            raw = resp.get("result")
            if isinstance(raw, list):
                return parse_status_list(raw)
            return {}
        _LOGGER.warning(
            "Could not read status for %s — continuing with empty DPs: %s",
            device_id,
            last_err,
        )
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
        locked = infer_is_locked(status)
        if locked is None:
            return None
        return not locked

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
    ) -> tuple[str | None, str | None]:
        """Allocate a live stream URL (hls/rtsp/…).

        Returns ``(url, error_message)``. ``error_message`` is set when the
        Cloud call fails (e.g. IoT Video Live Stream not subscribed).

        Tuya docs: POST /v1.0/devices/{device_id}/stream/actions/allocate
        Body: {"type": "hls"|"rtsp"|...}
        """
        stype = (stream_type or "hls").strip().lower()
        path = STREAM_ALLOCATE_ENDPOINT.format(device_id=device_id)
        resp = await self._request("POST", path, {"type": stype})
        if not resp.get("success"):
            msg = str(resp.get("msg") or "allocate failed")
            code = resp.get("code")
            detail = f"{msg}" + (f" ({code})" if code is not None else "")
            _LOGGER.warning(
                "Stream allocate (%s) failed for %s: %s",
                stype,
                device_id,
                detail,
            )
            return None, detail
        result = resp.get("result") or {}
        url = result.get("url") if isinstance(result, dict) else None
        if not url:
            return None, "allocate returned empty url"
        return str(url), None

    async def async_allocate_stream_preferred(
        self,
        device_id: str,
        preferred: str | None = None,
    ) -> tuple[str | None, str | None, str | None]:
        """Try preferred type then fallbacks.

        Returns ``(url, type_used, error_message)``.
        If the Cloud project lacks *IoT Video Live Stream*, all types fail with
        the same permission error — stop after the first such failure.
        """
        # Short negative cache: HA retries stream/snapshot aggressively.
        cache_key = f"stream_fail:{device_id}"
        cached = getattr(self, "_stream_fail_cache", None)
        if isinstance(cached, dict):
            entry = cached.get(cache_key)
            if (
                isinstance(entry, tuple)
                and len(entry) == 2
                and time.time() < float(entry[0])
            ):
                return None, None, str(entry[1])

        order: list[str] = []
        if preferred:
            order.append(preferred.strip().lower())
        for item in STREAM_TYPE_PREFERENCE:
            if item not in order:
                order.append(item)

        last_err: str | None = None
        for stype in order:
            url, err = await self.async_allocate_stream(device_id, stype)
            if url:
                return url, stype, None
            last_err = err
            # Same Cloud subscription gate for every type — no point hammering.
            if err and (
                "not subscribed" in err.lower()
                or "no permissions" in err.lower()
            ):
                break

        if last_err:
            if not hasattr(self, "_stream_fail_cache") or not isinstance(
                getattr(self, "_stream_fail_cache"), dict
            ):
                self._stream_fail_cache = {}
            # 10 minutes — user needs to subscribe the API, not retry.
            self._stream_fail_cache[cache_key] = (time.time() + 600.0, last_err)
        return None, None, last_err

    async def async_get_unlock_logs(
        self,
        device_id: str,
        page_no: int = 1,
        page_size: int = LOG_PAGE_SIZE,
        start_time: int = 0,
        end_time: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch unlock history logs from Tuya Cloud.

        Returns list of log entries with: update_time, status (code, value),
        unlock_name, user_id, nick_name.
        """
        now_ms = int(time.time() * 1000)
        if end_time == 0:
            end_time = now_ms
        if start_time == 0:
            # Last 24 hours by default
            start_time = now_ms - (24 * 60 * 60 * 1000)

        path = build_signed_path(
            OPEN_LOGS_ENDPOINT.format(device_id=device_id),
            {
                "end_time": end_time,
                "page_no": page_no,
                "page_size": page_size,
                "start_time": start_time,
            },
        )
        resp = await self._request("GET", path)
        if not resp.get("success"):
            _LOGGER.debug(
                "Unlock logs failed for %s: %s",
                device_id,
                resp.get("msg"),
            )
            return []
        result = resp.get("result") or {}
        logs = result.get("logs") if isinstance(result, dict) else []
        return logs if isinstance(logs, list) else []

    async def async_get_alarm_logs(
        self,
        device_id: str,
        page_no: int = 1,
        page_size: int = LOG_PAGE_SIZE,
        start_time: int = 0,
        end_time: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch alarm history logs from Tuya Cloud.

        Returns list of alarm entries with: update_time, alarm_type, etc.
        """
        now_ms = int(time.time() * 1000)
        if end_time == 0:
            end_time = now_ms
        if start_time == 0:
            start_time = now_ms - (24 * 60 * 60 * 1000)

        path = build_signed_path(
            ALARM_LOGS_ENDPOINT.format(device_id=device_id),
            {
                "end_time": end_time,
                "page_no": page_no,
                "page_size": page_size,
                "start_time": start_time,
            },
        )
        resp = await self._request("GET", path)
        if not resp.get("success"):
            _LOGGER.debug(
                "Alarm logs failed for %s: %s",
                device_id,
                resp.get("msg"),
            )
            return []
        result = resp.get("result") or {}
        logs = result.get("logs") if isinstance(result, dict) else []
        return logs if isinstance(logs, list) else []

    async def async_get_records(
        self,
        device_id: str,
        dp_codes: str = "alarm_lock,doorbell,unlock_card,unlock_face,unlock_fingerprint,unlock_password",
        page_no: int = 1,
        page_size: int = LOG_PAGE_SIZE,
        start_time: int = 0,
        end_time: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch combined alert + unlock records (Wi-Fi access control).

        This endpoint is better for videolock as it returns both unlock and
        alarm records with timestamps and record_type.

        Query params MUST be alphabetically sorted for Tuya HMAC sign.
        """
        now_ms = int(time.time() * 1000)
        if end_time == 0:
            end_time = now_ms
        if start_time == 0:
            start_time = now_ms - (24 * 60 * 60 * 1000)

        path = build_signed_path(
            RECORDS_ENDPOINT.format(device_id=device_id),
            {
                "end_time": end_time,
                "page_no": page_no,
                "page_size": page_size,
                "start_time": start_time,
                "target_standard_dp_codes": dp_codes,
            },
        )
        resp = await self._request("GET", path)
        if not resp.get("success"):
            _LOGGER.warning(
                "Records failed for %s: %s (%s)",
                device_id,
                resp.get("msg"),
                resp.get("code"),
            )
            return []
        result = resp.get("result") or {}
        records = result.get("records") if isinstance(result, dict) else []
        return records if isinstance(records, list) else []

    async def async_get_latest_events(
        self,
        device_id: str,
        since_timestamp: int = 0,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Get unlock, alarm and doorbell events since a timestamp.

        Returns (unlock_events, alarm_events, doorbell_events).
        Doorbell often appears as record_type=alarm with dps doorbell=true.
        Unlock face/fingerprint keep sticky DP values — records are required.
        """
        now_ms = int(time.time() * 1000)
        if since_timestamp == 0:
            since_timestamp = now_ms - (5 * 60 * 1000)

        unlock_events: list[dict[str, Any]] = []
        alarm_events: list[dict[str, Any]] = []
        doorbell_events: list[dict[str, Any]] = []

        records = await self.async_get_records(
            device_id,
            start_time=since_timestamp,
            end_time=now_ms,
        )
        for record in records:
            ts = int(record.get("gmt_create") or record.get("update_time") or 0)
            if ts <= since_timestamp:
                continue
            record_type = record.get("record_type", "normal")
            dps = record.get("dps") or []
            keys = _dp_keys(dps if isinstance(dps, list) else [])
            event = {
                "timestamp_ms": ts,
                "record_id": record.get("record_id"),
                "record_type": record_type,
                "user_id": record.get("user_id"),
                "user_name": record.get("user_name"),
                "unlock_name": record.get("unlock_name"),
                "dps": dps,
            }
            if "doorbell" in keys:
                doorbell_events.append(event)
            elif any(k.startswith("unlock_") for k in keys):
                unlock_events.append(event)
            elif record_type == "alarm" or "alarm_lock" in keys:
                alarm_events.append(event)
            else:
                unlock_events.append(event)

        # Fallback: legacy open-logs if records empty
        if not unlock_events and not alarm_events and not doorbell_events:
            unlock_logs = await self.async_get_unlock_logs(
                device_id, start_time=since_timestamp, end_time=now_ms
            )
            for log in unlock_logs:
                ts = int(log.get("update_time") or 0)
                if ts <= since_timestamp:
                    continue
                status = log.get("status") or {}
                if isinstance(status, list) and status:
                    status = status[0] if isinstance(status[0], dict) else {}
                unlock_events.append(
                    {
                        "timestamp_ms": ts,
                        "record_type": "normal",
                        "unlock_code": status.get("code") if isinstance(status, dict) else None,
                        "unlock_value": status.get("value") if isinstance(status, dict) else None,
                        "unlock_name": log.get("unlock_name"),
                        "user_id": log.get("user_id"),
                        "user_name": log.get("nick_name"),
                    }
                )

            alarm_logs = await self.async_get_alarm_logs(
                device_id, start_time=since_timestamp, end_time=now_ms
            )
            for log in alarm_logs:
                ts = int(log.get("update_time") or 0)
                if ts <= since_timestamp:
                    continue
                alarm_events.append(
                    {
                        "timestamp_ms": ts,
                        "record_type": "alarm",
                        "alarm_type": log.get("alarm_type"),
                        "details": log,
                    }
                )

        return unlock_events, alarm_events, doorbell_events
