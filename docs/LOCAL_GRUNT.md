# Local Grunt

The local grunt delegates small, bounded file jobs to the local Ollama model
instead of spending the main model's context and tokens on them. It ships in two
integration editions that share the same policy and guards:

| Edition | Entry point | Dependency |
|---|---|---|
| Native OpenCode plugin | `.opencode/plugins/pf-local-grunt.ts` | `@opencode/plugin` (Node) |
| Standalone CLI | `tools/local_grunt.py` | Python stdlib only |
| Standalone MCP | `tools/local_grunt_mcp.py` | Python stdlib only, imports the CLI core |

Model: `pf-grunt:3b` (built from `qwen2.5:3b`, 16k context).
Endpoint: `http://127.0.0.1:11450` - the port Windows 11 leaves alone on this
machine.

## Start It

```powershell
powershell -ExecutionPolicy Bypass -File tools\ollama\Ensure_Local_Grunt.ps1
```

The script starts Ollama on `127.0.0.1:11450` if needed, creates/refreshes
`pf-grunt:3b`, warms it, and exits 0. `keep_alive` is 30 minutes, so idle time
between calls does not force a cold start.

The plugin edition also needs its Node SDK once per clone:

```powershell
cd .opencode
npm install
```

Then reload OpenCode:

```powershell
opencode reload
```

## Plugin Edition

`.opencode/plugins/pf-local-grunt.ts` auto-registers a `local_grunt` tool. It
uses the V2 plugin SDK and the same guards as the Python core. Confirm it loads:

```powershell
opencode plugin list
```

## Standalone CLI

Run from the repo root. The CLI is stdlib only, so the venv path is optional:

```powershell
python tools\local_grunt.py read `
  --task "Return the first Markdown heading only." `
  --paths AGENTS.md

python tools\local_grunt.py propose `
  --task "Replace the word alpha with gamma. Keep everything else exactly as it is." `
  --paths note.txt

python tools\local_grunt.py apply --edits-file proposal.json
```

`--json` prints the full result object. `--root`, `--base-url`, `--model`, and
`--timeout` override the defaults.

## Standalone MCP

`.opencode/opencode.jsonc` starts `tools/local_grunt_mcp.py` as a local MCP
server named `pf`. OpenCode exposes its tool as `pf_local_grunt` (and as
`tools.pf.local_grunt` under Code Mode). Check the connection:

```powershell
opencode mcp list
```

The server speaks JSON-RPC 2.0 over stdio with the legacy MCP initialize
handshake. It has no third-party dependencies.

## Modes

### `read`

The local model answers from the files you pass. It cannot browse - pass explicit
paths.

```text
local_grunt(mode="read",
  task="Return the first Markdown heading only.",
  paths=["AGENTS.md"])
```

### `propose`

The local model proposes exact `old`/`new` replacements. **No files are written.**
Every `old` string must match exactly once, and the path must be allowed.

```text
local_grunt(mode="propose",
  task="Replace the word alpha with gamma. Keep everything else exactly as it is.",
  paths=["note.txt"])
```

The result includes a `PROPOSAL JSON` block.

### `apply`

Apply a proposal the parent has reviewed. The tool writes only when every edit
matches exactly once; a bad edit aborts the whole batch.

```text
local_grunt(mode="apply",
  edits=[{"path":"note.txt","old":"alpha","new":"gamma"}])
```

`propose` + `apply` is deliberately two steps. The 3B model is good at locating
text, but it is not trusted to write unreviewed changes.

## Limits and Guards

- 1-8 files per call
- 8k characters per read file, 24k characters total per prompt
- 120-second timeout
- Refuses `.git`, `node_modules`, `build`, `.gradle`, binaries, and paths outside
  the project root
- Edit/apply refuses `blueprints/`, `data/`, `assets/`, `.env`, `local.properties`,
  keystores, APKs, and databases
- No shell, no web, no subagents, no file creation or deletion

## Test the Cores

Plugin/core smoke test (Node):

```powershell
node .opencode/lib/local-grunt-smoke.mjs
```

Standalone core smoke test (Python):

```powershell
python tools/local_grunt_smoke.py
```

Expected tails:

```text
SMOKE PASS: read/propose/apply
SMOKE PASS: ambiguous edit refused (...)
SMOKE PASS: traversal refused (...)
```
