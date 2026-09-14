# Rules database

One FTS5 table, two editions, 43,884 rows. The laptop owns the master copy;
the phone ships a gzip of it inside the APK.

## Shape

`data/pathfinder_rag.db`, table `rules` (FTS5: `name, raw_content, system,
category, source_book`). Full column contract: [`../data/SCHEMA.md`](../data/SCHEMA.md).

| Fact (2026-09-14) | Value |
|---|---|
| Rows | 43,884 (1E 22,131 · 2E 21,753) |
| Size | 57MB (phone asset: 20MB gzip) |
| `system` | `1E`/`2E` UPPERCASE everywhere |
| Categories | canonical lowercase (`feat`, `spell`, `equipment`, `bestiary`, `action`, …) — never book names |
| `Unknown Source` rows | 8,926 legacy (ranked last, shrinking per import) |
| Content | plain text, HTML stripped |

## Sources (all open, all attributed per-row in `source_book`)

| Source | Edition | What | License |
|---|---|---|---|
| Paizo PRD JSON (via devonjones/PSRD-Data) | 1e | Core, Bestiaries 1–4, Ultimates, APG… (12,232 rows) | OGL |
| Pf2ools JSON | 2e | Backgrounds, conditions, skills, Player's Guides | MIT / CUP |
| pfsqlite YAML (jrmiller82) | 2e | OGL classes/spells/feats pipeline | Community Use |
| Archives of Nethys scrapes | both | Targeted gap-fills only | CUP |
| d20pfsrd scrapes | 1e | Targeted gap-fills only | OGL |

Fetched copies live under `hub/scripts/external/` (git-ignored, reproducible).
**Deliberately excluded:** adventure-path prose and Golarion lore (Product
Identity) — mechanics only. Personal use is fine; **commercial redistribution
rights are unverified**.

## Search ranking (hub + phone, identical tiers)

1. Exact `name` match (`COLLATE NOCASE`) — `flanking` → *Flanking · Core Rulebook*.
2. FTS5 `rank` over known-source rows.
3. FTS5 over `Unknown Source` rows.

Deduped by lowercase name; 2E searched before 1E on `edition=both`.

## Rebuild pipeline

```powershell
C:\venv-hub\venv\Scripts\python.exe hub/scripts/rebuild_rags.py
```

- `hub/scripts/db_normalize.py` — shared cleanup (categories, source repair,
  HTML strip, longest-wins dedupe preferring known sources).
- `hub/scripts/build_rag.py` — 1e side into `data/pathfinder_rag.db.new`.
- `hub/scripts/build_2e_rag.py` — appends the 2e side.
- `rebuild_rags.py` — validates (`integrity_check`, counts), backs the live DB
  up to `.bak`, swaps, `VACUUM` + `ANALYZE`.
- `hub/scripts/importers/` — `psrd_importer.py` (1e PRD), `pf2ools_importer.py`
  (2e JSON, inserts + upgrades Unknown rows), `pathfinder_2_sqlite_importer.py`.
- `hub/scripts/scrapers/` — rate-limited AoN 2e / AoN 1e / d20pfsrd fetchers
  (run targeted, never full-site).
- `hub/scripts/sources.yaml` — source registry (priority, license, URLs).

Builders accept `--pf2ools PATH` / `--yaml PATH` to fold open data in.

## Phone bundling

```powershell
# gzip -9 data/pathfinder_rag.db → spoke/assets/rules/pathfinder_rag.db.gz (Git LFS)
```

Then bump `RulebookDb.bundleVersion` in `spoke/lib/services/rulebook_db.dart`
or devices keep the stale extracted copy. Extraction streams 8KB natively
(Kotlin `AssetManager→GZIP`), `Isolate` fallback, static open-lock.
