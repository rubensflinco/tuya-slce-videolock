"""Constants for SL-CE Videolock."""

DOMAIN = "slce_videolock"
CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_DEVICE_ID = "device_id"
CONF_REGION = "region"

# Production RuGiu device (docs/device-sl-ce.md)
DEFAULT_DEVICE_ID = "eba0b0f3d9b38977ed8b0a"
DEFAULT_REGION = "AY"  # adjust per Tuya project (AY/AZ/EU/US…)

# Reference integrations (do not import at runtime — study only)
REF_XTEND_TUYA = "https://github.com/azerty9971/xtend_tuya"
REF_TUYA_SMART_LOCK = "https://github.com/nicolasglg/tuya-smart-lock"
REF_TUYA_LOCK_MONITOR = "https://github.com/crestall/ha-tuya-lock-monitor"
