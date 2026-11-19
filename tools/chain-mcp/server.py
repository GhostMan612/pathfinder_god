#!/usr/bin/env python3
"""sovereign-chain — MCP server over stdio for artifact-chain repos.

Standard library only. Speaks MCP over newline-delimited JSON-RPC 2.0
on stdin/stdout. All diagnostics go to stderr; stdout carries only
protocol responses.

Chain-root resolution (first match wins):
  1. --root argument
  2. SOVEREIGN_CHAIN_ROOT environment variable
  3. ./artifact-chain, when that directory exists
  4. The current directory

The server never writes outside the resolved chain root, never touches
the network, and never reads or writes secrets. See SPEC.md.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SERVER_NAME = "sovereign-chain"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"
MAX_READ_BYTES = 1_000_000

REQ_ID_RE = re.compile(r"\bR[0-9]+\b")
TASK_HEADING_RE = re.compile(r"^### T[0-9]+")
REQ_IN_LINE_RE = re.compile(r"(^|[^A-Za-z0-9_])R[0-9]+([^A-Za-z0-9_]|$)")
DECISION_ID_RE = re.compile(r"^##\s+D-([0-9]+)\b", re.MULTILINE)
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
AUTHOR_SLUG_RE = re.compile(r"[^a-z0-9]+")


def log(message):
    print("[sovereign-chain] " + message, file=sys.stderr, flush=True)


def utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tool_result(payload, is_error=False):
    """Build an MCP tools/call result whose text body is JSON."""
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "isError": is_error,
    }


def tool_error(message, code="TOOL_ERROR"):
    return tool_result({"ok": False, "error": code, "message": message}, is_error=True)


class ChainRoot:
    """A resolved chain directory. All paths resolve inside it."""

    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()

    def resolve_inside(self, relative):
        """Resolve `relative` inside the root, or raise ValueError."""
        if os.path.isabs(relative):
            raise ValueError("absolute paths are not allowed: %r" % relative)
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("path escapes the chain root: %r" % relative)
        return candidate

    def list_md(self, subdir, include_readme=False):
        directory = self.root / subdir
        if not directory.is_dir():
            return []
        names = sorted(
            p.name
            for p in directory.glob("*.md")
            if p.is_file() and (include_readme or p.name != "README.md")
        )
        return ["%s/%s" % (subdir, n) for n in names]

    def read_text(self, path):
        return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------- tools


def do_chain_status(chain, _args):
    artifacts = {}
    for subdir in ("intent", "spec", "plan", "review", "decisions",
                   "templates", "evals"):
        artifacts[subdir] = chain.list_md(subdir)
    findings = []
    findings_dir = chain.root / "review" / "findings"
    if findings_dir.is_dir():
        findings = sorted(
            "review/findings/%s" % p.name
            for p in findings_dir.glob("*.md")
            if p.is_file()
        )
    artifacts["review/findings"] = findings

    status_board = None
    chain_md = chain.root / "CHAIN.md"
    if chain_md.is_file():
        text = chain.read_text(chain_md)
        match = re.search(
            r"^## Status board.*?(?=^## |\Z)", text,
            re.MULTILINE | re.DOTALL,
        )
        if match:
            status_board = match.group(0).strip()

    decision_ids = []
    decisions_file = chain.root / "decisions" / "DECISIONS.md"
    if decisions_file.is_file():
        decision_ids = [
            "D-%s" % n
            for n in DECISION_ID_RE.findall(chain.read_text(decisions_file))
        ]

    return tool_result({
        "ok": True,
        "chain_root": str(chain.root),
        "chain_md_present": chain_md.is_file(),
        "status_board": status_board,
        "artifacts": artifacts,
        "decision_ids": decision_ids,
    })


def do_chain_read(chain, args):
    relative = args.get("path")
    if not isinstance(relative, str) or not relative:
        return tool_error("`path` is required and must be a string.",
                          "INVALID_PARAMS")
    try:
        target = chain.resolve_inside(relative)
    except ValueError as exc:
        return tool_error(str(exc), "PATH_ESCAPE")
    if not target.is_file():
        return tool_error("no such file inside the chain root: %r" % relative,
                          "NOT_FOUND")
    if target.stat().st_size > MAX_READ_BYTES:
        return tool_error("file exceeds the %d-byte read cap." % MAX_READ_BYTES,
                          "TOO_LARGE")
    return tool_result({
        "ok": True,
        "path": relative,
        "resolved": str(target),
        "bytes": target.stat().st_size,
        "content": chain.read_text(target),
    })


def run_consistency_check(chain):
    """Faithful re-implementation of the scaffold's evals/check-chain.sh.

    Check 1: every requirement ID (R<n>) in spec/*.md (README.md
    ignored) appears in some plan/*.md file.
    Check 2: every plan task block (headed `### T<n>`) cites >= 1
    requirement ID within its block (heading line included).
    Check 3 (notes only): spec/plan slug mismatches.
    Exit semantics: pass when no orphan requirement or task is found.

    The "traces to a test/device check" leg of the chain eval doc is
    NOT machine-checked here — the shipped script does not check it.
    It stays a review-gate item and is reported as such, never faked.
    """
    spec_dir = chain.root / "spec"
    plan_dir = chain.root / "plan"

    def md_files(directory):
        if not directory.is_dir():
            return []
        return sorted(
            p for p in directory.glob("*.md")
            if p.is_file() and p.name != "README.md"
        )

    spec_files = md_files(spec_dir)
    plan_files = md_files(plan_dir)
    findings = []
    notes = []

    if not spec_files and not plan_files:
        return {
            "ok": True,
            "passed": True,
            "findings": [],
            "notes": ["no spec/plan files yet — nothing to check."],
            "note": "test/device-check traceability is a review-gate item; "
                    "it is not machine-checked.",
        }

    plan_texts = {}
    for plan_file in plan_files:
        plan_texts[plan_file] = chain.read_text(plan_file)

    if spec_files and plan_files:
        req_ids = set()
        for spec_file in spec_files:
            req_ids.update(REQ_ID_RE.findall(chain.read_text(spec_file)))
        for rid in sorted(req_ids, key=lambda r: (len(r), r)):
            if not any(re.search(r"\b%s\b" % re.escape(rid), text)
                       for text in plan_texts.values()):
                findings.append({
                    "kind": "orphan_requirement",
                    "id": rid,
                    "message": "%s is in spec/ but cited by no plan file." % rid,
                })

    for plan_file in plan_files:
        current_task = None
        current_seen = False

        def flush():
            if current_task is not None and not current_seen:
                findings.append({
                    "kind": "orphan_task",
                    "id": current_task,
                    "file": "plan/%s" % plan_file.name,
                    "message": "%s in plan/%s cites no requirement ID (R<n>)."
                               % (current_task, plan_file.name),
                })

        for line in plan_texts[plan_file].splitlines():
            heading = TASK_HEADING_RE.match(line)
            if heading:
                flush()
                match = re.search(r"T[0-9]+", line)
                current_task = match.group(0) if match else None
                current_seen = bool(REQ_IN_LINE_RE.search(line))
                continue
            if current_task is not None and REQ_IN_LINE_RE.search(line):
                current_seen = True
        flush()

    for spec_file in spec_files:
        slug = spec_file.stem
        if not (plan_dir / ("%s.md" % slug)).exists():
            notes.append("spec/%s.md has no matching plan/%s.md yet."
                         % (slug, slug))
    for plan_file in plan_files:
        slug = plan_file.stem
        if not (spec_dir / ("%s.md" % slug)).exists():
            notes.append("plan/%s.md has no matching spec/%s.md."
                         % (slug, slug))

    return {
        "ok": True,
        "passed": not findings,
        "findings": findings,
        "notes": notes,
        "note": "test/device-check traceability is a review-gate item; "
                "it is not machine-checked.",
    }


def do_chain_check(chain, _args):
    return tool_result(run_consistency_check(chain))


def next_decision_id(chain):
    decisions_file = chain.root / "decisions" / "DECISIONS.md"
    if not decisions_file.is_file():
        return 1
    found = [int(n) for n in DECISION_ID_RE.findall(chain.read_text(decisions_file))]
    return (max(found) + 1) if found else 1


def do_chain_append_decision(chain, args):
    for field in ("question", "decision", "reason", "author"):
        if not isinstance(args.get(field), str) or not args[field].strip():
            return tool_error("`%s` is required and must be a non-empty string."
                              % field, "INVALID_PARAMS")
    model = args.get("model") or "unknown"
    if not isinstance(model, str):
        return tool_error("`model` must be a string.", "INVALID_PARAMS")
    artifact = args.get("artifact") or ""
    previous = args.get("previous") or "None — first decision"
    supersedes = args.get("supersedes") or "none"
    for field_name, value in (("artifact", artifact),
                              ("previous", previous),
                              ("supersedes", supersedes)):
        if not isinstance(value, str):
            return tool_error("`%s` must be a string." % field_name,
                              "INVALID_PARAMS")

    decisions_dir = chain.root / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    decisions_file = decisions_dir / "DECISIONS.md"
    number = next_decision_id(chain)
    entry_id = "D-%04d" % number
    stamp = utc_now_iso()
    entry = (
        "## %s — %s — %s\n\n"
        "- **Artifact / gate:** %s\n"
        "- **Question:** %s\n"
        "- **Previous decision:** %s\n"
        "- **New decision:** %s\n"
        "- **Reason:** %s\n"
        "- **Supersedes:** %s\n"
        "- **Signature:** %s / %s / %s\n"
    ) % (entry_id, utc_today(), args["author"].strip(),
         artifact.strip() or "(not stated)",
         args["question"].strip(), previous.strip(),
         args["decision"].strip(), args["reason"].strip(),
         supersedes.strip(), args["author"].strip(), model.strip(), stamp)

    if not decisions_file.is_file():
        header = (
            "# Decision log\n\n"
            "Append-only. New entries go at the end, in `D-####` order. "
            "Never edit, reorder, or delete an existing entry — correct one "
            "by appending a new entry that references it.\n\n"
        )
        decisions_file.write_text(header + entry, encoding="utf-8")
    else:
        text = chain.read_text(decisions_file)
        if "No entries yet." in text:
            text = text.replace("No entries yet.", entry.rstrip("\n"),
                                1)
            decisions_file.write_text(text, encoding="utf-8")
        else:
            if not text.endswith("\n"):
                text += "\n"
            decisions_file.write_text(text + "\n" + entry, encoding="utf-8")

    return tool_result({
        "ok": True,
        "entry_id": entry_id,
        "file": "decisions/DECISIONS.md",
        "signature": "%s / %s / %s" % (args["author"].strip(),
                                        model.strip(), stamp),
    })


def do_chain_propose(chain, args):
    name = args.get("name")
    if not isinstance(name, str) or not SLUG_RE.match(name):
        return tool_error(
            "`name` must be a slug: lowercase letters, digits, '-' or '_'.",
            "INVALID_PARAMS")
    for field in ("title", "problems", "outcomes", "author"):
        if not isinstance(args.get(field), str) or not args[field].strip():
            return tool_error("`%s` is required and must be a non-empty string."
                              % field, "INVALID_PARAMS")
    model = args.get("model") or "unknown"
    constraints = args.get("constraints") or ""
    if not isinstance(model, str) or not isinstance(constraints, str):
        return tool_error("`model` and `constraints` must be strings.",
                          "INVALID_PARAMS")
    overwrite = args.get("overwrite", False)
    if not isinstance(overwrite, bool):
        return tool_error("`overwrite` must be a boolean.", "INVALID_PARAMS")

    intent_dir = chain.root / "intent"
    intent_dir.mkdir(parents=True, exist_ok=True)
    target = intent_dir / ("%s.md" % name)
    existed = target.exists()
    if existed and not overwrite:
        return tool_error(
            "intent/%s.md already exists; pass overwrite=true to replace it."
            % name, "ALREADY_EXISTS")
    body = (
        "# Intent: %s\n\n"
        "Status: DRAFT — awaiting acceptance (Plan gate)\n"
        "Origin: proposed by %s (%s) at %s via sovereign-chain.\n\n"
        "## Title\n\n%s\n\n"
        "## Problems\n\n%s\n\n"
        "## Proposed outcomes\n\n%s\n\n"
        "## Affected users\n\n(To be filled in by the drafter.)\n\n"
        "## Constraints\n\n%s\n\n"
        "## Open questions\n\n(To be filled in by the drafter.)\n\n"
        "## Non-goals\n\n(To be filled in by the drafter.)\n\n"
        "## Acceptance (intent gate)\n\n"
        "Acceptance does not authorize implementation.\n"
    ) % (args["title"].strip(), args["author"].strip(), model.strip(),
         utc_now_iso(), args["title"].strip(), args["problems"].strip(),
         args["outcomes"].strip(),
         constraints.strip() or "(To be filled in by the drafter.)")
    target.write_text(body, encoding="utf-8")
    return tool_result({
        "ok": True,
        "file": "intent/%s.md" % name,
        "overwrote": bool(existed and overwrite),
        "status": "DRAFT",
    })


def do_chain_review_submit(chain, args):
    author = args.get("author")
    findings = args.get("findings")
    if not isinstance(author, str) or not author.strip():
        return tool_error("`author` is required and must be a string.",
                          "INVALID_PARAMS")
    if not isinstance(findings, str) or not findings.strip():
        return tool_error("`findings` is required and must be a string.",
                          "INVALID_PARAMS")
    date = args.get("date") or utc_today()
    if not isinstance(date, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return tool_error("`date` must be YYYY-MM-DD.", "INVALID_PARAMS")
    slug = AUTHOR_SLUG_RE.sub("-", author.strip().lower()).strip("-")
    if not slug:
        return tool_error("`author` must contain a usable name.", "INVALID_PARAMS")

    findings_dir = chain.root / "review" / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    base = "%s-%s" % (date, slug)
    target = findings_dir / ("%s.md" % base)
    suffix = 2
    while target.exists():
        target = findings_dir / ("%s-%d.md" % (base, suffix))
        suffix += 1
    body = (
        "# Review findings — %s — %s\n\n"
        "Reviewer: %s. Submitted %s via sovereign-chain. "
        "This file never edits review/REVIEW.md itself.\n\n%s\n"
    ) % (date, author.strip(), author.strip(), utc_now_iso(),
         findings.strip())
    target.write_text(body, encoding="utf-8")
    return tool_result({
        "ok": True,
        "file": "review/findings/%s" % target.name,
    })


TOOLS = [
    {
        "name": "chain_status",
        "description": "Read the chain status board (if present) and list "
                       "the artifacts under the chain root.",
        "inputSchema": {"type": "object", "properties": {},
                        "additionalProperties": False},
        "handler": do_chain_status,
    },
    {
        "name": "chain_read",
        "description": "Read one artifact by path relative to the chain "
                       "root. Paths that escape the root are refused.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Path relative to the chain root."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "handler": do_chain_read,
    },
    {
        "name": "chain_append_decision",
        "description": "Append one signed entry to decisions/DECISIONS.md "
                       "with the next sequential D-#### id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "decision": {"type": "string"},
                "reason": {"type": "string"},
                "author": {"type": "string"},
                "model": {"type": "string"},
                "artifact": {"type": "string"},
                "previous": {"type": "string"},
                "supersedes": {"type": "string"},
            },
            "required": ["question", "decision", "reason", "author"],
            "additionalProperties": False,
        },
        "handler": do_chain_append_decision,
    },
    {
        "name": "chain_check",
        "description": "Run the chain-consistency check: every spec "
                       "requirement cited by a plan task, every plan task "
                       "citing a requirement. Reports orphans as findings.",
        "inputSchema": {"type": "object", "properties": {},
                        "additionalProperties": False},
        "handler": do_chain_check,
    },
    {
        "name": "chain_propose",
        "description": "Write a NEW draft intent file under intent/. "
                       "Refuses to overwrite an existing file unless "
                       "overwrite=true is passed explicitly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Slug for intent/<name>.md."},
                "title": {"type": "string"},
                "problems": {"type": "string"},
                "outcomes": {"type": "string"},
                "constraints": {"type": "string"},
                "author": {"type": "string"},
                "model": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["name", "title", "problems", "outcomes", "author"],
            "additionalProperties": False,
        },
        "handler": do_chain_propose,
    },
    {
        "name": "chain_review_submit",
        "description": "Write a dated finding file under "
                       "review/findings/. Never edits review/REVIEW.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "author": {"type": "string"},
                "findings": {"type": "string"},
                "date": {"type": "string",
                         "description": "YYYY-MM-DD; defaults to today (UTC)."},
            },
            "required": ["author", "findings"],
            "additionalProperties": False,
        },
        "handler": do_chain_review_submit,
    },
]

TOOL_HANDLERS = {tool["name"]: tool["handler"] for tool in TOOLS}


# ----------------------------------------------------------------- MCP


def rpc_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def rpc_result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_message(chain, message):
    """Return a response dict, or None for notifications."""
    if isinstance(message, list):
        return rpc_error(None, -32600, "Batch requests are not supported.")
    if not isinstance(message, dict) or "method" not in message:
        return rpc_error(message.get("id") if isinstance(message, dict)
                         else None, -32600, "Invalid Request: no method.")
    method = message["method"]
    is_notification = "id" not in message
    request_id = message.get("id")

    if method.startswith("notifications/"):
        return None
    if is_notification:
        return None

    params = message.get("params") or {}
    if not isinstance(params, dict):
        return rpc_error(request_id, -32602, "params must be an object.")

    if method == "initialize":
        return rpc_result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method == "ping":
        return rpc_result(request_id, {})
    if method == "tools/list":
        return rpc_result(request_id, {
            "tools": [
                {"name": t["name"], "description": t["description"],
                 "inputSchema": t["inputSchema"]}
                for t in TOOLS
            ],
        })
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or name not in TOOL_HANDLERS:
            return rpc_error(request_id, -32602,
                             "Unknown tool: %r." % (name,))
        if not isinstance(arguments, dict):
            return rpc_error(request_id, -32602,
                             "arguments must be an object.")
        try:
            return rpc_result(request_id, TOOL_HANDLERS[name](chain, arguments))
        except Exception as exc:  # never crash the loop on a tool failure
            log("tool %s failed: %s" % (name, exc))
            return rpc_result(request_id, tool_error(
                "internal error: %s" % exc, "INTERNAL_ERROR"))
    return rpc_error(request_id, -32601, "Method not found: %s." % method)


def serve(chain):
    log("chain root: %s" % chain.root)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(rpc_error(
                None, -32700, "Parse error: malformed JSON.")) + "\n")
            sys.stdout.flush()
            continue
        try:
            response = handle_message(chain, message)
        except Exception as exc:  # last-resort guard: stay alive
            log("handler error: %s" % exc)
            response = rpc_error(
                message.get("id") if isinstance(message, dict) else None,
                -32603, "Internal error.")
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


def resolve_root(cli_root):
    if cli_root:
        return cli_root
    env_root = os.environ.get("SOVEREIGN_CHAIN_ROOT")
    if env_root:
        return env_root
    artifact_chain = Path.cwd() / "artifact-chain"
    if artifact_chain.is_dir():
        return str(artifact_chain)
    return os.getcwd()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="sovereign-chain MCP server (stdio).")
    parser.add_argument("--root", default=None,
                        help="Chain root directory.")
    args = parser.parse_args(argv)
    chain = ChainRoot(resolve_root(args.root))
    serve(chain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
