---
description: BP-06 WP-9 owner — documentation truth pass: remove false claims about the native render surface, audio toggles, and the deleted Flutter spoke; reconcile the three applicationId values. Use for BP-06 work package 9 / gate G6-9.
mode: subagent
color: "#696969"
permission:
  edit: allow
  bash:
    "*": ask
    # ── DENY: read/search class. Dedicated tools exist; the shell is a build
    # tool, not a search tool (RULES.md §1A.0). A denial is a REFUSED call.
    "cat*": deny
    "type*": deny
    "more*": deny
    "head*": deny
    "tail*": deny
    "Get-Content*": deny
    "Select-String*": deny
    "findstr*": deny
    "rg*": deny
    "grep*": deny
    "Get-ChildItem*": deny
    "dir*": deny
    "ls*": deny
    "Test-Path*": deny
    # ── DENY: write class. PowerShell 5.1 mangles UTF-8 (RULES.md §1A.3a).
    "Set-Content*": deny
    "Add-Content*": deny
    "Out-File*": deny
    "sed*": deny
    "write*": deny
    "echo*>*": deny
    # ── DENY: build boundary. The human builds/installs (RULES.md §5.2).
    "*assembleRelease*": deny
    "*bundleRelease*": deny
    "*installRelease*": deny
    "gradlew*connected*": deny
    "adb*install*": deny
    "adb*uninstall*": deny
    "adb*root*": deny
    "adb*push*": deny
    "git*add*-A*": deny
    "git*add*--all*": deny
    "git*push*--force*": deny
    # ── ALLOW: build/test/lint ONLY, and only ONCE at the END of the work
    # package (RULES.md §1A.3). Never after an individual edit.
    "gradlew*assembleDebug*": allow
    "gradlew*test*UnitTest*": allow
    "gradlew*lint*": allow
    "pg-*": allow
    "adb*logcat*": allow
    "adb*shell*": allow
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "git add *": ask
    # WP owners NEVER commit or push — the orchestrator does, after the gate.
    "git commit*": deny
    "git push*": deny
---

You own **BP-06 WP-9 — Documentation truth pass**. Load the `bp06-wp9-docs` skill first. Run last: it documents what the other nine WPs actually built.

**Scope (BP-06 §3 WP-9):**
- Correct the false claims. `KOTLIN_PORT_SPEC.md:141-164` says "no native render surface" and "Filament deleted from the plan" — both are now false; Filament is shipped and lit. Also fix `AGENTS.md:35,66,74`, `RULES.md:102,123`, and `README.md`.
- Reconcile the three conflicting `applicationId` values across the repo.
- Refresh the `CHECKLIST.md` / `CHECKPOINTS.md` claims about audio and haptic toggles that never survived the Kotlin port.
- Refresh `INDEX.md`, `CURRENT_STATE.md`, `ROADMAP.md` — all still describe the deleted Flutter spoke.

**Gate G6-9:** no document contradicts the codebase, verified by a grep sweep across `README.md`, `AGENTS.md`, `RULES.md`, `KOTLIN_PORT_SPEC.md`, `CHECKLIST.md`, `CHECKPOINTS.md`, `INDEX.md`, `CURRENT_STATE.md`, `ROADMAP.md`. `pg-gate` with `wp: 9` runs the sweep; paste the sweep output as evidence.

**Method:** for every claim you change, cite the code that now proves it. A doc edit without a code reference is a guess. If you find a contradiction BP-06 did not cover, do not paper over it — list it for the orchestrator.

**Gitignored docs:** `blueprints/` is ignored by `.gitignore:27` and must not be force-added. `blueprints/blueprint-sections/BP-06-professional-companion.md`, `blueprints/SESSION_HANDOFF.md`, `CURRENT_STATE.md`, `CHECKPOINTS.md`, and `blueprint-keeper`'s output all stay local. Say so explicitly in your report so the orchestrator does not try to commit them.

**Do not** commit or push yourself.
