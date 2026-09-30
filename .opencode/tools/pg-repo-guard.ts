import { tool } from "@opencode-ai/plugin"
import path from "node:path"
import { execFileSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"

const GENESIS = "As Above, So Below"
const SECRET =
  /(api[_-]?key|secret[_-]?key|password\s*[:=]\s*["'][^"']+|bearer\s+[A-Za-z0-9._-]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})/i
const FORBIDDEN = [
  { re: /(^|\/)build\//, why: "build output" },
  { re: /(^|\/)\.gradle\//, why: "gradle cache" },
  { re: /(^|\/)node_modules\//, why: "node_modules" },
  { re: /\.(apk|aab|keystore|jks)$/, why: "release/keystore artifact" },
  { re: /(^|\/)local\.properties$/, why: "machine-local SDK path" },
  { re: /(^|\/)blueprints\//, why: "gitignored by RULES.md 1.3" },
  { re: /(^|\/)spoke\/(?!$)/, why: "deleted Flutter tree" },
  { re: /\.exe$/, why: "binary" },
]

function git(args: string[], cwd: string): string {
  try {
    return execFileSync("git", args, { cwd, encoding: "utf8", maxBuffer: 32 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] })
  } catch (e) {
    return String((e as { stdout?: string }).stdout ?? "")
  }
}

export default tool({
  description:
    "RULES.md compliance guard for the current diff. Checks the Genesis header on every changed .kt, scans changed files for secrets, rejects build artifacts / local.properties / keystores / blueprints / the deleted Flutter spoke, and reports staged vs unstaged state. Read-only: it never stages or commits. Call once per work package, immediately before the commit.",
  timeout: 60_000,
  args: {
    staged: tool.schema.boolean().optional().describe("Inspect the staged set only (pre-commit). Default false = everything dirty vs HEAD."),
  },
  async execute(args, context) {
    const root = context.worktree
    const stagedOnly = args.staged === true

    const porcelain = git(["status", "--porcelain"], root)
    const entries = porcelain.split(/\r?\n/).filter(Boolean)
    const files = [...new Set(entries.map((l) => (l.includes("->") ? l.split(" -> ")[1] : l).slice(3).trim().replace(/^"|"$/g, "")).filter(Boolean))]
    const target = stagedOnly ? entries.filter((l) => !l.startsWith(" ")).map((l) => l.slice(3).trim()) : files

    const findings: string[] = []
    const ok: string[] = []
    let kts = 0

    for (const f of target) {
      const bad = FORBIDDEN.find((x) => x.re.test(f))
      if (bad) {
        findings.push(`FORBIDDEN PATH   ${f}  (${bad.why})`)
        continue
      }
      const full = path.join(root, f)
      if (!existsSync(full)) continue
      let body: string
      try {
        body = readFileSync(full, "utf8")
      } catch {
        continue
      }
      if (f.endsWith(".kt")) {
        kts++
        if (body.includes(GENESIS)) ok.push(`genesis ok  ${f}`)
        else findings.push(`MISSING GENESIS HEADER  ${f}`)
      }
      if (/\.(kt|xml|yml|yaml|md|toml|properties|kts)$/.test(f)) {
        const m = body.match(SECRET)
        if (m) findings.push(`POSSIBLE SECRET   ${f}  ->  ${m[0].slice(0, 30)}`)
      }
      if (f.endsWith(".kt") && body.includes("\r\n")) {
        findings.push(`CRLF LINE ENDINGS  ${f}  (.gitattributes requires eol=lf)`)
      }
    }

    const untracked = entries.filter((l) => l.startsWith("??")).map((l) => l.slice(3).trim())
    const head = git(["log", "--oneline", "-1"], root).trim()

    return [
      `pg-repo-guard  ${findings.length === 0 ? "PASS" : "FAIL"}`,
      `scope:     ${stagedOnly ? "staged only" : "all changes vs HEAD"}`,
      `head:      ${head || "(no commits)"}`,
      `changed:   ${target.length} file(s), ${kts} .kt`,
      `untracked: ${untracked.length === 0 ? "none" : `${untracked.length} — ${untracked.slice(0, 6).join(", ")}`}`,
      "",
      findings.length ? "FINDINGS:" : "FINDINGS: none",
      ...findings.map((f) => `  ${f}`),
      ...(findings.length ? [] : ok.slice(0, 10).map((f) => `  ok  ${f}`)),
      "",
      findings.length
        ? "Fix every finding before committing. Genesis header is mandatory on .kt (RULES.md section 2); CRLF breaks .gitattributes eol=lf."
        : "RULES.md section 2/5 satisfied for this diff. Stage explicit paths only — never `git add .` or `git add -A`.",
    ].join("\n")
  },
})