import { tool } from "@opencode-ai/plugin"
import path from "path"
import { existsSync, readFileSync, readdirSync, statSync } from "fs"

const MEDIA = /\.(wav|mp3|ogg|m4a|flac|png|webp|jpg|jpeg|svg|ttf|otf|ktx|glb|gltf|filamat)$/i

function walk(dir: string, acc: string[] = []): string[] {
  if (!existsSync(dir)) return acc
  for (const entry of readdirSync(dir)) {
    if (entry === "build" || entry === ".gradle" || entry === ".kotlin") continue
    const full = path.join(dir, entry)
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
    "Audit shipped media in spoke_kt against the credit registers. Reports uncredited assets (shipped with no license line in docs/asset-credits.md or docs/audio-credits.md) and orphan assets (present on disk but never referenced from Kotlin source). Read-only. Gate helper for WP-2 and WP-8.",
  args: {
    includeIcons: tool.schema
      .boolean()
      .optional()
      .describe("Also report mipmap/launcher-scale bitmaps. Default false to keep signal high."),
  },
  async execute(args, context) {
    const root = context.worktree
    const main = path.join(root, "spoke_kt", "app", "src", "main")
    const kotlinDir = path.join(main, "java")

    const roots = [
      path.join(main, "res", "raw"),
      path.join(main, "assets"),
      path.join(main, "res", "drawable"),
      path.join(main, "res", "drawable-hdpi"),
      path.join(main, "res", "drawable-xhdpi"),
      path.join(main, "res", "drawable-xxhdpi"),
      path.join(main, "res", "drawable-xxxhdpi"),
      path.join(main, "res", "mipmap-anydpi-v26"),
      path.join(main, "res", "mipmap-hdpi"),
      path.join(main, "res", "mipmap-xhdpi"),
      path.join(main, "res", "mipmap-xxhdpi"),
      path.join(main, "res", "mipmap-xxxhdpi"),
    ]

    const shipped = roots
      .flatMap((r) => walk(r))
      .filter((f) => MEDIA.test(f))
      .filter((f) => (args.includeIcons === true ? true : !f.includes("ic_launcher")))

    const registers = ["docs/asset-credits.md", "docs/audio-credits.md", "docs/credits.md"]
      .map((r) => ({ r, t: read(path.join(root, r)) }))
      .filter((x) => x.t.length > 0)
    const corpus = registers.map((x) => x.t).join("\n").toLowerCase()
    const source = walk(kotlinDir)
      .filter((f) => /\.(kt|xml|toml|properties)$/.test(f))
      .map((f) => read(f))
      .join("\n")
      .toLowerCase()

    const uncredited: string[] = []
    const orphans: string[] = []
    const credited: string[] = []

    for (const f of shipped) {
      const name = path.basename(f)
      const stem = name.replace(MEDIA, "").toLowerCase()
      const inRegister = corpus.includes(name.toLowerCase()) || (stem.length > 3 && corpus.includes(stem))
      if (inRegister) credited.push(name)
      else uncredited.push(path.relative(root, f).replace(/\\/g, "/"))
      if (!source.includes(stem) && !source.includes(name.toLowerCase()))
        orphans.push(path.relative(root, f).replace(/\\/g, "/"))
    }

    const lines = [
      `pg-license  ${uncredited.length === 0 && orphans.length === 0 ? "PASS" : "FAIL"}`,
      `registers:   ${registers.length ? registers.map((r) => r.r).join(", ") : "NONE FOUND — credits cannot be verified"}`,
      `shipped:     ${shipped.length} media files`,
      `credited:    ${credited.length}`,
      `uncredited:  ${uncredited.length}`,
      `orphans:     ${orphans.length}  (on disk, never referenced from Kotlin/XML source)`,
    ]
    if (uncredited.length) lines.push("", "UNCREDITED — add a license line to docs/asset-credits.md or docs/audio-credits.md:", ...uncredited.map((u) => `  - ${u}`))
    if (orphans.length) lines.push("", "ORPHANS — wire them or delete them:", ...orphans.map((o) => `  - ${o}`))
    if (!registers.length)
      lines.push("", "No credit register exists. WP-2 must create the in-app Audio Credits screen and docs/asset-credits.md before any asset ships.")
    if (uncredited.length === 0 && orphans.length === 0)
      lines.push("", "Every shipped asset has a credit line and is referenced. Gate G6-2/G6-8 credit half satisfied.")
    return lines.join("\n")
  },
})
