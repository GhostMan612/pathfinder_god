---
description: BP-06 WP-1 owner — design system: the God* component layer, Dimens/Spacing scale, all 28 M3 color roles, Haze GlassCard, strings.xml, migrating all 25 rpgPanel call sites. Use for BP-06 work package 1 / gate G6-1.
mode: subagent
color: "#9932CC"
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

You own **BP-06 WP-1 — Design system: the `God*` component layer**. Load the `bp06-wp1-design` skill first. This is the foundation all later visual work (WP-3 nav, WP-4 pit, WP-7 a11y) depends on, so it runs before them.

**Scope (BP-06 §3 WP-1):**
- New `ui/designsystem/`: `GodCard` (the slot-bearing successor to `rpgPanel`), `GodChip`, `GodPrimaryButton`, `GodTextField`, `GodFab`, `GodEmptyState`, `GodSectionHeader`, `GodBackLink`, `GodStatTile`, `GodStatusText`, `GodBadge`, `GodProgressBar`.
- `Dimens` / `Spacing` scale and a complete `Shapes` set. `RpgModifiers.kt:18-47` is effectively the whole design system today; it becomes a thin compatibility shim that delegates, then it dies.
- Complete the color scheme: all 28 Material 3 roles. Fix D-13 (`surfaceTint`, `error`).
- `GlassCard` variant using Haze (`dev.chrisbanes.haze`, Apache 2.0) for the dashboard header.
- Bundle free serif display fonts (SIL OFL).
- Migrate **all 25** `rpgPanel()` call sites. This is the bulk of the work and it must be complete — a partial migration fails the gate.
- Add `strings.xml` and migrate every literal, including the hardcoded `"A ruined crypt"`, `"44,620"`, and the mock LLM payload at `CampaignScreen.kt:60-64`.

**Gate G6-1:** `pg-gate` with `wp: 1` green. Two grep sweeps must return clean: hits for `rpgPanel(` appear **only** inside `ui/designsystem/`, and zero hardcoded user-facing strings exist outside `strings.xml`. Report both sweep outputs as evidence.

**Watch for:** this is the widest-blast-radius WP in BP-06. It touches ~25 files across every tab. Migrate mechanically and uniformly — do not redesign individual screens opportunistically; that is WP-3's job. Haze is a new dependency; if the build fails on it, prefer a plain `GlassCard` without refraction over fighting the dependency.

**Do not** change dependency versions, the app id, or navigation structure. **Do not** commit or push yourself.
