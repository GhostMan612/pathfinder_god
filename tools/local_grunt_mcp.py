#!/usr/bin/env python3
# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Minimal MCP stdio server for the standalone local grunt.

No SDK, no third-party packages. It exposes one tool, ``local_grunt``, backed by
the same Python core as tools/local_grunt.py. OpenCode starts it with:

    python tools/local_grunt_mcp.py

Protocol: MCP legacy initialize handshake (2024-11-05), JSON-RPC 2.0 over stdio.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from local_grunt import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_TIMEOUT_S, GruntError, run_grunt

TOOL = {
    "name": "local_grunt",
    "description": (
        "Delegate a small, bounded job to the local Ollama grunt (pf-grunt:3b on 127.0.0.1:11450). "
        "Use for narrow file summaries and symbol lookups when you already know the paths. "
        "Do NOT use for architecture, security, tests, or open-ended exploration. "
        "Pass 1-8 explicit project-relative file paths. "
        "mode=read returns a concise answer. mode=propose asks the local model for exact old/new "
        "replacements and returns a reviewed proposal without writing. mode=apply applies an explicit "
        "edits array that the parent has reviewed, requiring each old string to match exactly once "
        "inside the project root. Refuses blueprints, data, assets, secrets, binaries, build output, "
        "and paths outside the repo."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["read", "propose", "apply"],
                "description": "read = answer; propose = reviewed edit proposal (no writes); apply = apply explicit reviewed edits. Default read.",
            },
            "task": {
                "type": "string",
                "description": "The exact bounded job. Required for read and propose.",
            },
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Project-relative files to send for read/propose. Max 8; the grunt cannot browse.",
            },
            "edits": {
                "type": "array",
                "description": "Reviewed {path, old, new} edits for mode=apply. The parent must verify the proposal first.",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                    },
                    "required": ["path", "old", "new"],
                    "additionalProperties": False,
                },
            },
            "context": {
                "type": "string",
                "description": "Optional extra instructions or constraints for the grunt.",
            },
        },
        "additionalProperties": False,
    },
}


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(request_id: Any, result: Any) -> None:
    _write({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _handle(request: dict[str, Any]) -> bool:
    """Handle one JSON-RPC request. Returns False when the server should exit."""
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}

    if method == "initialize":
        requested = params.get("protocolVersion")
        supported = {"2024-11-05", "2025-06-18", "2025-11-25"}
        version = requested if requested in supported else "2024-11-05"
        _result(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pf-local-grunt", "version": "1.0.0"},
                "instructions": (
                    "Use local_grunt for bounded file reads and reviewed edit proposals. "
                    "The local model has no tools, no shell, and no web."
                ),
            },
        )
        return True

    if method == "notifications/initialized":
        return True

    if method == "ping":
        _result(request_id, {})
        return True

    if method == "tools/list":
        _result(request_id, {"tools": [TOOL]})
        return True

    if method == "tools/call":
        if request_id is None:
            return True
        name = params.get("name")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if name != "local_grunt":
            _result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                    "isError": True,
                },
            )
            return True

        try:
            result = run_grunt(
                root=os.getcwd(),
                mode=str(arguments.get("mode") or "read"),
                task=arguments.get("task"),
                paths=arguments.get("paths"),
                edits=arguments.get("edits"),
                context=arguments.get("context"),
                base_url=str(arguments.get("base_url") or DEFAULT_BASE_URL),
                model=str(arguments.get("model") or DEFAULT_MODEL),
                timeout_s=float(arguments.get("timeout_s") or DEFAULT_TIMEOUT_S),
            )
            _result(
                request_id,
                {
                    "content": [{"type": "text", "text": result["text"]}],
                    "isError": not result["ok"],
                },
            )
        except (GruntError, OSError, ValueError) as exc:
            _result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"local-grunt failed: {exc}"}],
                    "isError": True,
                },
            )
        return True

    if method == "shutdown":
        _result(request_id, None)
        return True

    if method == "exit":
        return False

    if request_id is not None:
        _error(request_id, -32601, f"method not found: {method}")
    return True


def main() -> int:
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            _error(None, -32700, f"parse error: {exc}")
            continue

        requests = message if isinstance(message, list) else [message]
        for request in requests:
            if not isinstance(request, dict):
                _error(None, -32600, "invalid request")
                continue
            if not _handle(request):
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
