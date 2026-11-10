import { Plugin } from "@opencode/plugin"
import { localGrunt } from "../lib/local-grunt-core.mjs"

type LocalGruntEdit = {
  path: string
  old: string
  new: string
}

type LocalGruntInput = {
  mode?: "read" | "propose" | "apply"
  task?: string
  paths?: string[]
  edits?: LocalGruntEdit[]
  context?: string
}

export default Plugin.define({
  id: "pf.local-grunt",
  async setup(ctx) {
    const root = ctx.location.directory

    await ctx.tool.transform((editor) => {
      editor.add({
        name: "local_grunt",
        description:
          "Delegate a small, bounded job to the local Ollama grunt (pf-grunt:3b on 127.0.0.1:11450). Use for narrow file summaries and symbol lookups when you already know the paths. Do NOT use for architecture, security, tests, or open-ended exploration. Pass 1-8 explicit file paths. mode=read returns a concise answer. mode=propose asks the local model for exact old/new replacements and returns a reviewed proposal without writing. mode=apply applies an explicit edits array that the parent has reviewed, requiring each old string to match exactly once inside the project root. Refuses blueprints, data, assets, secrets, binaries, build output, and paths outside the repo.",
        input: {
          type: "object",
          properties: {
            mode: {
              type: "string",
              enum: ["read", "propose", "apply"],
              description: "read = answer; propose = reviewed edit proposal (no writes); apply = apply explicit reviewed edits. Default read.",
            },
            task: {
              type: "string",
              description: "The exact bounded job. Required for read and propose.",
            },
            paths: {
              type: "array",
              items: { type: "string" },
              description: "Project-relative files to send for read/propose. Max 8; the grunt cannot browse.",
            },
            edits: {
              type: "array",
              description: "Reviewed {path, old, new} edits for mode=apply. The parent must verify the proposal first.",
              items: {
                type: "object",
                properties: {
                  path: { type: "string" },
                  old: { type: "string" },
                  new: { type: "string" },
                },
                required: ["path", "old", "new"],
                additionalProperties: false,
              },
            },
            context: {
              type: "string",
              description: "Optional extra instructions or constraints for the grunt.",
            },
          },
          additionalProperties: false,
        },
        execute: async (input, context) => {
          const args = input as LocalGruntInput
          try {
            const result = await localGrunt({
              root,
              mode: args.mode ?? "read",
              task: args.task,
              paths: args.paths,
              edits: args.edits,
              context: args.context,
              signal: context.signal,
            })
            return { content: result.text }
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            return { content: `local-grunt failed: ${message}` }
          }
        },
      })
    })

    const tools = await ctx.tool.list()
    const registered = tools.find((tool) => tool.id === "local_grunt")
    if (!registered) {
      throw new Error("local_grunt tool registration failed")
    }
    console.error(`[pf.local-grunt] registered ${registered.id} (root=${root})`)
  },
})
