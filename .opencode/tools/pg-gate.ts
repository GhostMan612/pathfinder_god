import { tool } from "@opencode-ai/plugin"
import path from "path"
import { readFileSync, readdirSync, statSync, existsSync } from "fs"
import { execFileSync } from "child_process"

type Check = { id: string; ok: boolean; evidence: string }

function walk(dir: string, acc: string[] = []): string[] {
  if (!existsSync(dir)) return acc
  for (const entry of readdirSync(dir)) {
    if (entry === "build" || entry === ".gradle" || entry === ".kotlin" || entry === "node_modules")
      continue
    const full = path.join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) walk(full, acc)
    else if (/\.(kt|xml|yml|yaml|md|toml|properties|java)$/.test(entry)) acc.push(full)
  }
  return acc
}

function read(f: string): string {
  try {
    return readFileSync(f, "utf8")
  } catch {
    return ""
  }
}

function rel(root: string, f: string) {
  return f.replace(root + path.sep, "").replace(/\\/g, "/")
}

export default tool({
  description:
    "Run the mechanical half of a BP-06 gate (G6-0..G6-9) for one work package and return a PASS/FAIL check list with evidence lines. Never certifies device-only behaviour; those are reported as HUMAN. Does not mutate the repo.",
  timeout: 60_000,
  args: {
    wp: tool.schema
      .number()
      .int()
      .min(0)
      .max(9)
      .describe("BP-06 work package number, 0-9. Gate id is G6-<wp>."),
  },
  async execute(args, context) {
    const root = context.worktree
    const wp = args.wp
    const main = path.join(root, "spoke_kt", "app", "src", "main")
    const kotlin = path.join(main, "java", "com", "pathfindergod", "spoke")
    const checks: Check[] = []
    const human: string[] = []
    const add = (id: string, ok: boolean, evidence: string) => checks.push({ id, ok, evidence })

    const allKt = walk(kotlin)

    if (wp === 0) {
      const ci = read(path.join(root, ".github", "workflows", "ci.yml"))
      add("ci-no-release", !/assembleRelease|bundleRelease/.test(ci), ci ? "ci.yml read" : "ci.yml MISSING")
      add(
        "ci-workdir",
        /working-directory:\s*spoke_kt/.test(ci),
        (ci.match(/working-directory:.*$/m) ?? ["no working-directory"])[0].trim(),
      )
      add("ci-debug-lane", /assembleDebug/.test(ci) && /testDebugUnitTest/.test(ci), "assembleDebug+testDebugUnitTest present")
      add("ci-lfs", /lfs|large file/i.test(ci), /lfs/.test(ci) ? "lfs step present" : "lfs step MISSING")
      // The invariant is that the machine-generated daemon pin must be
      // UNTRACKED (RULES.md §5; CHECKPOINTS G6-0). The old check asserted the
      // file merely EXISTS, so a *committed* pin passed. Test the real thing:
      // the file must not be in the git index.
      const daemon = path.join(root, "spoke_kt", "gradle", "gradle-daemon-jvm.properties")
      const daemonRel = "spoke_kt/gradle/gradle-daemon-jvm.properties"
      const daemonTracked = (() => {
        try {
          return /gradle-daemon-jvm\.properties/.test(execFileSync("git", ["ls-files", daemonRel], { cwd: root, encoding: "utf-8" }))
        } catch {
          return false
        }
      })()
      add("daemon-pin-untracked", existsSync(daemon) && !daemonTracked,
        daemonTracked ? "COMMITTED — machine-local pin must never be tracked" :
        existsSync(daemon) ? "present on disk and untracked (correct)" : "not on disk (also fine)")
      add("version-catalog", existsSync(path.join(root, "spoke_kt", "gradle", "libs.versions.toml")), "spoke_kt/gradle/libs.versions.toml")
      const mf = read(path.join(main, "AndroidManifest.xml"))
      add("manifest-vibrate", /android\.permission\.VIBRATE/.test(mf), /VIBRATE/.test(mf) ? "VIBRATE declared" : "VIBRATE MISSING")
      add("manifest-no-backup", /android:allowBackup="false"/.test(mf), /allowBackup="false"/.test(mf) ? "allowBackup=false" : "allowBackup not disabled")
      human.push("CI run green on GitHub Actions")
    }

    if (wp === 1) {
      const ds = path.join(kotlin, "ui", "designsystem")
      const offenders = allKt.filter((f) => /rpgPanel\(/.test(read(f)) && !rel(root, f).startsWith("spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/designsystem"))
      add("rpg-panel-contained", offenders.length === 0, offenders.length === 0 ? "0 hits outside ui/designsystem/" : `LEAK: ${offenders.map((f) => rel(root, f)).join(", ")}`)
      const literals: string[] = []
      for (const f of walk(path.join(kotlin, "ui"))) {
        if (!f.endsWith(".kt")) continue
        const lines = read(f).split(/\r?\n/)
        lines.forEach((l, i) => {
          if (/Text\(\s*"/.test(l) || /contentDescription\s*=\s*"/.test(l))
            literals.push(`${rel(root, f)}:${i + 1}`)
        })
      }
      add("no-hardcoded-strings", literals.length === 0, literals.length === 0 ? "0 literal Text/contentDescription" : `${literals.length}: ${literals.slice(0, 8).join(", ")}`)
      add("strings-xml", existsSync(path.join(main, "res", "values", "strings.xml")), "res/values/strings.xml")
      add("designsystem-present", existsSync(ds) && readdirSync(ds).some((e) => e.startsWith("God")), existsSync(ds) ? readdirSync(ds).filter((e) => e.startsWith("God")).join(", ") : "ui/designsystem/ MISSING")
    }

    if (wp === 2) {
      const audio = read(path.join(kotlin, "service", "AudioService.kt"))
      const audioDir = path.join(main, "assets", "audio")
      const assets = existsSync(audioDir)
        ? readdirSync(audioDir).filter((f) => /\.(wav|mp3|ogg|m4a|flac)$/i.test(f))
        : []
      add("audio-dir-found", assets.length > 0, existsSync(audioDir) ? `assets/audio: ${assets.length} file(s)` : `assets/audio MISSING at ${audioDir}`)
      const unused = assets.filter((a) => !audio.includes(a))
      add("no-orphan-audio", unused.length === 0, unused.length === 0 ? `${assets.length} audio assets all referenced by AudioService` : `ORPHANS: ${unused.join(", ")}`)
      const credits = read(path.join(root, "docs", "audio-credits.md"))
      const uncredited = assets.filter((a) => !credits.includes(a))
      add("audio-credited", uncredited.length === 0, uncredited.length === 0 ? "all audio has a credit line" : `UNCREDITED: ${uncredited.join(", ")}`)
      const inApp = walk(kotlin).some((f) => /Credits/i.test(f) && read(f).includes("CC BY"))
      add("in-app-credits", inApp, inApp ? "in-app Audio Credits screen present with CC BY text" : "in-app credits screen MISSING")
      add("vibrationeffect", /VibrationEffect/.test(audio), /VibrationEffect/.test(audio) ? "VibrationEffect used" : "still HapticFeedbackType")
      add("audio-focus", /AudioFocusRequest|AudioFocus/.test(audio), /AudioFocus/.test(audio) ? "focus handling present" : "no AudioFocusRequest")
      human.push("crit and fumble haptics distinguishable on device", "Setup -> Audio Credits screen renders correctly")
    }

    if (wp === 3) {
      const shell = read(path.join(kotlin, "ui", "navigation", "NavigationShell.kt"))
      add("navhost", /NavHost|NavHostController/.test(shell), /NavHost/.test(shell) ? "NavHost present" : "no NavHost")
      add("suite-scaffold", /NavigationSuiteScaffold/.test(shell), /NavigationSuiteScaffold/.test(shell) ? "NavigationSuiteScaffold present" : "not adopted")
      add("insets", /safeDrawing/.test(shell), /safeDrawing/.test(shell) ? "safeDrawing consumed" : "insets hole still open")
      add("placeholder-gone", !existsSync(path.join(kotlin, "ui", "navigation", "PlaceholderScreen.kt")), "PlaceholderScreen.kt removed")
      add("home-dashboard", existsSync(path.join(kotlin, "ui", "home", "HomeDashboardScreen.kt")) || /HomeDashboardScreen/.test(shell), "HomeDashboardScreen present")
      human.push("all 9 destinations reachable in <=2 taps", "predictive back works from every sub-screen")
    }

    if (wp === 4) {
      const test = read(path.join(root, "spoke_kt", "app", "src", "test", "java", "com", "pathfindergod", "spoke", "ui", "pit", "DieMeshTest.kt"))
      add("centroid-normal-tests", /centroid|normal/i.test(test), /centroid|normal/i.test(test) ? "per-face centroid/normal assertions present" : "NO centroid-normal tests — animation is not licensed to start")
      const mat = read(path.join(kotlin, "ui", "pit", "PitMaterial.kt"))
      add("lit-shading", /shadingModel/.test(mat) && !/unlit/.test(mat), /shadingModel/.test(mat) ? "shadingModel declared" : "still unlit")
      const pit = read(path.join(kotlin, "ui", "pit", "FilamentPit.kt"))
      add("lights", /LightManager|addLight|IBL|ibl/i.test(pit), /LightManager|addLight/i.test(pit) ? "lights present" : "no lights")
      add("msaa", /SurfaceSwapChainConfig|msaa|samples/i.test(pit), /SurfaceSwapChainConfig|samples/i.test(pit) ? "MSAA configured" : "no MSAA")
      const dice = read(path.join(kotlin, "ui", "dice", "DiceScreen.kt"))
      add("settle-face-parity", /rollValue|rolledFace|faceValue/.test(dice), /rollValue|rolledFace|faceValue/.test(dice) ? "rolled face reaches the renderer" : "2D/3D face parity not wired")
      add("lifecycle", /LifecycleEventObserver|DefaultLifecycleObserver/.test(pit), /LifecycleEventObserver|DefaultLifecycleObserver/.test(pit) ? "render pause on background" : "no lifecycle observer")
      human.push("all 6 solids render correctly", "UV / number orientation correct on every face", "settle-to-face matches the 2D readout", "pit holds display refresh rate")
    }

    if (wp === 5) {
      const themes = read(path.join(main, "res", "values", "themes.xml"))
      add("appcompat-theme", /Theme\.AppCompat/.test(themes), /Theme\.AppCompat/.test(themes) ? (themes.match(/parent="[^"]*"/) ?? ["parent=?"])[0] : "NOT AppCompat — GameActivity will throw IllegalStateException on launch")
      const main2 = read(path.join(kotlin, "MainActivity.kt"))
      add("game-activity", /GameActivity/.test(main2), /GameActivity/.test(main2) ? "MainActivity : GameActivity()" : "GameActivity not adopted")
      // Read the whole `ui/pit` package, not two hand-picked files. The
      // setFrameRate call actually lives in PitFrameGovernor.kt, so the old
      // two-file check could not see it and FAILED a correct implementation —
      // a false negative that blocked a good WP from committing.
      const pitSrc = walk(path.join(kotlin, "ui", "pit")).filter((f) => f.endsWith(".kt")).map((f) => read(f)).join("\n")
      const hasFrameRate = /setFrameRate/.test(main2) || /setFrameRate/.test(pitSrc)
      add("frame-rate", hasFrameRate, hasFrameRate ? "explicit frame-rate request present in ui/pit" : "no setFrameRate in MainActivity or ui/pit — Android 15+ will throttle to 60Hz")
      human.push("app launches on device without IllegalStateException", "pit holds display max refresh (paste dumpsys display)")
    }

    if (wp === 6) {
      const diceTest = walk(path.join(root, "spoke_kt", "app", "src", "test")).filter((f) => /DiceEngineTest/.test(f)).map((f) => read(f)).join("\n")
      const cases = [...diceTest.matchAll(/fun\s+`?([A-Za-z0-9_]+)`?\s*\(/g)].map((m) => m[1])
      for (const topic of ["crit", "pool", "modifier", "explod"]) {
        add(`dice-test-${topic}`, cases.some((c) => new RegExp(topic, "i").test(c)), cases.filter((c) => new RegExp(topic, "i").test(c)).join(", ") || `no ${topic} test case`)
      }
      add("dice-viewmodel", existsSync(path.join(kotlin, "ui", "dice", "DiceViewModel.kt")), "DiceViewModel extracted")
      const shell = read(path.join(kotlin, "ui", "navigation", "NavigationShell.kt"))
      add("no-per-tab-factory", !/HubApiFactory\(\)/.test(shell) || /singleton|by lazy|object/.test(shell), /HubApiFactory\(\)/.test(shell) ? "HubApiFactory still constructed inline" : "singleton")
      human.push("no main-thread image decode on the map screen (profiler)")
    }

    if (wp === 7) {
      const androidTest = path.join(root, "spoke_kt", "app", "src", "androidTest")
      add("androidtest-sourceset", existsSync(androidTest) && readdirSync(androidTest).length > 0, existsSync(androidTest) ? "src/androidTest present" : "src/androidTest MISSING")
      const desc = allKt.reduce((n, f) => n + (read(f).match(/contentDescription\s*=/g) ?? []).length, 0)
      const tags = allKt.reduce((n, f) => n + (read(f).match(/testTag\(/g) ?? []).length, 0)
      add("content-descriptions", desc > 30, `${desc} contentDescription assignments (was 8 at audit)`)
      add("testtags", tags > 0, `${tags} testTag call sites`)
      const live = allKt.some((f) => /LiveRegion|liveRegion/.test(read(f)))
      add("live-regions", live, live ? "liveRegion used for roll/damage" : "no liveRegion — blind players cannot hear results")
      human.push("connectedDebugAndroidTest green", "TalkBack announces every roll and damage change", "0 touch targets under 48dp (visual audit)")
    }

    if (wp === 8) {
      const credits = read(path.join(root, "docs", "asset-credits.md"))
      add("credits-doc", credits.length > 0, credits.length > 0 ? `${credits.split(/\r?\n/).length} lines` : "docs/asset-credits.md MISSING or empty")
      human.push("every third-party asset credited in-app as well as in-repo")
    }

    if (wp === 9) {
      // Every one of these paths is real; the old `if (t.length === 0) continue`
      // silently skipped the 5 that live under blueprints/, so the doc-truth
      // gate covered 4 of 9 and still reported "sweep clean". A gate that
      // cannot say what it skipped is a gate that lies.
      const docs = ["README.md", "AGENTS.md", "RULES.md", "KOTLIN_PORT_SPEC.md", "RELEASE_NOTES.md", "CLAUDE.md", "blueprints/CHECKLIST.md", "blueprints/CHECKPOINTS.md", "blueprints/INDEX.md", "blueprints/CURRENT_STATE.md", "blueprints/ROADMAP.md"].map((d) => ({ d, t: read(path.join(root, d)) }))
      const stale: string[] = []
      const skipped: string[] = []
      for (const { d, t } of docs) {
        if (t.length === 0) { skipped.push(d); continue }
        if (/no native render surface/i.test(t)) stale.push(`${d}: "no native render surface"`)
        if (/flutter build apk|flutter analyze|flutter test/i.test(t) && !/deleted|do not|never|SUPERSEDED|retired/i.test(t)) stale.push(`${d}: live flutter command`)
        if (/spoke\/app\/main\/dart|spoke\/lib\//i.test(t)) stale.push(`${d}: flutter path`)
      }
      add("no-stale-claims", stale.length === 0, stale.length === 0 ? "sweep clean" : stale.join(" | "))
      // Never let a missing file vanish into a clean report. Surface it.
      add("doc-sweep-coverage", skipped.length === 0, skipped.length === 0 ? `all ${docs.length} doc targets read` : `NOT FOUND, sweep skipped: ${skipped.join(", ")}`)
      const ids = [...new Set([...read(path.join(root, "spoke_kt", "app", "build.gradle.kts")).matchAll(/applicationId\s*=\s*"([^"]+)"/g)].map((m) => m[1]))]
      add("single-app-id", ids.length <= 1, ids.length <= 1 ? `applicationId: ${ids[0] ?? "?"}` : `${ids.length} values: ${ids.join(", ")}`)
    }

    const failed = checks.filter((c) => !c.ok)
    const verdict = failed.length === 0 ? (human.length > 0 ? "PASS (mechanical) — human checks outstanding" : "PASS") : "FAIL"

    return [
      `G6-${wp}: ${verdict}`,
      "",
      ...checks.map((c) => `${c.ok ? "PASS" : "FAIL"}  ${c.id}  —  ${c.evidence}`),
      "",
      human.length ? "HUMAN-ONLY (never self-certify):" : "HUMAN-ONLY: none",
      ...human.map((h) => `  - ${h}`),
      "",
      failed.length === 0 ? "mechanical block complete" : `first failing: ${failed[0].id}`,
    ].join("\n")
  },
})

function pit2read(root: string) {
  return readFileSync(
    path.join(root, "spoke_kt", "app", "src", "main", "java", "com", "pathfindergod", "spoke", "ui", "pit", "FilamentPit.kt"),
    "utf8",
  )
}
