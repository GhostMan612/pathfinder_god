# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Zero-config LAN discovery — the hub announces itself via mDNS/DNS-SD.

The phone (Spoke) browses for `_pathfindergod._tcp.local` instead of asking
a non-technical user to type an IP. TXT record carries version + model so
the app can show "Pathfinder God Hub v0.1.0 (phi4-mini)" in the picker.

Degrades gracefully: if `zeroconf` is not installed, this module is a no-op
and the hub runs normally (manual IP entry still works).
"""
from __future__ import annotations

import logging
import socket

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_pathfindergod._tcp.local."

_advertiser = None


def _service_name() -> str:
    host = socket.gethostname().split(".")[0]
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in host)[:32]
    return f"PathfinderGod-{safe}.{SERVICE_TYPE}"


def start_advertisement(port: int, version: str, model: str) -> bool:
    """Start the mDNS advertisement in a background thread. Returns True if live."""
    global _advertiser
    if _advertiser is not None:
        return True
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except ImportError:
        logger.info("zeroconf not installed — LAN auto-discovery disabled (manual IP still works)")
        return False

    try:
        zc = Zeroconf()
        addresses = _local_ipv4_addresses()
        if not addresses:
            logger.warning("No LAN IPv4 found — skipping mDNS advertisement")
            zc.close()
            return False
        info = ServiceInfo(
            SERVICE_TYPE,
            _service_name(),
            addresses=addresses,
            port=port,
            properties={
                b"version": version.encode("utf-8", "replace"),
                b"model": model.encode("utf-8", "replace"),
                b"app": b"pathfinder_god",
            },
        )
        zc.register_service(info)
        _advertiser = (zc, info)
        logger.info(f"mDNS advertising {_service_name()} on :{port} ({len(addresses)} addr)")
        return True
    except Exception as e:
        logger.warning(f"mDNS advertisement failed (hub still runs): {e}")
        return False


def stop_advertisement() -> None:
    global _advertiser
    if _advertiser is None:
        return
    zc, info = _advertiser
    _advertiser = None
    try:
        zc.unregister_service(info)
    except Exception:
        pass
    try:
        zc.close()
    except Exception:
        pass


def _local_ipv4_addresses() -> list[bytes]:
    """All non-loopback LAN IPv4s, packed for zeroconf."""
    found: set[str] = set()
    try:
        for fam, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None):
            if fam == socket.AF_INET and isinstance(sockaddr, tuple):
                ip = sockaddr[0]
                if not ip.startswith("127."):
                    found.add(ip)
    except socket.gaierror:
        pass
    if not found:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if not ip.startswith("127."):
                    found.add(ip)
        except OSError:
            pass
    packed = []
    for ip in sorted(found):
        try:
            packed.append(socket.inet_aton(ip))
        except OSError:
            continue
    return packed
