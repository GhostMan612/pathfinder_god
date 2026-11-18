// Shared shape for the five pg-* tools.
//
// OpenCode V2 registers tools through a plugin (`ctx.tool.transform`), not by
// dropping files in `.opencode/tools/`. Each pg module therefore exports a
// factory that takes the project root captured from `ctx.location.directory`
// during plugin setup, which preserves V1's `context.worktree` semantics
// without importing the retired `@opencode-ai/plugin` SDK.
export type PgToolInput = {
  readonly type: "object"
  readonly properties: Record<string, unknown>
  readonly required?: readonly string[]
  readonly additionalProperties: false
}

export type PgTool = {
  readonly name: string
  readonly description: string
  readonly input: PgToolInput
  // Arguments are validated against `input` by OpenCode before execute runs.
  // The index signature keeps each module's own narrowing readable.
  readonly execute: (input: Record<string, any>) => Promise<{ content: string }>
}
