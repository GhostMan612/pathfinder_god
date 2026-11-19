# SPEC — sovereign-chain MCP server

Version: 0.1.0. Reference implementation:
`tools/chain-mcp/server.py` (Python 3, standard library only).
Companion design: `../COUNCIL.md`. Overlay copy: the council overlay
ships this file and a byte-identical `server.py`.

## Transport

- stdio only. Newline-delimited JSON-RPC 2.0: one JSON object per line
  on stdin, one response object per line on stdout. No HTTP server in
  this build; no Content-Length framing.
- Protocol version reported at `initialize`: `2024-11-05`.
- Supported requests: `initialize`, `ping`, `tools/list`,
  `tools/call`. `notifications/*` (including
  `notifications/initialized`) receive no response. Anything else is a
  method-not-found error. Batch (array) requests are refused.
- All diagnostics go to stderr. Stdout carries protocol responses only.
- The server never exits on a bad request: malformed JSON, unknown
  tools, unknown methods, and tool failures all produce error
  responses and the loop continues. EOF on stdin exits 0.

## Chain-root resolution

First match wins:

1. `--root` argument.
2. `SOVEREIGN_CHAIN_ROOT` environment variable.
3. `./artifact-chain`, when that directory exists.
4. The current directory.

The resolved root is absolute (symlinks resolved) and is logged to
stderr at startup. In the council overlay layout the chain lives at
`<repo>/artifact-chain/`, so running the server from the repo root
resolves case 3 with no flags.

## Tools

Exactly six tools. Every `tools/call` result carries a `content` array
with one `text` item holding a JSON string; tool-level refusals return
`isError: true` with `{"ok": false, "error": "<CODE>", "message": ...}`.
Protocol-level problems (unknown tool, bad params shape) return
JSON-RPC errors instead.

### chain_status — input: `{}`

Reads the `## Status board` section of `CHAIN.md` when present
(`status_board: null` when absent) and lists artifacts:

```json
{
  "ok": true,
  "chain_root": "/abs/path",
  "chain_md_present": true,
  "status_board": "## Status board\n\n...",
  "artifacts": {
    "intent": ["intent/<slug>.md"],
    "spec": ["spec/<slug>.md"],
    "plan": ["plan/<slug>.md"],
    "review": ["review/REVIEW.md"],
    "review/findings": ["review/findings/<date>-<author>.md"],
    "decisions": ["decisions/DECISIONS.md"],
    "templates": ["templates/<name>-template.md"],
    "evals": ["evals/check-chain.sh"]
  },
  "decision_ids": ["D-0001"]
}
```

`README.md` files are excluded from the lists. Missing directories
list as `[]`.

### chain_read — input: `{"path": "<relative path>"}`

Returns `{"ok": true, "path", "resolved", "bytes", "content"}`.
Refusals: absolute paths and any path resolving outside the chain root
(`PATH_ESCAPE`), missing files (`NOT_FOUND`), files over 1,000,000
bytes (`TOO_LARGE`). Symlink escapes are caught because the candidate
path is resolved before the containment check.

### chain_append_decision — input

```json
{
  "question": "string, required",
  "decision": "string, required",
  "reason": "string, required",
  "author": "string, required",
  "model": "string, optional, default \"unknown\"",
  "artifact": "string, optional",
  "previous": "string, optional, default \"None — first decision\"",
  "supersedes": "string, optional, default \"none\""
}
```

Appends one entry to `decisions/DECISIONS.md` in the scaffold's
template shape, with the next sequential `D-####` id (max existing id
+ 1; `D-0001` when the log is empty). Heading:
`## D-#### — YYYY-MM-DD — <author>`. A final `Signature:` bullet
records `author / model / <UTC timestamp>` — the signing convention
from COUNCIL.md. If the file does not exist it is created with the
append-only header. If it still contains the scaffold's `No entries
yet.` placeholder, the first entry replaces that line. Existing entries
are never edited, reordered, or deleted. Returns
`{"ok": true, "entry_id", "file": "decisions/DECISIONS.md",
"signature"}`.

### chain_check — input: `{}`

Runs the scaffold's consistency-check logic, re-implemented in Python
to match `evals/check-chain.sh` exactly:

1. Every requirement ID (`R<n>`, word-boundary match) in `spec/*.md`
   (excluding `README.md`) must appear in some `plan/*.md` file.
   Otherwise: `{"kind": "orphan_requirement", "id", "message"}`.
2. Every plan task block (headed by a line matching `^### T[0-9]+`)
   must cite at least one requirement ID within the block, heading
   line included. Otherwise:
   `{"kind": "orphan_task", "id", "file", "message"}`.
3. Spec/plan slug mismatches are `notes`, never findings.

Returns `{"ok": true, "passed": <bool>, "findings": [...],
"notes": [...], "note": ...}`. With no spec/plan files at all it
passes with a "nothing to check" note, matching the shell script.

Honest limit, stated in the result's `note`: the chain eval doc's
"traces to a test/device check" leg is NOT machine-checked by the
shipped script, and this server does not fake it. That leg stays a
review-gate item for the reviewer pass. Exit-code semantics are
preserved in spirit: `passed: false` exactly when the shell script
would exit 1.

### chain_propose — input

```json
{
  "name": "string, required, slug ^[a-z0-9][a-z0-9_-]*$",
  "title": "string, required",
  "problems": "string, required",
  "outcomes": "string, required",
  "constraints": "string, optional",
  "author": "string, required",
  "model": "string, optional, default \"unknown\"",
  "overwrite": "boolean, optional, default false"
}
```

Writes `intent/<name>.md` in the scaffold's intent-template shape with
`Status: DRAFT`. Refuses (`ALREADY_EXISTS`) when the file exists and
`overwrite` is not exactly `true`. Returns
`{"ok": true, "file", "overwrote": <bool>, "status": "DRAFT"}`.
A proposal never writes spec or plan files and never approves
anything.

### chain_review_submit — input

```json
{
  "author": "string, required",
  "findings": "string, required",
  "date": "string, optional, YYYY-MM-DD, default today (UTC)"
}
```

Writes `review/findings/<date>-<author-slug>.md` (author slug is
lowercased, non-alphanumeric runs become `-`). On a filename collision
it appends `-2`, `-3`, … — findings are immutable and never merged.
It never reads, writes, or edits `review/REVIEW.md` itself. Returns
`{"ok": true, "file": "review/findings/<name>"}`.

## Error codes

| Code | Meaning |
|---|---|
| JSON-RPC `-32700` | Malformed JSON on stdin. |
| JSON-RPC `-32600` | Invalid request (no method; batch). |
| JSON-RPC `-32601` | Unknown method. |
| JSON-RPC `-32602` | Unknown tool, or params/arguments not an object. |
| JSON-RPC `-32603` | Internal error (last-resort guard; also logged). |
| `INVALID_PARAMS` | Tool argument missing, empty, or wrong-typed (tool error). |
| `PATH_ESCAPE` | Read path outside the chain root (tool error). |
| `NOT_FOUND` | Read path has no file (tool error). |
| `TOO_LARGE` | Read file over the byte cap (tool error). |
| `ALREADY_EXISTS` | Propose target exists without `overwrite=true` (tool error). |
| `INTERNAL_ERROR` | Tool raised unexpectedly; details logged to stderr (tool error). |

## Security rules

- Writes are confined to the resolved chain root: `intent/`
  (chain_propose), `decisions/DECISIONS.md` (chain_append_decision),
  `review/findings/` (chain_review_submit). No other path is ever
  written. Reads are confined the same way.
- No network access, no subprocesses, no environment reads other than
  `SOVEREIGN_CHAIN_ROOT`, no secret handling. Nothing in the chain
  files is treated as a credential.
- A compromised or mistaken caller can at most add draft intents,
  decision entries, and finding files inside the chain root. It cannot
  edit REVIEW.md, rewrite history, commit, push, merge, or approve
  anything. Approval stays human (see COUNCIL.md).
- The server trusts the local harness process that spawns it. Do not
  expose it over a network transport without adding authentication;
  this build ships stdio only for exactly that reason.

## Harness configuration (verified 2026-11-04)

All three shapes launch the same command from the repo root and rely
on the default `./artifact-chain` root resolution. No secrets appear
in any of them.

### Claude Code — `.mcp.json` (project scope, committed at repo root)

Verified against current Claude Code MCP docs: project scope lives in
`.mcp.json` at the repo root under `mcpServers`, is shared via git,
and Claude Code asks the user to approve project servers on first use.
For a stdio server the entry carries `command` and `args`; `"type":
"stdio"` is written explicitly, matching the documented shape.

```json
{
  "mcpServers": {
    "sovereign-chain": {
      "type": "stdio",
      "command": "python3",
      "args": ["tools/chain-mcp/server.py"]
    }
  }
}
```

CLI equivalent:
`claude mcp add --transport stdio --scope project sovereign-chain -- python3 tools/chain-mcp/server.py`

### OpenCode — `.opencode.json` (V2 shape, committed at repo root)

Verified by reading https://opencode.ai/v2/docs/mcp-servers on
2026-11-04: V2 places server names under `mcp.servers` (not directly
under `mcp`); a local server requires `"type": "local"` and
`"command"` as an array (executable followed by arguments); `cwd`
defaults to the workspace. No correction to the planned shape was
needed — the docs match it exactly.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "sovereign-chain": {
        "type": "local",
        "command": ["python3", "tools/chain-mcp/server.py"]
      }
    }
  }
}
```

CLI equivalent:
`opencode mcp add sovereign-chain -- python3 tools/chain-mcp/server.py`

### Codex — user-level config (cannot be committed)

Codex reads MCP servers from `~/.codex/config.toml` (`[mcp_servers.*]`
tables). There is no committed project file for Codex; the overlay
ships `codex.toml.snippet` plus the registration command, and the
server is registered per user:

```sh
codex mcp add sovereign-chain -- python3 tools/chain-mcp/server.py
```

Run from the repo root; Codex records the command and args. The
snippet's TOML shape is the file that command produces — prefer the
command over hand-editing. The Codex TOML spelling was not verified
against a live Codex install in this environment (see TEST-REPORT.md);
the registration command is the documented path.

## Versioning

Server version `0.1.0`, reported at `initialize` and in
`SERVER_VERSION`. Bump it together with the overlay `VERSION` file.
