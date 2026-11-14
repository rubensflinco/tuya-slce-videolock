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
# Official HA Tuya uses RTSP; Tuya HLS often expires / breaks HA stream worker
DEFAULT_STREAM_TYPE = "rtsp"
DEFAULT_AUTO_LOCK_DELAY = 3

# Polling: more aggressive to catch transient events (doorbell, alarms)
# Cloud rate limit is ~1 req/s per device; 15s is safe and catches most pulses
UPDATE_INTERVAL_SECONDS = 15

# Auto-reset delay for sticky binary sensors (doorbell, hijack)
# ha-tuya-lock-monitor uses 1s; we use 2s for safety margin
PULSE_RESET_SECONDS = 2.0

# How many recent log entries to fetch per poll (to detect new events)
LOG_PAGE_SIZE = 10

# OpenAPI hosts (Smart Home cloud projects)
# Platform codes AY/AZ map to CN/US data centers (see platform.tuya.com ?region=)
API_REGIONS: dict[str, str] = {
    "eu": "openapi.tuyaeu.com",
    "us": "openapi.tuyaus.com",
    "cn": "openapi.tuyacn.com",
    "in": "openapi.tuyain.com",
    "ay": "openapi.tuyacn.com",
    "az": "openapi.tuyaus.com",
}

# Dropdown values stored in config entry (normalized lowercase)
REGION_LABELS: dict[str, str] = {
    "us": "Americas / Américas (US · AZ)",
    "eu": "Europe / Europa (EU)",
    "cn": "China (CN · AY)",
    "in": "India / Índia (IN)",
}

TUYA_PROJECT_URL = (
    "https://platform.tuya.com/cloud/basic"
    "?id=p1630510951574getp4q&region=AZ&toptab=project"
)
# Same place Xtend documents for camera enablement
TUYA_CLOUD_SERVICES_URL = "https://platform.tuya.com/cloud"

# Smart Lock ticket unlock (MIT pattern from nicolasglg/tuya-smart-lock)
TICKET_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/password-ticket"
DOOR_OPERATE_ENDPOINT = (
    "/v1.0/smart-lock/devices/{device_id}/password-free/door-operate"
)
# Same path as tuya-smart-lock (IoT Core status); /v1.0/devices/.../status often fails
STATUS_ENDPOINT = "/v1.0/iot-03/devices/{device_id}/status"
DEVICE_ENDPOINT = "/v1.0/devices/{device_id}"
STREAM_ALLOCATE_ENDPOINT = "/v1.0/devices/{device_id}/stream/actions/allocate"
REMOTE_UNLOCKS_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/remote-unlocks"

# Lock event logs endpoints (Tuya Cloud API)
# See: https://developer.tuya.com/en/docs/cloud/doorlock-api-record
OPEN_LOGS_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/open-logs"
ALARM_LOGS_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/alarm-logs"
# Combined records endpoint (Wi-Fi access control devices)
RECORDS_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/records"

# Preferred stream order for HA ffmpeg (docs: developer.tuya.com IoT Video Live Stream)
# Order used after the config preferred type (docs/camera-todo.md)
STREAM_TYPE_PREFERENCE: tuple[str, ...] = ("rtsp", "hls")

# Tuya product categories this integration supports (config-flow device picker)
# Align with tuya-smart-lock + videolock (SL-CE)
SUPPORTED_LOCK_CATEGORIES: frozenset[str] = frozenset(
    {
        "videolock",
        "photolock",
        "ms",
        "mk",
        "jtmsbh",
        "jtmspro",
        "gyms",
        "hotelms",
    }
)

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

# Additional unlock method DPs (videolock / SL-CE)
DP_UNLOCK_FACE = "unlock_face"
DP_UNLOCK_KEY = "unlock_key"
DP_UNLOCK_DYNAMIC = "unlock_dynamic"
DP_UNLOCK_PHONE_REMOTE = "unlock_phone_remote"
DP_UNLOCK_FINGER_VEIN = "unlock_finger_vein"
DP_UNLOCK_HAND = "unlock_hand"
DP_UNLOCK_VOICE = "unlock_voice"
DP_UNLOCK_OFFLINE_PASSWORD = "unlock_offline_password"
DP_UNLOCK_IDENTITY_CARD = "unlock_identity_card"
DP_UNLOCK_EMERGENCY = "unlock_emergency"

# All unlock DP codes for event detection
ALL_UNLOCK_DPS: tuple[str, ...] = (
    DP_UNLOCK_FINGERPRINT,
    DP_UNLOCK_PASSWORD,
    DP_UNLOCK_CARD,
    DP_UNLOCK_APP,
    DP_UNLOCK_TEMPORARY,
    DP_UNLOCK_FACE,
    DP_UNLOCK_KEY,
    DP_UNLOCK_DYNAMIC,
    DP_UNLOCK_PHONE_REMOTE,
    DP_UNLOCK_FINGER_VEIN,
    DP_UNLOCK_HAND,
    DP_UNLOCK_VOICE,
    DP_UNLOCK_OFFLINE_PASSWORD,
    DP_UNLOCK_IDENTITY_CARD,
    DP_UNLOCK_EMERGENCY,
)

# Event types for HA event platform
EVENT_TYPE_DOORBELL = "ring"
EVENT_TYPE_ALARM = "alarm"
EVENT_TYPE_HIJACK = "duress"
EVENT_TYPE_UNLOCK = "unlock"

# Alarm types (from alarm_lock DP values)
ALARM_TYPES: tuple[str, ...] = (
    "wrong_finger",
    "wrong_password",
    "wrong_card",
    "wrong_face",
    "pry",
    "low_battery",
    "lock_stuck",
    "multiple_failures",
    "tamper",
    "forced_open",
)

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
