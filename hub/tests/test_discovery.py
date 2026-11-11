# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Tests for mDNS advertisement, including TLS TXT record flag."""
from __future__ import annotations

from app import discovery


def test_discovery_advertisement_without_tls(monkeypatch):
    monkeypatch.setattr(discovery, "_advertiser", None)
    monkeypatch.setattr(discovery, "_local_ipv4_addresses", lambda: [b"\x7f\x00\x00\x01"])

    registered_info = None

    class MockZeroconf:
        def register_service(self, info):
            nonlocal registered_info
            registered_info = info

        def close(self):
            pass

    monkeypatch.setattr("zeroconf.Zeroconf", MockZeroconf)

    success = discovery.start_advertisement(8000, "0.1.0", "phi4-mini", tls=False)
    assert success is True
    assert registered_info is not None
    assert b"tls" not in registered_info.properties
    assert registered_info.properties[b"version"] == b"0.1.0"
    assert registered_info.properties[b"model"] == b"phi4-mini"

    discovery.stop_advertisement()


def test_discovery_advertisement_with_tls(monkeypatch):
    monkeypatch.setattr(discovery, "_advertiser", None)
    monkeypatch.setattr(discovery, "_local_ipv4_addresses", lambda: [b"\x7f\x00\x00\x01"])

    registered_info = None

    class MockZeroconf:
        def register_service(self, info):
            nonlocal registered_info
            registered_info = info

        def close(self):
            pass

    monkeypatch.setattr("zeroconf.Zeroconf", MockZeroconf)

    success = discovery.start_advertisement(8000, "0.1.0", "phi4-mini", tls=True)
    assert success is True
    assert registered_info is not None
    assert registered_info.properties[b"tls"] == b"1"
    assert registered_info.properties[b"version"] == b"0.1.0"
    assert registered_info.properties[b"model"] == b"phi4-mini"

    discovery.stop_advertisement()
