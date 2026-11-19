#!/usr/bin/env python3
"""Stdio smoke test for tools/chain-mcp/server.py.

Drives the server over JSON-RPC 2.0 on stdin/stdout against throwaway
copies of the scaffold's evals fixtures in /tmp. No network, no repo
writes outside the temp dir.

Usage:
    python3 tests/smoke_test.py [--server PATH] [--scaffold PATH]

Exit 0 = every check passed. Prints one PASS/FAIL line per check.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
DEFAULT_SERVER = HERE.parents[1] / "server.py"
DEFAULT_SCAFFOLD = Path.home() / "workspace" / "artifact-chain-scaffold"

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append((name, bool(condition), detail))
    print("%s %s%s" % ("PASS" if condition else "FAIL", name,
                        (" — " + detail) if detail and not condition else ""))


class Client:
    def __init__(self, server_path, root):
        self.proc = subprocess.Popen(
            [sys.executable, str(server_path), "--root", str(root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1)
        self.next_id = 1

    def request(self, method, params=None):
        rid = self.next_id
        self.next_id += 1
        payload = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("server closed stdout during %s" % method)
        return json.loads(line)

    def notify(self, method, params=None):
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def raw(self, text):
        self.proc.stdin.write(text + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def tool(self, name, arguments):
        resp = self.request("tools/call",
                            {"name": name, "arguments": arguments})
        assert "result" in resp, "no result in %r" % (resp,)
        body = json.loads(resp["result"]["content"][0]["text"])
        body["_is_error"] = resp["result"].get("isError", False)
        return body

    def close(self):
        try:
            self.proc.stdin.close()
        except BrokenPipeError:
            pass
        self.proc.wait(timeout=10)
        return self.proc.returncode, self.proc.stderr.read()


def build_chain(tmp, scaffold, fixture):
    root = tmp / fixture
    for src in (scaffold / "evals" / "fixtures" / fixture).iterdir():
        shutil.copytree(src, root / src.name)
    shutil.copytree(scaffold / "decisions", root / "decisions")
    (root / "CHAIN.md").write_text(
        "# The artifact chain\n\n## Status board\n\n- Test chain.\n",
        encoding="utf-8")
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=str(DEFAULT_SERVER))
    parser.add_argument("--scaffold", default=str(DEFAULT_SCAFFOLD))
    args = parser.parse_args()
    server = Path(args.server)
    scaffold = Path(args.scaffold)
    assert server.is_file(), "server not found: %s" % server
    assert scaffold.is_dir(), "scaffold not found: %s" % scaffold

    tmp = Path(tempfile.mkdtemp(prefix="chain-mcp-test-"))
    good_root = build_chain(tmp, scaffold, "good")
    client = Client(server, good_root)
    try:
        init = client.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "0.1.0"},
        })
        check("initialize handshake",
              init.get("result", {}).get("serverInfo", {}).get("name")
              == "sovereign-chain",
              json.dumps(init)[:200])
        client.notify("notifications/initialized")

        tools = client.request("tools/list")
        names = [t["name"] for t in tools["result"]["tools"]]
        check("tools/list returns exactly the six contract tools",
              names == ["chain_status", "chain_read", "chain_append_decision",
                        "chain_check", "chain_propose",
                        "chain_review_submit"],
              ",".join(names))

        ping = client.request("ping")
        check("ping returns empty result", ping.get("result") == {})

        status = client.tool("chain_status", {})
        check("chain_status lists spec/plan artifacts",
              status.get("ok") and "spec/hello-version.md" in
              status["artifacts"]["spec"]
              and "plan/hello-version.md" in status["artifacts"]["plan"],
              json.dumps(status)[:200])
        check("chain_status reads the status board",
              status.get("status_board") == "## Status board\n\n- Test chain.")

        result = client.tool("chain_check", {})
        check("chain_check passes the good fixture",
              result.get("passed") is True and result.get("findings") == [],
              json.dumps(result)[:300])

        propose = client.tool("chain_propose", {
            "name": "smoke-intent", "title": "Smoke intent",
            "problems": "P1.", "outcomes": "O1.",
            "author": "smoke-test", "model": "test-model/1"})
        check("chain_propose writes a new DRAFT intent",
              propose.get("ok") and propose.get("file") == "intent/smoke-intent.md",
              json.dumps(propose)[:200])
        check("proposed intent file exists on disk",
              (good_root / "intent" / "smoke-intent.md").is_file())

        again = client.tool("chain_propose", {
            "name": "smoke-intent", "title": "Again",
            "problems": "P.", "outcomes": "O.", "author": "smoke-test"})
        check("chain_propose refuses overwrite without overwrite=true",
              again.get("_is_error") and again.get("error") == "ALREADY_EXISTS",
              json.dumps(again)[:200])

        forced = client.tool("chain_propose", {
            "name": "smoke-intent", "title": "Again",
            "problems": "P.", "outcomes": "O.", "author": "smoke-test",
            "overwrite": True})
        check("chain_propose overwrites with overwrite=true",
              forced.get("ok") and forced.get("overwrote") is True)

        bad_slug = client.tool("chain_propose", {
            "name": "../escape", "title": "x", "problems": "p",
            "outcomes": "o", "author": "smoke-test"})
        check("chain_propose rejects a non-slug name",
              bad_slug.get("_is_error"), json.dumps(bad_slug)[:150])

        first = client.tool("chain_append_decision", {
            "question": "Q1?", "decision": "Yes.", "reason": "Because.",
            "author": "smoke-test", "model": "test-model/1"})
        check("chain_append_decision assigns D-0001 first",
              first.get("entry_id") == "D-0001", json.dumps(first)[:200])
        second = client.tool("chain_append_decision", {
            "question": "Q2?", "decision": "No.", "reason": "Because not.",
            "author": "smoke-test", "model": "test-model/1"})
        check("chain_append_decision assigns D-0002 next",
              second.get("entry_id") == "D-0002")
        log_text = (good_root / "decisions" / "DECISIONS.md").read_text()
        check("decision log carries author/model/timestamp signature",
              "smoke-test / test-model/1" in log_text)
        check("first entry replaced the 'No entries yet.' placeholder",
              "No entries yet." not in log_text)

        review = client.tool("chain_review_submit", {
            "author": "smoke-test",
            "findings": "## F1\n\nNo issues found."})
        check("chain_review_submit writes a dated findings file",
              review.get("ok") and review.get("file", "").startswith(
                  "review/findings/"), json.dumps(review)[:200])
        check("findings file exists and REVIEW.md untouched",
              (good_root / review["file"]).is_file()
              and not (good_root / "review" / "REVIEW.md").exists())

        read = client.tool("chain_read", {"path": "spec/hello-version.md"})
        check("chain_read returns file content inside the root",
              read.get("ok") and "R1" in read.get("content", ""))
        escape = client.tool("chain_read", {"path": "../outside.md"})
        check("chain_read refuses a path escape",
              escape.get("_is_error") and escape.get("error") == "PATH_ESCAPE",
              json.dumps(escape)[:150])
        absolute = client.tool("chain_read", {"path": "/etc/hostname"})
        check("chain_read refuses an absolute path",
              absolute.get("_is_error"), json.dumps(absolute)[:150])
        missing = client.tool("chain_read", {"path": "spec/nope.md"})
        check("chain_read reports a missing file",
              missing.get("_is_error") and missing.get("error") == "NOT_FOUND")

        unknown = client.request("tools/call",
                                 {"name": "nope_tool", "arguments": {}})
        check("unknown tool returns JSON-RPC -32602",
              unknown.get("error", {}).get("code") == -32602,
              json.dumps(unknown)[:150])

        bad_method = client.request("resources/list")
        check("unknown method returns JSON-RPC -32601",
              bad_method.get("error", {}).get("code") == -32601)

        parse_err = client.raw("{not json")
        check("malformed JSON returns -32700 and the server stays alive",
              parse_err.get("error", {}).get("code") == -32700)
        alive = client.request("ping")
        check("server alive after malformed input",
              alive.get("result") == {})
    finally:
        code, stderr = client.close()
    check("server exits 0 on stdin EOF", code == 0, "exit=%s" % code)
    check("server wrote nothing alarming to stderr",
          "Traceback" not in stderr, stderr[-300:])

    # Broken fixture: a second instance must FAIL the check.
    broken_root = build_chain(tmp, scaffold, "broken")
    broken = Client(server, broken_root)
    try:
        broken.request("initialize", {"protocolVersion": "2024-11-05",
                                      "capabilities": {},
                                      "clientInfo": {"name": "smoke-test",
                                                     "version": "0.1.0"}})
        result = broken.tool("chain_check", {})
        kinds = sorted(f["kind"] for f in result.get("findings", []))
        check("chain_check fails the broken fixture with orphan findings",
              result.get("passed") is False and kinds == [
                  "orphan_requirement", "orphan_task"],
              json.dumps(result)[:300])
    finally:
        broken.close()

    shutil.rmtree(tmp, ignore_errors=True)
    failed = [name for name, ok, _ in CHECKS if not ok]
    print("\n%d checks, %d failed." % (len(CHECKS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
