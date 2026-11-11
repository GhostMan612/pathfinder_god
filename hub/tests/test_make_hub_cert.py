# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for hub/scripts/make_hub_cert.py."""
from __future__ import annotations

import ipaddress
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

from scripts.make_hub_cert import compute_spki_pin, generate_hub_cert


def test_generate_cert_creates_valid_cert_and_key(tmp_path: Path):
    cert_path = tmp_path / "test-cert.pem"
    key_path = tmp_path / "test-key.pem"

    result = generate_hub_cert(cert_path=cert_path, key_path=key_path)

    assert cert_path.is_file()
    assert key_path.is_file()
    assert result["pin"].startswith("sha256/")

    # Parse the generated cert
    cert_bytes = cert_path.read_bytes()
    cert = x509.load_pem_x509_certificate(cert_bytes)

    # Subject & issuer
    assert cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value == "Pathfinder God Hub"
    assert cert.issuer == cert.subject

    # Public key and pin match
    pubkey = cert.public_key()
    assert isinstance(pubkey, rsa.RSAPublicKey)
    assert compute_spki_pin(pubkey) == result["pin"]

    # Check SANs
    san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
    sans = san_ext.value
    dns_names = [name.value for name in sans if isinstance(name, x509.DNSName)]
    ip_addrs = [name.value for name in sans if isinstance(name, x509.IPAddress)]

    assert "localhost" in dns_names
    assert ipaddress.IPv4Address("127.0.0.1") in ip_addrs


def test_refuses_overwrite_without_force(tmp_path: Path):
    cert_path = tmp_path / "test-cert.pem"
    key_path = tmp_path / "test-key.pem"

    generate_hub_cert(cert_path=cert_path, key_path=key_path)

    with pytest.raises(FileExistsError, match="already exists"):
        generate_hub_cert(cert_path=cert_path, key_path=key_path, force=False)


def test_overwrites_with_force(tmp_path: Path):
    cert_path = tmp_path / "test-cert.pem"
    key_path = tmp_path / "test-key.pem"

    res1 = generate_hub_cert(cert_path=cert_path, key_path=key_path)
    res2 = generate_hub_cert(cert_path=cert_path, key_path=key_path, force=True)

    assert cert_path.is_file()
    assert key_path.is_file()
    # A new RSA key was generated, so the pin changes
    assert res1["pin"] != res2["pin"]


def test_extra_sans(tmp_path: Path):
    cert_path = tmp_path / "test-cert.pem"
    key_path = tmp_path / "test-key.pem"

    result = generate_hub_cert(
        cert_path=cert_path,
        key_path=key_path,
        extra_sans=["custom.lan", "10.99.88.77"],
    )

    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
    sans = san_ext.value
    dns_names = [name.value for name in sans if isinstance(name, x509.DNSName)]
    ip_addrs = [name.value for name in sans if isinstance(name, x509.IPAddress)]

    assert "custom.lan" in dns_names
    assert ipaddress.IPv4Address("10.99.88.77") in ip_addrs
    assert "custom.lan" in result["sans"]
    assert "10.99.88.77" in result["sans"]
