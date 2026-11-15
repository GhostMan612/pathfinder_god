import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "node:child_process"
import { existsSync, readdirSync } from "node:fs"
import path from "node:path"

// The lane JDK is Temurin 17, but its location is NOT stable: the old pin lived under
// %TEMP%\opencode\jdk17, and Windows purged that directory between sessions. A single
// hardcoded path therefore turns a working lane into "no java.exe under ..." on a fresh
// boot. Resolve by probing candidates and accepting the first that actually has a JVM.
const JDK_JBR_DIRS = [
  "C:\\android\\Android Studio\\jbr",
  "C:\\Program Files\\Android\\Android Studio\\jbr",
]

// Studio/IntelliJ download toolchains into a jdks/ folder; pick any 17.x there.
const JDK_SEARCH_ROOTS = [
  "C:\\android\\Android Studio\\jbr\\jdks",
  "C:\\Program Files\\Android\\Android Studio\\jbr\\jdks",
  "C:\\Users\\612co\\.jdks",
]

const JDK_TEMURIN_17_PREFERRED = [
  "C:\\android\\Android Studio\\jbr\\jdks\\eclipse_adoptium-17-amd64-windows.2",
  "C:\\Users\\612co\\AppData\\Local\\Temp\\opencode\\jdk17\\jdk-17.0.20.1+1",
]

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

function hasJava(home: string): boolean {
  return existsSync(path.join(home, "bin", "java.exe"))
}

function resolveJdk(label: "temurin17" | "jbr"): { home: string; tried: string[] } {
  const candidates: string[] = []
  const tried: string[] = []

  if (label === "jbr") {
    candidates.push(...JDK_JBR_DIRS)
  } else {
    // An explicit JAVA_HOME wins, but only if it is a real JVM directory: CI images and
    // stale shells routinely export a path that no longer exists.
    const envHome = process.env.JAVA_HOME
    if (envHome) candidates.push(envHome)
    candidates.push(...JDK_TEMURIN_17_PREFERRED)
    for (const root of JDK_SEARCH_ROOTS) {
      if (!existsSync(root)) continue
      try {
        for (const entry of readdirSync(root)) {
          if (!/\b17\b|17[.\-]/.test(entry)) continue
          candidates.push(path.join(root, entry))
        }
      } catch {
        // An unreadable toolchain dir must not abort the search.
      }
    }
  }

  for (const home of candidates) {
    if (tried.includes(home)) continue
    tried.push(home)
    if (hasJava(home)) return { home, tried }
  }
  return { home: "", tried }
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

    const label = args.jdk ?? "temurin17"
    const { home, tried } = resolveJdk(label)
    if (!home) {
      return [
        `FAIL: no JDK with bin/java.exe found for "${label}"`,
        "Tried:",
        ...tried.map((h) => `  ${h}`),
        "Fix: export JAVA_HOME to a JDK 17 (Temurin), or install one via Android Studio's",
        "SDK Manager > SDK Tools > JDK. The lane only needs a 17+ JVM to launch Gradle;",
        "the foojay resolver provisions the compile toolchain from kotlin.jvmToolchain(17).",
      ].join("\n")
    }

    const task = TASKS[args.action]
    // cmd /s /c strips one layer of quotes, so a bare "path" wrapper makes cmd read
    // the .bat name as C:\...\gradlew.bat" <args> and fail to resolve it. The command
    // must therefore be double-wrapped: cmd /s /c ""C:\...\gradlew.bat" task ...".
    const command = `""${gradlew}" ${task} --no-daemon --console=plain"`
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
