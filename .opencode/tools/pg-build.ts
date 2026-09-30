import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import path from "node:path"

const JDK_TEMURIN = "C:\\Users\\612co\\AppData\\Local\\Temp\\opencode\\jdk17\\jdk-17.0.20.1+1"
const JDK_JBR = "C:\\android\\Android Studio\\jbr"

const TASKS: Record<string, string> = {
  assembleDebug: ":app:assembleDebug",
  testDebugUnitTest: ":app:testDebugUnitTest",
  testPit: ":app:testDebugUnitTest --tests *DieMeshTest",
  testDice: ":app:testDebugUnitTest --tests *DiceEngineTest",
  lint: ":app:lintDebug",
}

const NOISE =
  /^(Download|Starting|Welcome|To honour|Closing|Deprecated|warning: |Note:|Caching|Configuration cache|Received|file or directory|Now considering|Starting a Gradle|Validating|Build cache|daemon|Kotlin Gradle|Projects loaded|Parallel|Using)/i

const KEEP = /BUILD |FAILED|SUCCESSFUL|error:|e: |> Task .*(FAILED|tested|executed)|tests? completed|Execution failed|Caused by:|^\s+at |Exception|tests? = /i

function tail(text: string, limit = 40): string {
  const lines = text.split(/\r?\n/).map((l) => l.trimEnd()).filter((l) => l.trim().length > 0)
  const interesting = lines.filter((l) => KEEP.test(l) && !NOISE.test(l))
  const chosen = (interesting.length > 0 ? interesting : lines).slice(-limit)
  return chosen.join("\n")
}

export default tool({
  description:
    "Run a permitted spoke_kt Gradle lane check with an explicit JDK and --no-daemon. Release tasks (assembleRelease/bundleRelease) are deliberately not exposed and cannot be reached through this tool. Actions: assembleDebug, testDebugUnitTest, testPit, testDice, lint.",
  timeout: 1_800_000,
  args: {
    action: tool.schema
      .enum(["assembleDebug", "testDebugUnitTest", "testPit", "testDice", "lint"])
      .describe("Lane task to run. Debug lane only."),
    jdk: tool.schema
      .enum(["temurin17", "jbr"])
      .optional()
      .describe("temurin17 (default) or jbr. WP-0 pinned temurin17."),
  },
  async execute(args, context) {
    const root = context.worktree
    const spoke = path.join(root, "spoke_kt")
    const gradlew = path.join(spoke, "gradlew.bat")

    if (!existsSync(gradlew)) {
      return `FAIL: gradlew.bat not found at ${gradlew}\nThe native lane lives in spoke_kt/, not spoke/.`
    }

    const home = args.jdk === "jbr" ? JDK_JBR : JDK_TEMURIN
    if (!existsSync(path.join(home, "bin", "java.exe"))) {
      return `FAIL: no java.exe under ${home}\nPick the other jdk value, or fix the toolchain in WP-0.`
    }

    const task = TASKS[args.action]
    const command = `"${gradlew}" ${task} --no-daemon --console=plain`
    const started = Date.now()

    const res = spawnSync("cmd.exe", ["/d", "/s", "/c", command], {
      cwd: spoke,
      encoding: "utf8",
      maxBuffer: 256 * 1024 * 1024,
      env: {
        ...process.env,
        JAVA_HOME: home,
        PATH: `${home}\\bin;${process.env.PATH ?? ""}`,
      },
    })

    const secs = ((Date.now() - started) / 1000).toFixed(1)
    const code = res.status ?? -1
    const combined = `${res.stdout ?? ""}\n${res.stderr ?? ""}`

    if (code === -1 && res.error) {
      return `FAIL: could not launch gradlew\n${res.error.message}\ncommand: ${command}`
    }

    return [
      `pg-build ${code === 0 ? "PASS" : "FAIL"}`,
      `action: ${args.action}  (${task})`,
      `jdk:    ${home}`,
      `exit:   ${code}  in ${secs}s`,
      `log:    <filtered tail>`,
      "---",
      tail(combined),
    ].join("\n")
  },
})
