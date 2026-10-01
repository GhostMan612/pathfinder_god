---
description: Start a BP-06 work package — read the blueprint section, check prerequisites, dispatch the WP owner.
agent: bp06-orchestrator
---

Start BP-06 work package **$ARGUMENTS** (a number 0-9, or a name like `wp4`).

Do this, in order, and stop at the first failure:

1. Read `RULES.md` §2 (native lane) and §5 (git discipline).
2. Read `blueprints/blueprint-sections/BP-06-professional-companion.md` — the section for the requested WP, plus §6 (gate table).
3. Confirm the execution order has been respected. The fixed order is:
   WP-0 → WP-2 → WP-1 → WP-3 → WP-6 → WP-4 → WP-5 → WP-7 → WP-8 → WP-9.
   If an earlier WP is not green, say so and name the blocker. Do not start out of order.
4. Check that WP's prerequisites are landed. Known hard ones:
   - WP-1 needs WP-0 (CI/toolchain).
   - WP-3 needs WP-1 (`GodCard` and friends).
   - WP-4 needs WP-6.
   - WP-5 needs WP-4 **and** the AppCompat theme reparent, or it crashes on launch.
   - WP-8 needs WP-2's in-app Audio Credits screen.
5. Dispatch exactly ONE WP owner subagent via Task. Never two.
6. Report the owner, the skill it must load, the gate id, and the human-only checks that will remain.

The WP owner returns a change summary. It does not commit. You gate, then commit.
