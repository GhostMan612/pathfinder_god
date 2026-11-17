// Read-only smoke test for the V2 pg-* tool port.
//
// Proves the properties the migration must preserve without a live model call:
//   1. all five definitions expose the V2 shape (name / JSON Schema / execute);
//   2. pg-build cannot reach a release task, even when schema validation is
//      bypassed, and fails with the lane's existing message when spoke_kt is absent;
//   3. pg-gate / pg-license / pg-repo-guard run against an explicit root and
//      return { content }, so V1 context.worktree semantics survive;
//   4. root is honoured rather than the process cwd;
//   5. pg-repo-guard staged mode reads the exact index blobs, so a credential
//      staged then removed from the worktree still fails the guard.
//
// It never runs Gradle and never calls pg-hub-probe (RULES.md 1A.2 trap 3).
//
// Run: node .opencode/lib/pg-tools-smoke.mjs
import assert from "node:assert/strict"
import { mkdtemp, writeFile } from "node:fs/promises"
import { execFileSync } from "node:child_process"
import os from "node:os"
import path from "node:path"
import { pgBuild } from "../tools/pg-build.ts"
import { pgGate } from "../tools/pg-gate.ts"
import { pgHubProbe } from "../tools/pg-hub-probe.ts"
import { pgLicense } from "../tools/pg-license.ts"
import { pgRepoGuard } from "../tools/pg-repo-guard.ts"

const root = path.resolve(import.meta.dirname, "..", "..")
const empty = await mkdtemp(path.join(os.tmpdir(), "pg-tools-smoke-"))

const definitions = [
  ["pg-build", pgBuild(root)],
  ["pg-gate", pgGate(root)],
  ["pg-hub-probe", pgHubProbe()],
  ["pg-license", pgLicense(root)],
  ["pg-repo-guard", pgRepoGuard(root)],
]

for (const [name, tool] of definitions) {
  assert.equal(tool.name, name, `${name}: name`)
  assert.equal(tool.input.type, "object", `${name}: input.type`)
  assert.equal(tool.input.additionalProperties, false, `${name}: additionalProperties`)
  assert.equal(typeof tool.input.properties, "object", `${name}: properties`)
  assert.equal(typeof tool.description, "string", `${name}: description`)
  assert.equal(typeof tool.execute, "function", `${name}: execute`)
}
console.log("PASS  five definitions expose name + JSON Schema + execute")

// pg-build: the debug-lane whitelist is unchanged, and release tasks stay
// unreachable even if a caller bypasses the schema enum.
const build = pgBuild(root)
assert.deepEqual(
  build.input.properties.action.enum,
  ["assembleDebug", "testDebugUnitTest", "testPit", "testDice", "lint"],
)
for (const forbidden of ["assembleRelease", "bundleRelease"]) {
  assert.equal(build.input.properties.action.enum.includes(forbidden), false, `${forbidden} must not be exposed`)
  const refused = await build.execute({ action: forbidden })
  assert.match(refused.content, new RegExp(`unsupported action "${forbidden}"`))
  assert.match(refused.content, /deliberately not exposed/)
}
console.log("PASS  pg-build refuses assembleRelease/bundleRelease outside the schema")

const vanishedLane = await pgBuild(empty).execute({ action: "lint" })
assert.match(vanishedLane.content, /gradlew\.bat not found/)
assert.match(vanishedLane.content, /The native lane lives in spoke_kt\/, not spoke\//)
console.log("PASS  pg-build reports a missing lane with the existing message")

// pg-gate: the mechanical gate still runs and still labels HUMAN-ONLY work.
const gate = await pgGate(root).execute({ wp: 0 })
assert.match(gate.content, /^G6-0: (PASS|FAIL)/)
assert.match(gate.content, /genesis-headers/)
assert.match(gate.content, /HUMAN-ONLY/)
console.log("PASS  pg-gate returns a G6-0 report")

// pg-license: real root audits the shipped media; an empty root proves it does
// not fall back to the process cwd.
const license = await pgLicense(root).execute({})
assert.match(license.content, /^pg-license\s+(PASS|FAIL)/)
assert.match(license.content, /uncredited:/)
assert.match(license.content, /orphans:/)
const emptyLicense = await pgLicense(empty).execute({})
assert.match(emptyLicense.content, /NONE FOUND — credits cannot be verified/)
console.log("PASS  pg-license honours the captured root")

// pg-repo-guard: real root reports the current diff; an empty root has no HEAD,
// which can only happen if the tool used the passed root.
const guard = await pgRepoGuard(root).execute({})
assert.match(guard.content, /^pg-repo-guard\s+(PASS|FAIL)/)
assert.match(guard.content, /scope:\s+all changes vs HEAD/)
assert.match(guard.content, /RULES\.md section 2\/5|Fix every finding/)
const emptyGuard = await pgRepoGuard(empty).execute({})
assert.match(emptyGuard.content, /head:\s+\(no commits\)/)
assert.match(emptyGuard.content, /changed:\s+0 file\(s\), 0 \.kt/)
console.log("PASS  pg-repo-guard honours the captured root")

// pg-repo-guard staged mode must inspect the index, not the whole worktree.
// A throwaway repo with one staged edit and one untracked overlay proves the
// untracked overlay is reported separately and never counted as committed.
const repo = await mkdtemp(path.join(os.tmpdir(), "pg-guard-staged-"))
const gitIn = (args) => execFileSync("git", args, { cwd: repo, encoding: "utf8" })
gitIn(["init", "-q"])
gitIn(["config", "core.autocrlf", "false"])
gitIn(["config", "user.email", "synthetic@example.test"])
gitIn(["config", "user.name", "Synthetic Test"])
await writeFile(path.join(repo, "tracked.md"), "baseline\n")
gitIn(["add", "tracked.md"])
gitIn(["commit", "-qm", "baseline"])
await writeFile(path.join(repo, "tracked.md"), "baseline\nstaged edit\n")
await writeFile(path.join(repo, "overlay.md"), "untracked overlay\n")
gitIn(["add", "tracked.md"])
const stagedGuard = await pgRepoGuard(repo).execute({ staged: true })
assert.match(stagedGuard.content, /scope:\s+staged only/)
assert.match(stagedGuard.content, /changed:\s+1 file\(s\), 0 \.kt/)
assert.match(stagedGuard.content, /untracked: 1 — overlay\.md/)
console.log("PASS  pg-repo-guard staged mode counts only the index")

// pg-repo-guard staged mode must read the exact index blob. Divergent
// index/worktree contents are the failure mode: a staged credential removed
// from the worktree (or a staged file whose header exists only locally) must
// be judged on what the commit would contain.
const blobRepo = await mkdtemp(path.join(os.tmpdir(), "pg-guard-blob-"))
const gitBlob = (args) => execFileSync("git", args, { cwd: blobRepo, encoding: "utf8" })
gitBlob(["init", "-q"])
gitBlob(["config", "core.autocrlf", "false"])
gitBlob(["config", "user.email", "synthetic@example.test"])
gitBlob(["config", "user.name", "Synthetic Test"])
await writeFile(path.join(blobRepo, "baseline.txt"), "baseline\n")
gitBlob(["add", "baseline.txt"])
gitBlob(["commit", "-qm", "baseline"])

// A: staged credential + clean worktree -> FAIL on the index blob.
await writeFile(path.join(blobRepo, "staged-secret.md"), 'password = "s3cr3tValue123"\n')
gitBlob(["add", "staged-secret.md"])
await writeFile(path.join(blobRepo, "staged-secret.md"), "clean\n")
const dirtyIndex = await pgRepoGuard(blobRepo).execute({ staged: true })
assert.match(dirtyIndex.content, /pg-repo-guard\s+FAIL/)
assert.match(dirtyIndex.content, /POSSIBLE SECRET\s+staged-secret\.md/)
gitBlob(["reset", "--hard", "-q"])

// B: clean staged content + credential only in the worktree -> PASS.
await writeFile(path.join(blobRepo, "worktree-secret.md"), "clean\n")
gitBlob(["add", "worktree-secret.md"])
await writeFile(path.join(blobRepo, "worktree-secret.md"), 'password = "s3cr3tValue456"\n')
const cleanIndex = await pgRepoGuard(blobRepo).execute({ staged: true })
assert.match(cleanIndex.content, /pg-repo-guard\s+PASS/)
assert.doesNotMatch(cleanIndex.content, /POSSIBLE SECRET/)
gitBlob(["reset", "--hard", "-q"])

// C: the Genesis header must come from the index too.
await writeFile(path.join(blobRepo, "Staged.kt"), "fun main() = Unit\n")
gitBlob(["add", "Staged.kt"])
await writeFile(path.join(blobRepo, "Staged.kt"), "// As Above, So Below\nfun main() = Unit\n")
const unstagedHeader = await pgRepoGuard(blobRepo).execute({ staged: true })
assert.match(unstagedHeader.content, /MISSING GENESIS HEADER\s+Staged\.kt/)
gitBlob(["reset", "--hard", "-q"])
console.log("PASS  pg-repo-guard staged mode reads index blobs")

// pg-hub-probe: schema only. Executing it mid-work is forbidden by RULES.md 1A.2.
const probe = pgHubProbe()
assert.deepEqual(Object.keys(probe.input.properties).sort(), ["base", "timeoutMs"])
assert.equal(probe.input.properties.timeoutMs.type, "integer")
console.log("PASS  pg-hub-probe keeps its end-of-plan schema (not executed)")

console.log(`\npg-tools smoke: PASS (root=${root})`)
