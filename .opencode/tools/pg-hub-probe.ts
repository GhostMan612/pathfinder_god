import { tool } from "@opencode-ai/plugin"

const ENDPOINTS = [
  { id: "health", path: "/health", method: "GET" as const },
  { id: "rules-search", path: "/rules/search?q=flanking&edition=2e&limit=3", method: "GET" as const },
]

export default tool({
  description:
    "DO NOT CALL DURING IMPLEMENTATION. This is a live HTTP probe against the running Hub (:8000) with a per-request timeout — it is an end-of-plan verification step only, per RULES.md 1A.2 trap 3 (\"one probe to see what's going on\"). If you think you need it mid-task, that is a BLOCKED item to report, not a call to make. Read-only: never mutates the rules DB or campaign data. Reports the backend actually used so the Ollama -> raw FTS5 fallback can be proven.",
  timeout: 120_000,
  args: {
    base: tool.schema.string().optional().describe("Hub base URL. Default http://127.0.0.1:8000."),
    timeoutMs: tool.schema.number().int().optional().describe("Per-request timeout in ms. Default 8000."),
  },
  async execute(args) {
    const base = (args.base ?? "http://127.0.0.1:8000").replace(/\/$/, "")
    const timeoutMs = args.timeoutMs ?? 8000
    const out: string[] = [`pg-hub-probe  base=${base}`]

    for (const ep of ENDPOINTS) {
      const ac = new AbortController()
      const timer = setTimeout(() => ac.abort(), timeoutMs)
      const started = Date.now()
      try {
        const res = await fetch(`${base}${ep.path}`, { signal: ac.signal })
        const text = (await res.text()).slice(0, 300).replace(/\s+/g, " ")
        const ms = Date.now() - started
        let verdict = `HTTP ${res.status}`
        if (res.ok) {
          if (ep.id === "health") verdict = /"status"\s*:\s*"ok"/.test(text) ? "healthy" : `HTTP ${res.status}`
          if (ep.id === "rules-search") {
            const n = (text.match(/"name"/g) ?? []).length
            verdict = n > 0 ? `${n} FTS5 hit(s) — offline rules path live` : "no hits — FTS5 lookup empty"
          }
        }
        out.push(`PASS  ${ep.id.padEnd(13)} ${verdict}  (${ms}ms)`)
      } catch (e) {
        const msg = (e as Error).name === "AbortError" ? `timeout ${timeoutMs}ms` : (e as Error).message
        out.push(`FAIL  ${ep.id.padEnd(13)} ${msg}`)
        if (ep.id === "health") {
          out.push("  Hub not reachable. Start it:  cd hub  &&  C:\\venv-hub\\venv\\Scripts\\python.exe -m app.main")
          out.push("  Ollama:  ollama serve   (0.0.0.0:11434; hub .env maps 127.0.0.1:11450)")
          break
        }
      } finally {
        clearTimeout(timer)
      }
    }
    return out.join("\n")
  },
})