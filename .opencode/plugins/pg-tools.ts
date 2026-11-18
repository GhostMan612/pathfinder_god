import { Plugin } from "@opencode/plugin"
import { pgBuild } from "../tools/pg-build.ts"
import { pgGate } from "../tools/pg-gate.ts"
import { pgHubProbe } from "../tools/pg-hub-probe.ts"
import { pgLicense } from "../tools/pg-license.ts"
import { pgRepoGuard } from "../tools/pg-repo-guard.ts"

// OpenCode V2 registers tools through a plugin transform. The V1 SDK
// (`@opencode-ai/plugin` `tool()`) is retired and its `.opencode/tools/*.ts`
// entries are inert, so this plugin is the single registration point for the
// five pg-* lane tools.
//
// Root: `ctx.location.directory` is the location this plugin instance loaded
// for. Capturing it during setup preserves V1's `context.worktree` semantics —
// a session moved into a worktree loads that location's plugins, so the tools
// follow the worktree instead of the canonical checkout.
const NAMES = ["pg-build", "pg-gate", "pg-hub-probe", "pg-license", "pg-repo-guard"] as const

export default Plugin.define({
  id: "pg.tools",
  async setup(ctx) {
    const root = ctx.location.directory
    const definitions = [
      pgBuild(root),
      pgGate(root),
      pgHubProbe(),
      pgLicense(root),
      pgRepoGuard(root),
    ]

    await ctx.tool.transform((editor) => {
      for (const definition of definitions) editor.add(definition)
    })

    // A silent non-registration is the exact regression this port fixes, so
    // fail the plugin load loudly instead of starting a session without tools.
    const registered = (await ctx.tool.list()).map((tool) => tool.id)
    const missing = NAMES.filter((name) => !registered.includes(name))
    if (missing.length > 0) {
      throw new Error(
        `pg tool registration failed: missing ${missing.join(", ")}; pg ids present: ${
          registered.filter((id) => id.startsWith("pg")).join(", ") || "none"
        }`,
      )
    }

    console.error(`[pg.tools] registered ${NAMES.join(", ")} (root=${root})`)
  },
})
