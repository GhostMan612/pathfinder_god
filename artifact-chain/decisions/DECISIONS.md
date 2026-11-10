# Decision log

Append-only. New entries go at the end, in `D-####` order. Never edit,
reorder, or delete an existing entry — correct one by appending a new
entry that references it. Format and rules: `decisions/README.md`.
Template: `decisions/decision-template.md`.

## D-0001 — 2026-11-10 — Glenn

- **Artifact / gate:** COUNCIL.md (repo root), pilot install
- **Question:** Pilot the Sovereign Council chain in pathfinder_god?
- **Previous decision:** None — first decision.
- **New decision:** Yes. Install the council chain on branch `council-chain-pilot` off `main` at `33a969a`: `artifact-chain/` scaffold, `tools/chain-mcp/server.py` (byte-identical to the council reference), OpenCode MCP wiring in `.opencode/opencode.jsonc`, and `tools/chain-watcher.ps1` on the laptop. Local build only — nothing pushed, nothing merged.
- **Reason:** Pathfinder God is the active repo with the local-grunt OpenCode plugin already in place; the council design says the repo is the shared state between agents, and this pilot tests whether Muse and OpenCode can hand work back and forth through the chain instead of Glenn pasting reports between chats.
- **Supersedes:** none.
- **Signature:** Glenn / unknown / 2026-11-10T23:17:00Z
