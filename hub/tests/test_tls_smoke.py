# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Smoke test for hub TLS serving."""
from __future__ import annotations

import asyncio
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from app.main import create_app
from scripts.make_hub_cert import generate_hub_cert


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_tls_smoke_https_and_http_refusal(tmp_path: Path, monkeypatch):
    # Disable zeroconf discovery in test runner
    monkeypatch.setattr("app.discovery.start_advertisement", lambda *a, **k: True)
    monkeypatch.setattr("app.discovery.stop_advertisement", lambda: None)

    cert_path = tmp_path / "test-cert.pem"
    key_path = tmp_path / "test-key.pem"
    generate_hub_cert(cert_path=cert_path, key_path=key_path)

    port = _get_free_port()
    app = create_app()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        ssl_certfile=str(cert_path),
        ssl_keyfile=str(key_path),
        log_level="warning",
    )
    server = uvicorn.Server(config)

    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Wait for server to start
    start_time = time.time()
    while not server.started:
        if time.time() - start_time > 10.0:
            server.should_exit = True
            thread.join(timeout=2.0)
            pytest.fail("Uvicorn TLS test server failed to start within 10s")
        time.sleep(0.05)

    try:
        # 1. Assert GET /health returns 200 over HTTPS with verification disabled in test client
        with httpx.Client(verify=False, timeout=5.0) as client:
            resp = client.get(f"https://127.0.0.1:{port}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

        # 2. Assert plain HTTP to the TLS port is refused (connection error, not 200 or redirect)
        with pytest.raises((httpx.RequestError, httpx.RemoteProtocolError)), httpx.Client(timeout=5.0) as client:
            client.get(f"http://127.0.0.1:{port}/health")

    finally:
        server.should_exit = True
        thread.join(timeout=5.0)
