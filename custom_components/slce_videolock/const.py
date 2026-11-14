"""Constants for SL-CE Videolock."""

from __future__ import annotations

DOMAIN = "slce_videolock"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_DEVICE_ID = "device_id"
CONF_REGION = "region"
CONF_DEVICE_NAME = "device_name"

# Production RuGiu device (docs/device-sl-ce.md)
DEFAULT_DEVICE_ID = "eba0b0f3d9b38977ed8b0a"
# Brazil / Smart Life Americas typically uses the US OpenAPI endpoint
DEFAULT_REGION = "us"

# Human-readable region labels → OpenAPI hosts
# Aliases ay/az match older Tuya data-center codes.
API_REGIONS: dict[str, str] = {
    "eu": "openapi.tuyaeu.com",
    "us": "openapi.tuyaus.com",
    "cn": "openapi.tuyacn.com",
    "in": "openapi.tuyain.com",
    "ay": "openapi.tuyacn.com",
    "az": "openapi.tuyaus.com",
}

REGION_LABELS: dict[str, str] = {
    "eu": "Europe (EU)",
    "us": "Americas (US)",
    "cn": "China (CN)",
    "in": "India (IN)",
}

# Cloud poll interval (seconds) — status DPs + online meta
UPDATE_INTERVAL = 60
# How often to refresh device metadata (name, online, product)
META_REFRESH_SECONDS = 300
# Default auto-lock delay when DP auto_lock_time is missing
DEFAULT_AUTO_LOCK_DELAY = 5

# Smart Lock ticket / door-operate endpoints
# Pattern adapted from nicolasglg/tuya-smart-lock (MIT)
TICKET_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/password-ticket"
DOOR_OPERATE_ENDPOINT = (
    "/v1.0/smart-lock/devices/{device_id}/password-free/door-operate"
)
STATUS_ENDPOINT = "/v1.0/devices/{device_id}/status"
DEVICE_INFO_ENDPOINT = "/v1.0/devices/{device_id}"
REMOTE_UNLOCKS_ENDPOINT = "/v1.0/devices/{device_id}/door-lock/remote-unlocks"

# Status DP codes common on videolock / ms (see docs/device-sl-ce.md)
DP_BATTERY = "residual_electricity"
DP_DOORBELL = "doorbell"
DP_UNLOCK_FINGERPRINT = "unlock_fingerprint"
DP_UNLOCK_PASSWORD = "unlock_password"
DP_UNLOCK_CARD = "unlock_card"
DP_UNLOCK_APP = "unlock_app"
DP_UNLOCK_TEMPORARY = "unlock_temporary"
DP_ALARM_LOCK = "alarm_lock"
DP_LOCK_MOTOR = "lock_motor_state"
DP_AUTOMATIC_LOCK = "automatic_lock"
DP_AUTO_LOCK_TIME = "auto_lock_time"

MANUFACTURER = "Novadigital / Tuya"
MODEL = "SL-CE Elegance (videolock)"
DEFAULT_DEVICE_NAME = "Fechadura Inteligente SL-CE (Wi-Fi)"

# Reference integrations (study only — do not import at runtime)
REF_XTEND_TUYA = "https://github.com/azerty9971/xtend_tuya"
REF_TUYA_SMART_LOCK = "https://github.com/nicolasglg/tuya-smart-lock"
REF_TUYA_LOCK_MONITOR = "https://github.com/crestall/ha-tuya-lock-monitor"
