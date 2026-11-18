"""Unit tests for Tuya lock media decrypt helpers."""

from __future__ import annotations

import unittest

from custom_components.slce_videolock.const import SNAPSHOT_KIND_UNLOCK
from custom_components.slce_videolock.tuya_media import (
    compose_storage_url,
    decrypt_tuya_lock_media,
    extract_media_from_initiative,
    media_info_from_dict,
    needs_url_resolve,
    normalize_storage_base_url,
    pick_album_entry,
)


class TestDecryptTuyaLockMedia(unittest.TestCase):
    def test_passthrough_jpeg(self) -> None:
        jpeg = b"\xff\xd8\xff" + b"fake"
        self.assertEqual(decrypt_tuya_lock_media(jpeg, "ignored"), jpeg)

    def test_aes_roundtrip(self) -> None:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.padding import PKCS7
        except ImportError:
            self.skipTest("cryptography not installed")

        key = b"0123456789abcdef"
        iv = b"abcdefghijklmnop"
        plain = b"\xff\xd8\xff" + b"hello-tuya-lock-media!!"  # need pad length
        padder = PKCS7(128).padder()
        padded = padder.update(plain) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        enc = cipher.encryptor()
        ciphertext = enc.update(padded) + enc.finalize()
        blob = b"\x00\x00\x00\x01" + iv + (b"\x00" * 44) + ciphertext
        out = decrypt_tuya_lock_media(blob, key.decode("ascii"))
        self.assertTrue(out.startswith(b"\xff\xd8\xff"))
        self.assertIn(b"hello-tuya-lock-media", out)


class TestMediaInfoHelpers(unittest.TestCase):
    def test_media_info_from_dict(self) -> None:
        info = media_info_from_dict(
            {"file_url": "https://x/y.jpg", "file_key": "abc123abc123abcd"}
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info["file_url"], "https://x/y.jpg")

    def test_compose_truncated_host_plus_path(self) -> None:
        # Official docs sample: file_url ends with ".com6" (garbage digit)
        url = compose_storage_url(
            file_url="https://ty-cn-storage60-1254153901.cos.tuyacn.com6",
            file_path="/3039e1-30532026.jpg",
            bucket="ty-cn-storage60-1254153901",
        )
        self.assertEqual(
            url,
            "https://ty-cn-storage60-1254153901.cos.tuyacn.com/3039e1-30532026.jpg",
        )

    def test_normalize_base_url(self) -> None:
        self.assertEqual(
            normalize_storage_base_url(
                "https://ty-cn-storage60-1254153901.cos.tuyacn.com6"
            ),
            "https://ty-cn-storage60-1254153901.cos.tuyacn.com",
        )

    def test_bucket_path_needs_resolve(self) -> None:
        info = media_info_from_dict(
            {
                "bucket": "ty-us-storage",
                "file_path": "/face.jpg",
                "file_key": "0123456789abcdef",
            }
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertTrue(needs_url_resolve(info))

    def test_initiative_files_array(self) -> None:
        info = extract_media_from_initiative(
            {
                "bucket": "ty-us-storage",
                "files": [["/path/face.jpeg", "0123456789abcdef"]],
            }
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info["bucket"], "ty-us-storage")
        self.assertEqual(info["file_path"], "/path/face.jpeg")
        self.assertEqual(info["file_key"], "0123456789abcdef")

    def test_pick_album_entry_by_time(self) -> None:
        albums = [
            {
                "event_type": 11,
                "file_url": "https://old.jpg",
                "file_key": "0123456789abcdef",
                "upload_time": 1000,
            },
            {
                "event_type": 11,
                "file_url": "https://near.jpg",
                "file_key": "0123456789abcdef",
                "upload_time": 2000,
            },
        ]
        picked = pick_album_entry(
            albums,
            kind=SNAPSHOT_KIND_UNLOCK,
            event_types={11},
            around_ts_ms=2005_000,
            window_seconds=60,
        )
        self.assertIsNotNone(picked)
        assert picked is not None
        self.assertEqual(picked["file_url"], "https://near.jpg")


if __name__ == "__main__":
    unittest.main()
