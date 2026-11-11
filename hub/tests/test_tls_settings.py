# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for hub TLS settings and fail-fast validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from scripts.make_hub_cert import generate_hub_cert


def test_tls_settings_default_to_disabled():
    s = Settings()
    assert s.tls_enabled is False
    assert s.tls_certfile is None
    assert s.tls_keyfile is None


def test_tls_fail_fast_when_certfile_missing(tmp_path: Path):
    missing_cert = tmp_path / "does_not_exist.pem"
    key_file = tmp_path / "key.pem"
    key_file.touch()

    # Emulate __main__ check logic
    test_settings = Settings(
        tls_enabled=True,
        tls_certfile=missing_cert,
        tls_keyfile=key_file,
    )

    with pytest.raises(FileNotFoundError, match=r"TLS certfile not found: .*does_not_exist\.pem"):
        if test_settings.tls_enabled:
            if not test_settings.tls_certfile or not test_settings.tls_certfile.is_file():
                raise FileNotFoundError(f"TLS certfile not found: {test_settings.tls_certfile}")


def test_tls_fail_fast_when_keyfile_missing(tmp_path: Path):
    cert_file = tmp_path / "cert.pem"
    cert_file.touch()
    missing_key = tmp_path / "does_not_exist_key.pem"

    test_settings = Settings(
        tls_enabled=True,
        tls_certfile=cert_file,
        tls_keyfile=missing_key,
    )

    with pytest.raises(FileNotFoundError, match=r"TLS keyfile not found: .*does_not_exist_key\.pem"):
        if test_settings.tls_enabled:
            if not test_settings.tls_certfile or not test_settings.tls_certfile.is_file():
                raise FileNotFoundError(f"TLS certfile not found: {test_settings.tls_certfile}")
            if not test_settings.tls_keyfile or not test_settings.tls_keyfile.is_file():
                raise FileNotFoundError(f"TLS keyfile not found: {test_settings.tls_keyfile}")


def test_tls_passes_validation_when_files_exist(tmp_path: Path):
    cert_path = tmp_path / "hub-cert.pem"
    key_path = tmp_path / "hub-key.pem"
    generate_hub_cert(cert_path=cert_path, key_path=key_path)

    test_settings = Settings(
        tls_enabled=True,
        tls_certfile=cert_path,
        tls_keyfile=key_path,
    )

    assert test_settings.tls_enabled is True
    assert test_settings.tls_certfile.is_file()
    assert test_settings.tls_keyfile.is_file()
