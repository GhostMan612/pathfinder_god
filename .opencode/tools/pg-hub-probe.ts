import { tool } from "@opencode-ai/plugin"

const ENDPOINTS = [
  { id: "health", path: "/health", method: "GET" as const },
  { id: "rules-search", path: "/rules/search?q=flanking&edition=2e&limit=3", method: "GET" as const },
  { id: "ask", path: "/ask", method: "POST" as const, body: { question: "What is the modifier for flanking an enemy?", edition: "2e" } },
]

export default tool({
  description:
    "END-OF-PLAN ONLY. Probe the local Python Hub (:8000) health, FTS5 rules search, and /ask fallback chain and return structured pass/fail. Read-only — never mutates the rules DB or campaign data. Reports the backend actually used, so you can prove the Ollama -> raw FTS5 fallback still works with the laptop.\n\n" +
    "⛔ Do NOT call this mid-implementation. This is a live 120s HTTP round-trip against a running service; it is verification, not a lookup, and RULES.md §1A.3 batches verification to the end of a work package. Use read/grep/glob/edit while you work; call this once when the WP is done.",
  timeout: 120_000,
  args: {
    base: tool.schema
      .string()
      .optional()
      .describe("Hub base URL. Default http://127.0.0.1:8000. Emulator device uses 10.0.2.2, real device uses the laptop LAN IP."),
    timeoutMs: tool.schema.number().int().optional().describe("Per-request timeout in ms. Default 30000."),
  },
  async execute(args) {
    const base = (args.base ?? "http://127.0.0.1:8000").replace(/\/$/, "")
    const timeoutMs = args.timeoutMs ?? 30_000
    const out: string[] = [`pg-hub-probe  base=${base}`]

    for (const ep of ENDPOINTS) {
      const ac = new AbortController()
      const timer = setTimeout(() => ac.abort(), timeoutMs)
      const started = Date.now()
      try {
        const res = await fetch(`${base}${ep.path}`, {
          method: ep.method,
          headers: { "content-type": "application/json" },
          body: ep.body ? JSON.stringify(ep.body) : undefined,
          signal: ac.signal,
        })
        const text = (await res.text()).slice(0, 400).replace(/\s+/g, " ")
        const ms = Date.now() - started
        let verdict = `HTTP ${res.status}`
        if (res.ok) {
          if (ep.id === "health") verdict = /ok|healthy|status/i.test(text) ? "healthy" : `HTTP ${res.status} (unexpected body)`
          if (ep.id === "rules-search") {
            const n = (text.match(/"name"/g) ?? []).length
            verdict = n > 0 ? `${n} FTS5 result(s) — offline rules path live` : "no results — FTS5 lookup empty"
          }
          if (ep.id === "ask") {
            const backend = text.match(/"backend"\s*:\s*"([^"]+)"/)?.[1]
            const answer = text.match(/"(?:answer|response)"\s*:\s*"([^"]*)"/)?.[1]
            verdict = `backend=${backend ?? "?"}${answer ? ` answer="${answer.slice(0, 60)}..."` : ""}`
          }
        }
        out.push(`PASS  ${ep.id.padEnd(13)} ${verdict}  (${ms}ms)`)
      } catch (e) {
        const msg = (e as Error).name === "AbortError" ? `timeout after ${timeoutMs}ms` : (e as Error).message
        out.push(`FAIL  ${ep.id.padEnd(13)} ${msg}`)
        if (ep.id === "health") {
          out.push("", "Hub is not reachable. Start it with:  cd hub  &&  C:\\venv-hub\\venv\\Scripts\\python.exe -m app.main")
          out.push("Ollama must be up too:  ollama serve  (0.0.0.0:11434, hub .env maps 127.0.0.1:11450)")
          break
        }
      } finally {
        clearTimeout(timer)
      }
    }

    out.push("", "Lane is local-only. No cloud tiers, no API keys — /ask should resolve to Ollama or raw FTS5, never an external provider.")
    return out.join("\n")
  },
})
