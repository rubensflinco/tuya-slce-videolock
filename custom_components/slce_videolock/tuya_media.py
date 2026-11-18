"""Download + decrypt Tuya smart-lock event cover images (AES-CBC).

Format documented at:
https://developer.tuya.com/en/docs/cloud/doorlock-api-photovideos

Header layout: 4 bytes placeholder | 16 bytes IV | 44 bytes placeholder | ciphertext
Cipher: AES/CBC/PKCS5Padding, key = ``file_key`` UTF-8 bytes.
"""

from __future__ import annotations

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

_HEADER_SKIP = 4
_IV_LEN = 16
_MID_SKIP = 44
_PAYLOAD_OFFSET = _HEADER_SKIP + _IV_LEN + _MID_SKIP  # 64

# Docs sample truncates host as "...cos.tuyacn.com6" — strip junk after TLD
_BASE_HOST_RE = re.compile(
    r"^(https?://[^\s/?]+?\.(?:com|cn|net|us|eu|in))(?:\d+)?/?$",
    re.IGNORECASE,
)
_SIGNED_OR_FILE_RE = re.compile(
    r"(\?|\.(?:jpe?g|png|mp4)(?:$|\?))",
    re.IGNORECASE,
)


def decrypt_tuya_lock_media(encrypted: bytes, file_key: str) -> bytes:
    """Decrypt a Tuya door-lock media blob into image bytes."""
    if not encrypted:
        raise ValueError("empty media payload")
    # Already a plain JPEG/PNG (some CDNs return plaintext)
    if encrypted[:2] == b"\xff\xd8" or encrypted[:8] == b"\x89PNG\r\n\x1a\n":
        return encrypted
    if len(encrypted) <= _PAYLOAD_OFFSET:
        raise ValueError("media payload shorter than encryption header")
    if not file_key:
        raise ValueError("missing file_key")

    iv = encrypted[_HEADER_SKIP : _HEADER_SKIP + _IV_LEN]
    ciphertext = encrypted[_PAYLOAD_OFFSET:]
    key = _normalize_aes_key(file_key)

    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7
    except ImportError as err:
        raise RuntimeError(
            "cryptography package required to decrypt Tuya lock media"
        ) from err

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    if not plain:
        raise ValueError("decrypted media is empty")
    return plain


def _normalize_aes_key(file_key: str) -> bytes:
    """AES key from Tuya file_key (usually 16 ASCII chars)."""
    key = file_key.encode("utf-8")
    if len(key) in (16, 24, 32):
        return key
    if len(key) < 16:
        return key.ljust(16, b"\0")
    return key[:16]


def is_direct_download_url(url: str) -> bool:
    """True when URL looks ready to GET (signed or ends with media extension)."""
    return bool(url and _SIGNED_OR_FILE_RE.search(url))


def normalize_storage_base_url(url: str) -> str:
    """Fix truncated COS hosts from Tuya samples (``.com6`` → ``.com``)."""
    url = (url or "").strip()
    if not url:
        return ""
    match = _BASE_HOST_RE.match(url)
    if match:
        return match.group(1)
    return url.rstrip("/")


def compose_storage_url(
    *,
    file_url: str = "",
    file_path: str = "",
    bucket: str = "",
) -> str | None:
    """Build a downloadable URL from Tuya media fields.

    ``latest/media/url`` often returns a *base* ``file_url`` plus ``file_path``.
    Operate-records / initiative often return empty ``file_url`` with bucket+path
    — those need OpenAPI resolve (``movement-configs``); this is a fallback join.
    """
    url = (file_url or "").strip()
    path = (file_path or "").strip()
    bucket = (bucket or "").strip()

    if is_direct_download_url(url):
        return url

    base = normalize_storage_base_url(url) if url else ""
    if base and path:
        if path.lstrip("/") not in base:
            return f"{base}/{path.lstrip('/')}"
        return base

    if bucket and path:
        # Prefer US first (RuGiu AZ); resolve API is more reliable than guessing
        for suffix in (
            "cos.tuyaus.com",
            "cos.tuyaeu.com",
            "cos.tuyacn.com",
            "cos.ap-shanghai.myqcloud.com",
            "cos.ap-hongkong.myqcloud.com",
        ):
            return f"https://{bucket}.{suffix}/{path.lstrip('/')}"
    return base or None


def needs_url_resolve(info: dict[str, str]) -> bool:
    """Whether bucket+path should be resolved via OpenAPI before download.

    Signed album URLs contain ``?`` and are ready. Guesses from bucket+path
    (even if they end in ``.jpg``) still need ``movement-configs`` because the
    COS region host is often wrong.
    """
    url = (info.get("file_url") or "").strip()
    if "?" in url:
        return False
    return bool(
        (info.get("bucket") or "").strip() and (info.get("file_path") or "").strip()
    )


def media_info_from_dict(raw: Any) -> dict[str, str] | None:
    """Normalize a media_info / album entry into download fields.

    Returns keys: file_url (may be empty until resolved), file_key, bucket, file_path.
    """
    if not isinstance(raw, dict):
        return None
    url = str(
        raw.get("file_url")
        or raw.get("fileUrl")
        or raw.get("media_url")
        or raw.get("mediaUrl")
        or ""
    ).strip()
    key = str(
        raw.get("file_key")
        or raw.get("fileKey")
        or raw.get("media_key")
        or raw.get("mediaKey")
        or ""
    ).strip()
    path = str(
        raw.get("file_path")
        or raw.get("filePath")
        or raw.get("media_path")
        or raw.get("mediaPath")
        or ""
    ).strip()
    bucket = str(
        raw.get("bucket")
        or raw.get("media_bucket")
        or raw.get("mediaBucket")
        or ""
    ).strip()

    # initiative_message / IPC style: {"bucket":"...","files":[[path,key],...]}
    files = raw.get("files")
    if isinstance(files, list) and files and not path:
        first = files[0]
        if isinstance(first, (list, tuple)) and len(first) >= 1:
            path = str(first[0] or "").strip()
            if len(first) >= 2 and not key:
                key = str(first[1] or "").strip()

    composed = compose_storage_url(file_url=url, file_path=path, bucket=bucket)
    if not key:
        return None
    if not composed and not (bucket and path):
        return None
    return {
        "file_url": composed or "",
        "file_key": key,
        "bucket": bucket,
        "file_path": path,
    }


def extract_media_from_initiative(payload: dict[str, Any]) -> dict[str, str] | None:
    """Pull bucket/path/key from an initiative_message payload if present."""
    if not isinstance(payload, dict):
        return None
    for candidate in (
        payload,
        payload.get("ext") if isinstance(payload.get("ext"), dict) else None,
        payload.get("data") if isinstance(payload.get("data"), dict) else None,
        payload.get("file") if isinstance(payload.get("file"), dict) else None,
    ):
        if not candidate:
            continue
        info = media_info_from_dict(candidate)
        if info:
            return info
    return None


def pick_album_entry(
    albums: list[dict[str, Any]],
    *,
    kind: str,
    event_types: set[int],
    around_ts_ms: int | None,
    window_seconds: int,
) -> dict[str, str] | None:
    """Pick the best album cover for an event kind / time window."""
    del kind  # reserved for future filtering
    candidates: list[tuple[int, dict[str, str]]] = []
    for item in albums:
        if not isinstance(item, dict):
            continue
        try:
            event_type = int(item.get("event_type", item.get("eventType", -1)))
        except (TypeError, ValueError):
            continue
        if event_types and event_type not in event_types:
            continue
        media = media_info_from_dict(item)
        if not media:
            continue
        upload = item.get("upload_time", item.get("uploadTime"))
        try:
            upload_s = int(upload)
        except (TypeError, ValueError):
            upload_s = 0
        score = upload_s
        if around_ts_ms and upload_s:
            delta = abs(around_ts_ms // 1000 - upload_s)
            if delta > window_seconds:
                continue
            score = -delta
        candidates.append((score, media))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]
