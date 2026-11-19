#!/usr/bin/env bash
# check-chain.sh — heuristic chain-consistency check for an artifact chain.
# Usage: ./evals/check-chain.sh [chain-root]   (default: current directory)
# Checks:
#   1. Every requirement ID (R1, R2, ...) in spec/*.md appears in plan/*.md.
#   2. Every plan task heading (T1, T2, ...) cites >= 1 requirement ID
#      within its task block.
#   3. Reports (does not fail) on spec/plan slug mismatches.
# README.md files are ignored. Exit 0 = pass, 1 = orphan(s) found.
set -u

ROOT="${1:-.}"
SPEC_DIR="$ROOT/spec"
PLAN_DIR="$ROOT/plan"
fail=0

spec_files=()
plan_files=()
[ -d "$SPEC_DIR" ] && for f in "$SPEC_DIR"/*.md; do
  [ -e "$f" ] || continue
  [ "$(basename "$f")" = "README.md" ] && continue
  spec_files+=("$f")
done
[ -d "$PLAN_DIR" ] && for f in "$PLAN_DIR"/*.md; do
  [ -e "$f" ] || continue
  [ "$(basename "$f")" = "README.md" ] && continue
  plan_files+=("$f")
done

if [ "${#spec_files[@]}" -eq 0 ] && [ "${#plan_files[@]}" -eq 0 ]; then
  echo "check-chain: no spec/plan files yet — nothing to check."
  exit 0
fi

# --- Check 1: every requirement ID is cited by some plan file. ---
if [ "${#spec_files[@]}" -gt 0 ] && [ "${#plan_files[@]}" -gt 0 ]; then
  req_ids=$(grep -hoE '\bR[0-9]+\b' "${spec_files[@]}" 2>/dev/null | sort -u)
  for rid in $req_ids; do
    if ! grep -rqE "\b$rid\b" "${plan_files[@]}" 2>/dev/null; then
      echo "ORPHAN REQUIREMENT: $rid is in spec/ but cited by no plan file."
      fail=1
    fi
  done
fi

# --- Check 2: every task block cites a requirement ID. ---
# One awk pass per plan file; task state flushes at each new task
# heading and at end of file. Word boundaries are written portably
# (no \b) so the script works under gawk and mawk alike.
for pf in "${plan_files[@]}"; do
  awk '
    function flush() {
      if (task != "" && !seen) {
        printf "ORPHAN TASK: %s in %s cites no requirement ID (R<n>).\n", tid, fname
        bad = 1
      }
    }
    FNR == 1 && NR != 1 { flush(); task = ""; seen = 0 }
    /^### T[0-9]+/ {
      flush()
      task = $0; fname = FILENAME; seen = 0
      if (match($0, /T[0-9]+/)) tid = substr($0, RSTART, RLENGTH)
      if ($0 ~ /(^|[^A-Za-z0-9_])R[0-9]+([^A-Za-z0-9_]|$)/) seen = 1
      next
    }
    /(^|[^A-Za-z0-9_])R[0-9]+([^A-Za-z0-9_]|$)/ { seen = 1 }
    END { flush(); exit (bad ? 1 : 0) }
  ' "$pf" || fail=1
done

# --- Check 3 (report only): slug mismatches between spec/ and plan/. ---
for sf in "${spec_files[@]}"; do
  slug=$(basename "$sf" .md)
  [ -e "$PLAN_DIR/$slug.md" ] || echo "NOTE: spec/$slug.md has no matching plan/$slug.md yet."
done
for pf in "${plan_files[@]}"; do
  slug=$(basename "$pf" .md)
  [ -e "$SPEC_DIR/$slug.md" ] || echo "NOTE: plan/$slug.md has no matching spec/$slug.md."
done

if [ "$fail" -eq 0 ]; then
  echo "check-chain: OK — no orphan requirements or tasks."
fi
exit "$fail"
