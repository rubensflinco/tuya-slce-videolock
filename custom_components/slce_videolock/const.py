"""Constants for SL-CE Videolock."""

from __future__ import annotations

DOMAIN = "slce_videolock"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_DEVICE_ID = "device_id"
CONF_REGION = "region"
CONF_DEVICE_NAME = "device_name"
CONF_STREAM_TYPE = "stream_type"

# Production RuGiu device (docs/device-sl-ce.md)
DEFAULT_DEVICE_ID = "eba0b0f3d9b38977ed8b0a"
DEFAULT_REGION = "us"
DEFAULT_STREAM_TYPE = "hls"
DEFAULT_AUTO_LOCK_DELAY = 3
UPDATE_INTERVAL_SECONDS = 60

# OpenAPI hosts (Smart Home cloud projects)
API_REGIONS: dict[str, str] = {
    "eu": "openapi.tuyaeu.com",
    "us": "openapi.tuyaus.com",
    "cn": "openapi.tuyacn.com",
    "in": "openapi.tuyain.com",
}

REGION_LABELS: dict[str, str] = {
    "eu": "Europe (EU)",
    "us": "Americas (US)",
    "cn": "China (CN)",
    "in": "India (IN)",
}

# Smart Lock ticket unlock (MIT pattern from nicolasglg/tuya-smart-lock)
TICKET_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/password-ticket"
DOOR_OPERATE_ENDPOINT = (
    "/v1.0/smart-lock/devices/{device_id}/password-free/door-operate"
)
STATUS_ENDPOINT = "/v1.0/devices/{device_id}/status"
DEVICE_ENDPOINT = "/v1.0/devices/{device_id}"
STREAM_ALLOCATE_ENDPOINT = "/v1.0/devices/{device_id}/stream/actions/allocate"
REMOTE_UNLOCKS_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/remote-unlocks"

# Preferred stream order for HA ffmpeg (docs: developer.tuya.com IoT Video Live Stream)
STREAM_TYPE_PREFERENCE: tuple[str, ...] = ("hls", "rtsp")

# Status DP codes (videolock / ms) — see docs/device-sl-ce.md
DP_BATTERY = "residual_electricity"
DP_DOORBELL = "doorbell"
DP_HIJACK = "hijack"
DP_UNLOCK_FINGERPRINT = "unlock_fingerprint"
DP_UNLOCK_PASSWORD = "unlock_password"
DP_UNLOCK_CARD = "unlock_card"
DP_UNLOCK_APP = "unlock_app"
DP_UNLOCK_TEMPORARY = "unlock_temporary"
DP_UNLOCK_REQUEST = "unlock_request"
DP_ALARM_LOCK = "alarm_lock"
DP_AUTO_LOCK_TIME = "auto_lock_time"
DP_AUTOMATIC_LOCK = "automatic_lock"
DP_LOCK_MOTOR_STATE = "lock_motor_state"

MANUFACTURER = "Novadigital / Tuya"
MODEL = "SL-CE Elegance (videolock)"
DEVICE_NAME = "Fechadura Inteligente SL-CE (Wi-Fi)"
DEFAULT_DEVICE_NAME = DEVICE_NAME

# Reference integrations (study only — do not import at runtime)
REF_XTEND_TUYA = "https://github.com/azerty9971/xtend_tuya"
REF_TUYA_SMART_LOCK = "https://github.com/nicolasglg/tuya-smart-lock"
REF_TUYA_LOCK_MONITOR = "https://github.com/crestall/ha-tuya-lock-monitor"
TUYA_STREAM_DOCS = (
    "https://developer.tuya.com/en/docs/cloud/iot-video-live-stream?id=Kaiuybxmi136f"
)
