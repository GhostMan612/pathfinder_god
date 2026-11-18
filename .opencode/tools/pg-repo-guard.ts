import path from "node:path"
import { execFileSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import type { PgTool } from "../lib/pg-tool"

const GENESIS = "As Above, So Below"
// A secret is a NAME BOUND TO A VALUE, not a name. The previous pattern matched the bare
// token `api[_-]?key` with no value at all, so it flagged:
//   - shared/openapi.yaml's `APIKeyHeader:` security-scheme identifier (type: apiKey,
//     header X-API-Key) - a schema name, 13 occurrences, no material in it;
//   - the `X-API-Key` header name in docs and Kotlin sources.
// Every hit was a false positive, and a guard that cries wolf gets ignored, which is worse
// than no guard. So a name now has to be assigned a plausible value. This still catches the
// real cases: api_key = "...", secretKey: "...", password: "...", bearer <token>,
// sk-.../ghp_... provider tokens.
const SECRET = new RegExp(
  [
    // The whole name list must be ONE group, otherwise `|` splits the outer alternation and
    // bare `password` / `secret_key` match on their own with no value required.
    String.raw`(?:(?:api|secret|access|auth|private|encryption|signing)[_-]?key|secret|password|passwd|auth[_-]?token|access[_-]?token|bearer[_-]?token|token)`,
    // optional closing quote after the name, so JSON/Kotlin `"authToken": "..."` is caught
    String.raw`["']?\s*[:=]\s*["']?[A-Za-z0-9+/=._\-]{8,}["']?`,
    // provider-style tokens, matched anywhere
    String.raw`|bearer\s+[A-Za-z0-9._\-]{20,}`,
    String.raw`|\bsk-[A-Za-z0-9]{20,}`,
    String.raw`|\bghp_[A-Za-z0-9]{20,}`,
    String.raw`|\bAKIA[0-9A-Z]{16}\b`,
  ].join(""),
  "i",
)
const FORBIDDEN = [
  { re: /(^|\/)build\//, why: "build output" },
  { re: /(^|\/)\.gradle\//, why: "gradle cache" },
  { re: /(^|\/)node_modules\//, why: "node_modules" },
  { re: /\.(apk|aab|keystore|jks)$/, why: "release/keystore artifact" },
  { re: /(^|\/)local\.properties$/, why: "machine-local SDK path" },
  { re: /(^|\/)blueprints\//, why: "gitignored by RULES.md 1.3" },
  // The deleted Flutter tree is `spoke/` at the repo ROOT, not any path segment
  // ending in "spoke". Unanchored, this matched spoke_kt/... (the live native
  // lane) and flagged all 90 Kotlin sources as forbidden. Anchor to the root.
  { re: /^spoke\/(?!$)/, why: "deleted Flutter tree" },
  { re: /\.exe$/, why: "binary" },
]

function git(args: string[], cwd: string): string {
  try {
    return execFileSync("git", args, { cwd, encoding: "utf8", maxBuffer: 32 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] })
  } catch (e) {
    return String((e as { stdout?: string }).stdout ?? "")
  }
}

const TEXT_EXT = /\.(kt|xml|yml|yaml|md|toml|properties|kts)$/

type StagedRead =
  | { kind: "blob"; body: string }
  | { kind: "absent" } // staged deletion: nothing will be committed at this path
  | { kind: "error"; detail: string }

// `staged=true` must inspect what will actually be committed, not the working
// tree. A file can be staged with a credential and then edited (or reverted)
// without restaging; reading the worktree would report PASS while the index
// blob still carries the credential into the commit.
function readStagedBlob(root: string, file: string): StagedRead {
  try {
    execFileSync("git", ["ls-files", "--error-unmatch", "--", file], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "ignore", "pipe"],
    })
  } catch (e) {
    // ls-files --error-unmatch exits 1 when the path is not in the index
    // (staged deletion). Anything else is an unexpected read failure and must
    // fail closed rather than silently skip the file.
    const status = (e as { status?: number }).status
    const stderr = String((e as { stderr?: string }).stderr ?? "").trim()
    if (status === 1) return { kind: "absent" }
    return {
      kind: "error",
      detail: `git ls-files failed (status ${status ?? "?"}): ${stderr || (e as Error).message}`,
    }
  }
  try {
    return {
      kind: "blob",
      body: execFileSync("git", ["cat-file", "blob", `:${file}`], {
        cwd: root,
        encoding: "utf8",
        maxBuffer: 64 * 1024 * 1024,
      }),
    }
  } catch (e) {
    return { kind: "error", detail: `git cat-file :${file} failed: ${(e as Error).message}` }
  }
}

export const pgRepoGuard = (root: string): PgTool => ({
  name: "pg-repo-guard",
  description:
    "RULES.md compliance guard for the current diff. Checks the Genesis header on every changed .kt, scans changed files for secrets, rejects build artifacts / local.properties / keystores / blueprints / the deleted Flutter spoke, and reports staged vs unstaged state. With staged=true it reads the exact index blobs, so the report matches what will be committed. Read-only: it never stages or commits. Call once per work package, immediately before the commit.",
  input: {
    type: "object",
    properties: {
      staged: {
        type: "boolean",
        description: "Inspect the staged set only (pre-commit). Default false = everything dirty vs HEAD.",
      },
    },
    additionalProperties: false,
  },
  async execute(args) {
    const stagedOnly = args.staged === true

    const porcelain = git(["status", "--porcelain"], root)
    const entries = porcelain.split(/\r?\n/).filter(Boolean)
    const pathOf = (l: string) => (l.includes(" -> ") ? l.split(" -> ")[1] : l).slice(3).trim().replace(/^"|"$/g, "")
    const files = [...new Set(entries.map(pathOf).filter(Boolean))]
    // Staged means an index status letter (M/A/R/D/C) in column 1. Untracked
    // entries (`??`) and worktree-only edits (` M`) are not staged; including
    // them made `staged=true` scan every local overlay and report them as part
    // of the commit. Staged renames keep the destination path, like `files`.
    const target = stagedOnly
      ? entries.filter((l) => !l.startsWith(" ") && !l.startsWith("??")).map(pathOf)
      : files

    const findings: string[] = []
    const ok: string[] = []
    let kts = 0

    for (const f of target) {
      const bad = FORBIDDEN.find((x) => x.re.test(f))
      if (bad) {
        findings.push(`FORBIDDEN PATH   ${f}  (${bad.why})`)
        continue
      }
      let body: string
      if (stagedOnly) {
        const staged = readStagedBlob(root, f)
        if (staged.kind === "absent") continue
        if (staged.kind === "error") {
          findings.push(`STAGED READ ERROR   ${f}  ->  ${staged.detail}`)
          continue
        }
        body = staged.body
      } else {
        const full = path.join(root, f)
        if (!existsSync(full)) continue
        try {
          body = readFileSync(full, "utf8")
        } catch {
          continue
        }
      }
      if (f.endsWith(".kt")) {
        kts++
        if (body.includes(GENESIS)) ok.push(`genesis ok  ${f}`)
        else findings.push(`MISSING GENESIS HEADER  ${f}`)
      }
      if (TEXT_EXT.test(f)) {
        const m = body.match(SECRET)
        if (m) findings.push(`POSSIBLE SECRET   ${f}  ->  ${m[0].slice(0, 30)}`)
      }
      if (f.endsWith(".kt") && body.includes("\r\n")) {
        findings.push(`CRLF LINE ENDINGS  ${f}  (.gitattributes requires eol=lf)`)
      }
    }

    const untracked = entries.filter((l) => l.startsWith("??")).map((l) => l.slice(3).trim())
    const head = git(["log", "--oneline", "-1"], root).trim()

    const report = [
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

    return { content: report }
  },
})