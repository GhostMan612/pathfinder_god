# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Self-signed Hub TLS Certificate Generator.

Generates an RSA 2048 self-signed certificate with 10-year validity for the
Pathfinder God Hub, supporting localhost, 127.0.0.1, and detected LAN IPv4s.
Calculates and prints the OkHttp SPKI SHA-256 pin for release Spoke pinning.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from cryptography.x509.oid import NameOID

# Ensure hub package is on sys.path when script is run standalone
REPO_ROOT = Path(__file__).resolve().parents[2]
HUB_DIR = REPO_ROOT / "hub"
if str(HUB_DIR) not in sys.path:
    sys.path.insert(0, str(HUB_DIR))

from app.discovery import _local_ipv4_addresses

DEFAULT_CERT_PATH = REPO_ROOT / "data" / "tls" / "hub-cert.pem"
DEFAULT_KEY_PATH = REPO_ROOT / "data" / "tls" / "hub-key.pem"


def compute_spki_pin(public_key: rsa.RSAPublicKey) -> str:
    """Calculate the RFC 7469 / OkHttp SubjectPublicKeyInfo SHA-256 pin."""
    spki_der = public_key.public_bytes(
        encoding=Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(spki_der).digest()
    return f"sha256/{base64.b64encode(digest).decode('ascii')}"


def generate_hub_cert(
    cert_path: Path = DEFAULT_CERT_PATH,
    key_path: Path = DEFAULT_KEY_PATH,
    force: bool = False,
    extra_sans: list[str] | None = None,
) -> dict:
    """Generate self-signed certificate and private key.

    Returns a dict with certificate details and OkHttp pin string.
    Raises FileExistsError if output files exist and force is False.
    """
    cert_path = Path(cert_path).resolve()
    key_path = Path(key_path).resolve()

    if (cert_path.exists() or key_path.exists()) and not force:
        raise FileExistsError(
            f"Certificate or key already exists ({cert_path}, {key_path}). "
            "Use --force to overwrite and generate a new certificate with a new pin."
        )

    if (cert_path.exists() or key_path.exists()) and force:
        sys.stderr.write(
            "WARNING: Overwriting existing certificate and key. The old public key pin is now "
            "INVALID. Any release Spoke client using the previous pin will fail TLS handshakes "
            "until updated with the new pin.\n"
        )

    # 1. Generate RSA 2048 private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # 2. Compile SANs: localhost, 127.0.0.1, detected LAN IPs, and extra SANs
    sans: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    seen_ips = {"127.0.0.1"}

    for packed_ip in _local_ipv4_addresses():
        ip_str = socket.inet_ntoa(packed_ip)
        if ip_str not in seen_ips:
            try:
                sans.append(x509.IPAddress(ipaddress.IPv4Address(ip_str)))
                seen_ips.add(ip_str)
            except ValueError:
                pass

    if extra_sans:
        for extra in extra_sans:
            try:
                ip_obj = ipaddress.ip_address(extra)
                if str(ip_obj) not in seen_ips:
                    sans.append(x509.IPAddress(ip_obj))
                    seen_ips.add(str(ip_obj))
            except ValueError:
                sans.append(x509.DNSName(extra))

    # 3. Build certificate (10 years validity = 3650 days)
    now = datetime.now(timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Pathfinder God Hub"),
    ])
    issuer = subject  # Self-signed

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(sans),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(public_key),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # 4. Write cert and key files
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    cert_pem = cert.public_bytes(Encoding.PEM)
    cert_path.write_bytes(cert_pem)

    key_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    key_path.write_bytes(key_pem)

    try:
        key_path.chmod(0o600)
    except OSError:
        pass

    pin = compute_spki_pin(public_key)
    san_strings = [
        str(name.value) for name in sans
    ]
    expires_at = (now + timedelta(days=3650)).isoformat()

    return {
        "pin": pin,
        "cert_path": str(cert_path),
        "key_path": str(key_path),
        "expires_at": expires_at,
        "sans": san_strings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Pathfinder God Hub TLS Certificate")
    parser.add_argument(
        "--cert-out",
        type=Path,
        default=DEFAULT_CERT_PATH,
        help=f"Path for output cert PEM (default: {DEFAULT_CERT_PATH})",
    )
    parser.add_argument(
        "--key-out",
        type=Path,
        default=DEFAULT_KEY_PATH,
        help=f"Path for output private key PEM (default: {DEFAULT_KEY_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing certificate and key",
    )
    parser.add_argument(
        "--san",
        action="append",
        dest="extra_sans",
        help="Additional Subject Alternative Name (DNS or IP, can be specified multiple times)",
    )

    args = parser.parse_args()

    try:
        info = generate_hub_cert(
            cert_path=args.cert_out,
            key_path=args.key_out,
            force=args.force,
            extra_sans=args.extra_sans,
        )
    except FileExistsError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1

    print("============================================================")
    print("Pathfinder God Hub TLS Certificate Generated Successfully")
    print("============================================================")
    print(f"Cert written to: {info['cert_path']}")
    print(f"Key written to:  {info['key_path']}")
    print(f"Expires at:      {info['expires_at']}")
    print(f"SANs:            {', '.join(info['sans'])}")
    print("------------------------------------------------------------")
    print("OkHttp Certificate Pin for Spoke (HubTlsClient.kt):")
    print(f"HUB_CERT_PIN = \"{info['pin']}\"")
    print("============================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
