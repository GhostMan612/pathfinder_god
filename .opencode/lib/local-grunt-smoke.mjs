import { mkdir, readFile, rm, writeFile } from "node:fs/promises"
import path from "node:path"
import { localGrunt } from "./local-grunt-core.mjs"

const base = "C:\\Users\\612co\\AppData\\Local\\Temp\\opencode\\pf-local-grunt-smoke"
const root = path.join(base, `run-${Date.now()}`)
await mkdir(root, { recursive: true })
const file = path.join(root, "note.txt")
await writeFile(file, "alpha\nbeta\n", "utf8")

try {
  const read = await localGrunt({
    root,
    task: "Return the first line only. Do not explain.",
    paths: ["note.txt"],
    mode: "read",
    timeoutMs: 120_000,
  })
  console.log("READ:")
  console.log(read.text)
  console.log("---")

  const proposal = await localGrunt({
    root,
    task: "Replace the word alpha with gamma. Keep everything else exactly as it is.",
    paths: ["note.txt"],
    mode: "propose",
    timeoutMs: 120_000,
  })
  console.log("PROPOSE:")
  console.log(proposal.text)
  console.log("---")

  const beforeApply = await readFile(file, "utf8")
  if (beforeApply !== "alpha\nbeta\n") {
    console.error("SMOKE FAIL: propose wrote to the file")
    process.exitCode = 1
  }

  if (!proposal.proposal || proposal.proposal.edits.length === 0) {
    console.error("SMOKE FAIL: no proposal edits")
    process.exitCode = 1
  } else {
    const applied = await localGrunt({
      root,
      mode: "apply",
      task: "Apply the reviewed proposal.",
      edits: proposal.proposal.edits,
    })
    console.log("APPLY:")
    console.log(applied.text)
    console.log("---")
  }

  const after = await readFile(file, "utf8")
  console.log("FILE AFTER:")
  console.log(JSON.stringify(after))
  if (after !== "gamma\nbeta\n") {
    console.error("SMOKE FAIL: edit did not apply exactly")
    process.exitCode = 1
  } else {
    console.log("SMOKE PASS: read/propose/apply")
  }

  const multi = path.join(root, "multi.txt")
  await writeFile(multi, "x\nx\n", "utf8")
  try {
    await localGrunt({
      root,
      mode: "apply",
      edits: [{ path: "multi.txt", old: "x", new: "y" }],
    })
    console.error("SMOKE FAIL: ambiguous edit was applied")
    process.exitCode = 1
  } catch (error) {
    console.log(`SMOKE PASS: ambiguous edit refused (${error.message})`)
  }

  try {
    await localGrunt({
      root,
      mode: "read",
      task: "read the file",
      paths: ["../outside.txt"],
    })
    console.error("SMOKE FAIL: traversal path was accepted")
    process.exitCode = 1
  } catch (error) {
    console.log(`SMOKE PASS: traversal refused (${error.message})`)
  }
} finally {
  await rm(root, { recursive: true, force: true })
}
