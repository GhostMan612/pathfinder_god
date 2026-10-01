import { tool } from "@opencode-ai/plugin"
import path from "node:path"
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { execFileSync } from "node:child_process"

type Check = { id: string; ok: boolean; evidence: string }

const GENESIS = "As Above, So Below"

function walk(dir: string, acc: string[] = []): string[] {
  if (!existsSync(dir)) return acc
  for (const entry of readdirSync(dir)) {
    if (["build", ".gradle", ".kotlin", "node_modules"].includes(entry)) continue
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) walk(full, acc)
    else if (/\.(kt|xml|yml|yaml|md|toml|properties)$/.test(entry)) acc.push(full)
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

function gitTracked(root: string, file: string): boolean {
  try {
    return execFileSync("git", ["ls-files", "--error-unmatch", file], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim().length > 0
  } catch {
    return false
  }
}

export default tool({
  description:
    "Run the mechanical half of a BP-06 gate (G6-0..G6-9) for one work package. Returns a PASS/FAIL list with evidence and separates HUMAN-ONLY checks. Does not mutate the repo. Call ONCE per work package, after implementation is finished — never mid-edit (RULES.md 1A.2).",
  timeout: 120_000,
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

    const pitDir = path.join(kotlin, "ui", "pit")
    const pitFiles = walk(pitDir)
    const pitCorpus = pitFiles.map((f) => read(f)).join("\n")
    const navCorpus = walk(path.join(kotlin, "ui", "navigation")).map((f) => read(f)).join("\n")
    const mainActivity = read(path.join(kotlin, "MainActivity.kt"))
    const allKt = walk(kotlin)

    if (wp === 0) {
      const ci = read(path.join(root, ".github", "workflows", "ci.yml"))
      add("ci-no-release", !/assembleRelease|bundleRelease/.test(ci), "no release task in ci.yml")
      add("ci-workdir", /working-directory:\s*spoke_kt/.test(ci), (ci.match(/working-directory:\s*\S+/) ?? ["none"])[0])
      add("ci-debug-lane", /assembleDebug/.test(ci) && /testDebugUnitTest/.test(ci), "assembleDebug + testDebugUnitTest")
      // FIX: the invariant is that the generated daemon pin is UNTRACKED, not that it exists.
      const daemon = "spoke_kt/gradle/gradle-daemon-jvm.properties"
      add("daemon-pin-untracked", !gitTracked(root, daemon), gitTracked(root, daemon) ? `${daemon} IS TRACKED` : `${daemon} untracked`)
      add("version-catalog", existsSync(path.join(root, "spoke_kt", "gradle", "libs.versions.toml")), "libs.versions.toml")
      const mf = read(path.join(main, "AndroidManifest.xml"))
      add("manifest-vibrate", /android\.permission\.VIBRATE/.test(mf), /VIBRATE/.test(mf) ? "declared" : "MISSING")
      add("manifest-no-backup", /android:allowBackup="false"/.test(mf), /allowBackup="false"/.test(mf) ? "allowBackup=false" : "not disabled")
      human.push("CI run green on GitHub Actions")
    }

    if (wp === 1) {
      const offenders = allKt.filter(
        (f) => /rpgPanel\(/.test(read(f)) && !rel(root, f).includes("/ui/designsystem/"),
      )
      add(
        "rpg-panel-contained",
        offenders.length === 0,
        offenders.length === 0 ? "0 hits outside ui/designsystem/" : `LEAK: ${offenders.map((f) => rel(root, f)).join(", ")}`,
      )
      add("strings-xml", existsSync(path.join(main, "res", "values", "strings.xml")), "res/values/strings.xml")
      add("designsystem-present", existsSync(path.join(kotlin, "ui", "designsystem")), "ui/designsystem/")
    }

    if (wp === 2) {
      const audio = read(path.join(kotlin, "service", "AudioService.kt"))
      const audioDir = path.join(main, "assets", "audio")
      const assets = existsSync(audioDir) ? readdirSync(audioDir).filter((f) => /\.(wav|mp3|ogg|m4a|flac)$/i.test(f)) : []
      add("audio-dir-found", assets.length > 0, existsSync(audioDir) ? `assets/audio: ${assets.length}` : `MISSING ${audioDir}`)
      const unused = assets.filter((a) => !audio.includes(a))
      add("no-orphan-audio", unused.length === 0, unused.length === 0 ? "all referenced" : `ORPHANS: ${unused.join(", ")}`)
      const credits = read(path.join(root, "docs", "audio-credits.md"))
      const uncredited = assets.filter((a) => !credits.includes(a))
      add("audio-credited", uncredited.length === 0, uncredited.length === 0 ? "all credited in-repo" : `UNCREDITED: ${uncredited.join(", ")}`)
      const creditsScreen = allKt.find((f) => /Credits/i.test(f))
      const screenText = creditsScreen ? read(creditsScreen) : ""
      const stringsText = read(path.join(root, "spoke_kt", "app", "src", "main", "res", "values", "strings.xml"))
      const attributionInScreen = /CC BY/.test(screenText)
      const attributionInStrings = /CC BY/.test(stringsText)
      const attributionReferenced = /credits_license_by\d+/.test(screenText)
      const inApp = Boolean(creditsScreen) && (attributionInScreen || (attributionInStrings && attributionReferenced))
      add(
        "in-app-credits",
        inApp,
        !creditsScreen
          ? "in-app credits screen MISSING"
          : inApp
            ? `in-app credits screen with CC BY (${attributionInScreen ? "in screen" : "via strings.xml"})`
            : "credits screen found but no CC BY attribution reachable",
      )
      add("vibrationeffect", /VibrationEffect/.test(audio), /VibrationEffect/.test(audio) ? "present" : "HapticFeedbackType still in use")
      human.push("crit and fumble haptics distinguishable on device")
    }

    if (wp === 3) {
      add("navhost", /NavHost\(/.test(navCorpus), /NavHost\(/.test(navCorpus) ? "NavHost present" : "no NavHost")
      add("suite-scaffold", /NavigationSuiteScaffold/.test(navCorpus), /NavigationSuiteScaffold/.test(navCorpus) ? "present" : "not adopted")
      const navSource = read(path.join(kotlin, "ui", "navigation", "NavigationItem.kt"))
      // The bottom bar is the NavigationItem enum, NOT the Destinations object.
      // Destinations also holds overflow entries and sub-routes (hero detail,
      // map viewer, audio credits), so counting Destination( calls counts the
      // wrong thing. Count the enum's constants instead.
      const enumStart = navSource.indexOf("enum class NavigationItem")
      const enumEnd = enumStart < 0 ? -1 : navSource.indexOf("\n}", enumStart)
      const enumBody = enumStart < 0 || enumEnd < 0 ? null : navSource.slice(enumStart, enumEnd)
      // Match the enum constant lines directly; a capturing-group lookahead is
      // fragile across formatting. Note the last constant ends in ";" not ",".
      const itemCount = enumBody
        ? (enumBody.split("\n").filter((l) => /^\s{2,}[A-Z][A-Z0-9_]*\s*\(/.test(l)).length)
        : 0
      add("nav-le-four", itemCount >= 3 && itemCount <= 5, `${itemCount} bottom-bar destinations (cap 3-5)`)
      add("insets", /safeDrawing/.test(navCorpus), /safeDrawing/.test(navCorpus) ? "safeDrawing consumed" : "insets hole open")
      human.push("all 9 destinations reachable in <=2 taps", "predictive back from every sub-screen")
    }

    if (wp === 4) {
      const test = walk(path.join(root, "spoke_kt", "app", "src", "test"))
        .filter((f) => /DieMeshTest|PitSettleTest/.test(f))
        .map((f) => read(f))
        .join("\n")
      const cases = [...test.matchAll(/fun\s+`?(\w+)`?\s*\(/g)].map((m) => m[1])
      const cent = cases.filter((c) => /centroid/i.test(c))
      add("centroid-normal-tests", cent.length > 0, cent.length > 0 ? cent.join(", ") : "NONE — animation not licensed")
      const parity = cases.filter((c) => /parity|settle|readout/i.test(c))
      add("settle-parity-tests", parity.length > 0, parity.length > 0 ? parity.join(", ") : "no 2D/3D parity test")
      add("lit-shading", /shadingModel\s*:\s*lit/.test(pitCorpus), /shadingModel\s*:\s*lit/.test(pitCorpus) ? "lit" : "unlit")
      add("lights", /LightManager|addLight/.test(pitCorpus), /LightManager|addLight/.test(pitCorpus) ? "present" : "none")
      const msaaConfigured = /SurfaceSwapChainConfig|\.samples\(|CONFIG_MSAA_\d+_SAMPLES|SwapChainFlags\.CONFIG_MSAA/.test(pitCorpus)
      add("msaa", msaaConfigured, msaaConfigured ? "configured" : "none")
      human.push("all 6 solids", "UV/number orientation", "settle-to-face parity on device", "pit holds display refresh rate")
    }

    if (wp === 5) {
      const themeFiles = ["values/themes.xml", "values-v31/themes.xml"]
      const badThemes = themeFiles.filter((f) => {
        const t = read(path.join(main, "res", f))
        return t.length > 0 && !/Theme\.AppCompat/.test(t)
      })
      add("appcompat-theme", badThemes.length === 0, badThemes.length === 0 ? `AppCompat in ${themeFiles.filter((f) => read(path.join(main, "res", f))).length} theme file(s)` : `NOT AppCompat: ${badThemes.join(", ")} — GameActivity crashes on launch`)
      add("game-activity", /GameActivity/.test(mainActivity), /GameActivity/.test(mainActivity) ? "MainActivity : GameActivity()" : "not adopted")
      // FIX: setFrameRate lives in the pit package, not only MainActivity. Scan the whole corpus.
      const rateCallers = [...pitFiles, path.join(kotlin, "MainActivity.kt")].filter((f) => /setFrameRate\(/.test(read(f)))
      add("frame-rate", rateCallers.length > 0, rateCallers.length > 0 ? rateCallers.map((f) => rel(root, f)).join(", ") : "no setFrameRate anywhere — Android 15+ throttles to 60Hz")
      add("refresh-not-hardcoded", /preferredDisplayModeId|display\.supportedModes/.test(pitCorpus), /preferredDisplayModeId|display\.supportedModes/.test(pitCorpus) ? "derived from display modes" : "refresh rate appears hardcoded")
      human.push("app launches on device without IllegalStateException", "pit holds display max refresh (dumpsys display)")
    }

    if (wp === 6) {
      const diceTest = walk(path.join(root, "spoke_kt", "app", "src", "test")).filter((f) => /DiceEngineTest/.test(f)).map((f) => read(f)).join("\n")
      const cases = [...diceTest.matchAll(/fun\s+`?(\w+)`?\s*\(/g)].map((m) => m[1])
      for (const topic of ["crit", "pool", "modifier", "explod"]) {
        const hit = cases.filter((c) => new RegExp(topic, "i").test(c))
        add(`dice-test-${topic}`, hit.length > 0, hit.join(", ") || `no ${topic} case`)
      }
      add("dice-viewmodel", existsSync(path.join(kotlin, "ui", "viewmodel", "DiceViewModel.kt")), "DiceViewModel")
      const factory = read(path.join(kotlin, "data", "network", "HubApiFactory.kt"))
      add("okhttp-singleton", /singleton|@Volatile|companion object/.test(factory) && !/fun create\(/.test(factory), /fun create\(/.test(factory) ? "per-call create() still present" : "process singleton")
      human.push("no main-thread image decode (profiler)")
    }

    if (wp === 7) {
      const at = path.join(root, "spoke_kt", "app", "src", "androidTest")
      add("androidtest-sourceset", existsSync(at) && walk(at).length > 0, existsSync(at) ? `${walk(at).length} files` : "src/androidTest MISSING")
      const tags = allKt.reduce((n, f) => n + (read(f).match(/testTag\(|GodTags\./g) ?? []).length, 0)
      add("testtags", tags > 0, `${tags} testTag references`)
      const desc = allKt.reduce((n, f) => n + (read(f).match(/contentDescription\s*=/g) ?? []).length, 0)
      add("content-descriptions", desc > 30, `${desc} contentDescription assignments`)
      const live = allKt.filter((f) => /liveRegion\s*=/.test(read(f)))
      add("live-regions", live.length > 0, `${live.length} file(s) declare liveRegion`)
      const small = allKt.filter((f) => /godTouch(Height|Size)\(/.test(read(f)))
      add("touch-target-floors", small.length > 0, `${small.length} file(s) apply a 48dp floor`)
      human.push("connectedDebugAndroidTest green", "TalkBack announces every roll and damage change")
    }

    if (wp === 8) {
      const docs = ["docs/asset-credits.md", "docs/audio-credits.md"]
      const missing = docs.filter((d) => !existsSync(path.join(root, d)))
      add("registers-exist", missing.length === 0, missing.length === 0 ? docs.join(", ") : `MISSING: ${missing.join(", ")}`)
      const credits = read(path.join(root, "docs", "asset-credits.md")) + read(path.join(root, "docs", "audio-credits.md"))
      const media = [
        ...(existsSync(path.join(main, "assets", "audio")) ? readdirSync(path.join(main, "assets", "audio")) : []),
        ...(existsSync(path.join(main, "res", "drawable")) ? readdirSync(path.join(main, "res", "drawable")).filter((f) => f.startsWith("ki_") || f.startsWith("gi_")) : []),
      ]
      const uncredited = media.filter((m) => !credits.includes(m))
      add("media-credited", uncredited.length === 0, uncredited.length === 0 ? `${media.length} media credited` : `UNCREDITED: ${uncredited.join(", ")}`)
      human.push("every third-party asset credited in-app as well as in-repo")
    }

    if (wp === 9) {
      // FIX: a sweep must not silently skip a path that does not exist. Missing = FAIL.
      const targets = [
        "README.md",
        "AGENTS.md",
        "RULES.md",
        "KOTLIN_PORT_SPEC.md",
        "CLAUDE.md",
        "blueprints/INDEX.md",
        "blueprints/CURRENT_STATE.md",
        "blueprints/ROADMAP.md",
        "blueprints/CHECKLIST.md",
        "blueprints/CHECKPOINTS.md",
      ]
      const missing = targets.filter((t) => !existsSync(path.join(root, t)))
      add("sweep-targets-exist", missing.length === 0, missing.length === 0 ? `${targets.length} targets present` : `MISSING (cannot be swept): ${missing.join(", ")}`)

      const stale: string[] = []
      for (const t of targets.filter((x) => existsSync(path.join(root, x)))) {
        const body = read(path.join(root, t))
        if (/no native render surface/i.test(body)) stale.push(`${t}: "no native render surface"`)
        if (/(^|[^-\w])spoke\/lib\//.test(body)) stale.push(`${t}: flutter path spoke/lib/`)
        if (/com\.pathfindergod(?![\w.])/.test(body)) stale.push(`${t}: stale applicationId com.pathfindergod`)
        if (/flutter analyze|flutter test/.test(body)) stale.push(`${t}: live flutter command`)
      }
      add("no-stale-claims", stale.length === 0, stale.length === 0 ? "sweep clean across present targets" : stale.join(" | "))

      const dangling: string[] = []
      for (const t of ["AGENTS.md", "RULES.md", "README.md", "KOTLIN_PORT_SPEC.md"]) {
        const body = read(path.join(root, t))
        for (const m of body.matchAll(/`(\.opencode\/[a-z]+\/[a-z0-9_-]+\.md)`/g)) {
          if (!existsSync(path.join(root, m[1]))) dangling.push(`${t} cites missing ${m[1]}`)
        }
      }
      add("no-dangling-refs", dangling.length === 0, dangling.length === 0 ? "all .opencode citations resolve" : dangling.join(" | "))
    }

    // Cross-cutting: Genesis header on every .kt, always.
    const noHeader = allKt.filter((f) => !read(f).includes(GENESIS))
    add("genesis-headers", noHeader.length === 0, noHeader.length === 0 ? `${allKt.length} .kt files all headed` : `${noHeader.length} missing: ${noHeader.slice(0, 4).map((f) => rel(root, f)).join(", ")}`)

    const failed = checks.filter((c) => !c.ok)
    const verdict = failed.length === 0 ? (human.length > 0 ? "PASS (mechanical) — HUMAN-ONLY outstanding" : "PASS") : "FAIL"

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