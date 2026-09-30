import { tool } from "@opencode-ai/plugin"
import path from "node:path"
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"

const MEDIA = /\.(wav|mp3|ogg|m4a|flac|png|webp|jpg|jpeg|svg|ttf|otf)$/i

function walk(dir: string, acc: string[] = []): string[] {
  if (!existsSync(dir)) return acc
  for (const e of readdirSync(dir)) {
    if (["build", ".gradle", ".kotlin"].includes(e)) continue
    const full = path.join(dir, e)
    if (statSync(full).isDirectory()) walk(full, acc)
    else acc.push(full)
  }
  return acc
}

function read(f: string) {
  try {
    return readFileSync(f, "utf8")
  } catch {
    return ""
  }
}

export default tool({
  description:
    "Audit shipped media in spoke_kt against the credit registers. Reports media with no license line in docs/asset-credits.md or docs/audio-credits.md (a CC BY compliance failure) and orphan media present on disk but never referenced from source. Read-only. Call once per work package.",
  args: {
    includeIcons: tool.schema.boolean().optional().describe("Also report launcher-scale bitmaps. Default false."),
  },
  async execute(args, context) {
    const root = context.worktree
    const main = path.join(root, "spoke_kt", "app", "src", "main")
    const dirs = [
      path.join(main, "assets", "audio"),
      path.join(main, "res", "drawable"),
      path.join(main, "assets"),
    ]
    const shipped = [...new Set(dirs.flatMap((d) => walk(d)))]
      .filter((f) => MEDIA.test(f))
      .filter((f) => (args.includeIcons === true ? true : !f.includes("ic_launcher")))

    const registers = ["docs/asset-credits.md", "docs/audio-credits.md", "docs/credits.md"]
      .map((r) => ({ r, t: read(path.join(root, r)) }))
      .filter((x) => x.t.length > 0)
    const corpus = registers.map((x) => x.t).join("\n")
    const source = walk(path.join(main, "java")).map((f) => read(f)).join("\n") + read(path.join(main, "res", "values", "strings.xml"))

    const uncredited: string[] = []
    const orphans: string[] = []
    for (const f of shipped) {
      const name = path.basename(f)
      if (!corpus.includes(name)) uncredited.push(path.relative(root, f).replace(/\\/g, "/"))
      const stem = name.replace(MEDIA, "")
      if (stem.length > 3 && !source.includes(stem) && !source.includes(name)) {
        orphans.push(path.relative(root, f).replace(/\\/g, "/"))
      }
    }

    const lines = [
      `pg-license  ${uncredited.length === 0 && orphans.length === 0 ? "PASS" : "FAIL"}`,
      `registers:  ${registers.length ? registers.map((r) => r.r).join(", ") : "NONE FOUND — credits cannot be verified"}`,
      `shipped:    ${shipped.length} media files`,
      `uncredited: ${uncredited.length}`,
      `orphans:    ${orphans.length}`,
    ]
    if (!registers.length) lines.push("", "No credit register exists. CC BY assets cannot ship until one does.")
    if (uncredited.length) lines.push("", "UNCREDITED:", ...uncredited.map((u) => `  - ${u}`))
    if (orphans.length) lines.push("", "ORPHANS:", ...orphans.map((o) => `  - ${o}`))
    return lines.join("\n")
  },
})