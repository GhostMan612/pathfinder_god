import { tool } from "@opencode-ai/plugin"
import path from "path"
import { execFileSync } from "child_process"
import { existsSync, readFileSync } from "fs"

const GENESIS = "As Above, So Below"
const SECRET = /(api[_-]?key|secret[_-]?key|password\s*[:=]\s*["'][^"']+|bearer\s+[A-Za-z0-9._-]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})/i
const FORBIDDEN = [
  /(^|\/)(build|\.gradle|\.kotlin|node_modules)\//,
  /\.(apk|aab|keystore|jks)$/,
  /(^|\/)local\.properties$/,
  /(^|\/)blueprints\//,
  /(^|\/)spoke\/(?!$)/,
]

function git(args: string[], cwd: string): string {
  try {
    return execFileSync("git", args, { cwd, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 })
  } catch (e) {
    return String((e as { stdout?: string }).stdout ?? "")
  }
}

export default tool({
  description:
    "RULES.md compliance guard for the current BP-06 diff. Checks the Genesis header on every changed .kt, scans changed files for secrets, rejects build artifacts / local.properties / keystores / force-added blueprints / the deleted Flutter spoke, and reports staged vs unstaged state. Read-only on content; it never stages or commits.",
  args: {
    staged: tool.schema
      .boolean()
      .optional()
      .describe("Inspect the staged set only (pre-commit check). Default false = everything dirty vs HEAD."),
  },
  async execute(args, context) {
    const root = context.worktree
    const staged = args.staged === true
    const raw = staged
      ? git(["diff", "--cached", "--name-only"], root)
      : git(["status", "--porcelain"], root)

    const paths = raw
      .split(/\r?\n/)
      .map((l) => (staged ? l.trim() : l.slice(3).trim()))
      .map((l) => l.replace(/^"|"$/g, ""))
      .filter((l) => l && !l.includes(" -> "))
    const renames = raw
      .split(/\r?\n/)
      .filter((l) => l.includes(" -> "))
      .map((l) => l.split(" -> ")[1]?.replace(/^"|"$/g, "") ?? "")

    const files = [...new Set([...paths, ...renames])].filter(Boolean)
    const porcelain = git(["status", "--porcelain"], root).split(/\r?\n/).filter(Boolean)
    const untracked = porcelain.filter((l) => l.startsWith("??")).map((l) => l.slice(3).trim())

    const findings: string[] = []
    const ok: string[] = []

    for (const f of files) {
      const full = path.join(root, f)
      if (FORBIDDEN.some((re) => re.test(f))) {
        findings.push(`FORBIDDEN PATH  ${f}`)
        continue
      }
      if (!existsSync(full)) continue
      if (f.endsWith(".kt")) {
        const body = readFileSync(full, "utf8")
        if (!body.includes(GENESIS)) findings.push(`MISSING GENESIS HEADER  ${f}`)
        else ok.push(`genesis ok  ${f}`)
      }
      if (/\.(kt|xml|yml|yaml|md|toml|properties|json|gradle|gradle\.kts)$/.test(f) || f.endsWith(".kts")) {
        const body = readFileSync(full, "utf8")
        const m = body.match(SECRET)
        if (m) findings.push(`POSSIBLE SECRET  ${f}  ->  ${m[0].slice(0, 40)}`)
      }
    }

    const branch = git(["rev-parse", "--abbrev-ref", "HEAD"], root).trim()
    const head = git(["log", "--oneline", "-1"], root).trim()
    const clean = porcelain.length === 0

    return [
      `pg-repo-guard  ${findings.length === 0 ? "PASS" : "FAIL"}`,
      `scope:    ${staged ? "staged only" : "all changes vs HEAD"}`,
      `branch:   ${branch}`,
      `head:     ${head}`,
      `changed:  ${files.length} file(s)`,
      `untracked:${untracked.length === 0 ? " none" : ` ${untracked.length} — ${untracked.slice(0, 6).join(", ")}`}`,
      `worktree: ${clean ? "clean" : `${porcelain.length} dirty entr${porcelain.length === 1 ? "y" : "ies"}`}`,
      "",
      findings.length ? "FINDINGS:" : "FINDINGS: none",
      ...findings.map((f) => `  ${f}`),
      ...(findings.length ? [] : ok.slice(0, 12).map((f) => `  ok  ${f}`)),
      "",
      findings.length
        ? "Fix every finding before committing. Genesis header is mandatory on .kt (RULES.md section 2)."
        : "RULES.md section 2/5 satisfied for this diff. Still stage explicit paths only — never `git add .` or `git add -A`.",
    ].join("\n")
  },
})
