"""Download + decrypt Tuya smart-lock event cover images (AES-CBC).

Format documented at:
https://developer.tuya.com/en/docs/cloud/doorlock-api-photovideos

Header layout: 4 bytes placeholder | 16 bytes IV | 44 bytes placeholder | ciphertext
Cipher: AES/CBC/PKCS5Padding, key = ``file_key`` UTF-8 bytes.
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

_HEADER_SKIP = 4
_IV_LEN = 16
_MID_SKIP = 44
_PAYLOAD_OFFSET = _HEADER_SKIP + _IV_LEN + _MID_SKIP  # 64


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
    # Pad / truncate to AES-128 if Cloud returns an odd length
    if len(key) < 16:
        return key.ljust(16, b"\0")
    return key[:16]


def media_info_from_dict(raw: Any) -> dict[str, str] | None:
    """Normalize a media_info / album entry into url+key fields."""
    if not isinstance(raw, dict):
        return None
    url = (
        raw.get("file_url")
        or raw.get("fileUrl")
        or raw.get("media_url")
        or raw.get("mediaUrl")
        or ""
    )
    key = (
        raw.get("file_key")
        or raw.get("fileKey")
        or raw.get("media_key")
        or raw.get("mediaKey")
        or ""
    )
    path = raw.get("file_path") or raw.get("filePath") or ""
    bucket = raw.get("bucket") or raw.get("media_bucket") or raw.get("mediaBucket") or ""
    url = str(url).strip()
    key = str(key).strip()
    path = str(path).strip()
    # Some APIs return bucket base + relative path separately
    if (not url or url.endswith(".com") or url.endswith(".com/")) and path:
        base = url.rstrip("/") if url else ""
        if not base and bucket:
            base = f"https://{bucket}.cos.tuyaus.com"
        if base:
            url = f"{base}/{path.lstrip('/')}"
    if not url or not key:
        return None
    return {"file_url": url, "file_key": key}


def pick_album_entry(
    albums: list[dict[str, Any]],
    *,
    kind: str,
    event_types: set[int],
    around_ts_ms: int | None,
    window_seconds: int,
) -> dict[str, str] | None:
    """Pick the best album cover for an event kind / time window."""
    candidates: list[tuple[int, dict[str, str]]] = []
    for item in albums:
        if not isinstance(item, dict):
            continue
        try:
            event_type = int(
                item.get("event_type", item.get("eventType", -1))
            )
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
        # Prefer entries near the event time; else newest
        score = upload_s
        if around_ts_ms and upload_s:
            delta = abs(around_ts_ms // 1000 - upload_s)
            if delta > window_seconds:
                continue
            score = -delta  # closer is better (less negative when sorted reverse)
        candidates.append((score, media))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]
