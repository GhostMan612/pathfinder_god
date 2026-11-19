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

## D-0002 — 2026-11-18 — Phoenix (for Glenn's approval)

- **Artifact / gate:** artifact-chain/RSI.md (RSI spec), artifact-chain/evals/metrics/baseline.md
- **Question:** Do the rework-round definition and the baseline exclusion list say what RSI means?
- **Previous decision:** RSI.md: "A rework round is one findings file followed by a fix push that still leaves findings open." Baseline excludes only PRs #40 and #41 as merged before RSI started.
- **New decision:** A rework round is one findings file followed by its fix push — one review→fix cycle — whether or not that push closes everything (0 rounds = merges after first review with zero findings; 1 round = one findings file + one fix push). Baseline excludes PRs #40, #41, #49, #50, #51 — all PRs merged 17–18 Nov 2026 before RSI started.
- **Reason:** The definition as written scores a PR that needed exactly one fix round as 0, the same as a PR that needed none — the loop's only outcome metric would undercount. The exclusion list named only two of the five pre-RSI merges; an incomplete record invites retrofitted numbers later.
- **Supersedes:** none (corrects wording, not a prior decision)

## D-0003 — 2026-11-18 — Glenn

- **Artifact / gate:** artifact-chain/RSI.md (RSI spec), artifact-chain/evals/metrics/baseline.md
- **Question:** Run Recursive Self-Improvement on the council chain pilot?
- **Previous decision:** None — first RSI decision.
- **New decision:** Yes. RSI = Recursive Self-Improvement, approved for Pathfinder God on council-chain-pilot. Single metric rework rounds per PR (secondary: first-review P0/P1 counts, CI first-pass, gate dwell). Budget: max 1 chain change per batch of 3 PRs, one variable per turn, revert on 2 consecutive worsening batches. Baseline = next 3 PRs, change nothing, metrics files only; PRs merged before RSI started are not baseline data. Every chain change goes through a diff on the pilot branch with Glenn's approval; no auto-commit, auto-push, or auto-merge.
- **Reason:** The council loop already produces code; RSI feeds each run's outcome back into the machinery (skills, templates, thresholds, evals) so the chain gets better at producing mergeable work first time.
- **Supersedes:** none
