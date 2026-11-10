#!/usr/bin/env python3
# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Smoke test for the standalone local grunt core.

Exercises read, propose, apply, the ambiguous-match guard, and the
path-traversal guard. Requires Ollama on 127.0.0.1:11450 with pf-grunt:3b.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from local_grunt import GruntError, run_grunt


def main() -> int:
    base = Path(tempfile.gettempdir()) / "opencode" / "pf-local-grunt-smoke"
    root = base / f"run-{os.getpid()}"
    root.mkdir(parents=True, exist_ok=True)
    note = root / "note.txt"
    note.write_bytes(b"alpha\nbeta\n")

    try:
        read = run_grunt(
            root=root,
            mode="read",
            task="Return the first line only. Do not explain.",
            paths=["note.txt"],
            timeout_s=120,
        )
        print("READ:")
        print(read["text"])
        print("---")

        proposal = run_grunt(
            root=root,
            mode="propose",
            task="Replace the word alpha with gamma. Keep everything else exactly as it is.",
            paths=["note.txt"],
            timeout_s=120,
        )
        print("PROPOSE:")
        print(proposal["text"])
        print("---")

        if note.read_bytes() != b"alpha\nbeta\n":
            print("SMOKE FAIL: propose wrote to the file", file=sys.stderr)
            return 1
        if not proposal.get("proposal") or not proposal["proposal"]["edits"]:
            print("SMOKE FAIL: no proposal edits", file=sys.stderr)
            return 1

        applied = run_grunt(
            root=root,
            mode="apply",
            edits=proposal["proposal"]["edits"],
        )
        print("APPLY:")
        print(applied["text"])
        print("---")

        after = note.read_bytes()
        print("FILE AFTER:")
        print(repr(after))
        if after != b"gamma\nbeta\n":
            print("SMOKE FAIL: edit did not apply exactly", file=sys.stderr)
            return 1
        print("SMOKE PASS: read/propose/apply")

        multi = root / "multi.txt"
        multi.write_bytes(b"x\nx\n")
        try:
            run_grunt(
                root=root,
                mode="apply",
                edits=[{"path": "multi.txt", "old": "x", "new": "y"}],
            )
            print("SMOKE FAIL: ambiguous edit was applied", file=sys.stderr)
            return 1
        except GruntError as exc:
            print(f"SMOKE PASS: ambiguous edit refused ({exc})")

        try:
            run_grunt(
                root=root,
                mode="read",
                task="read the file",
                paths=["../outside.txt"],
            )
            print("SMOKE FAIL: traversal path was accepted", file=sys.stderr)
            return 1
        except GruntError as exc:
            print(f"SMOKE PASS: traversal refused ({exc})")

        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
