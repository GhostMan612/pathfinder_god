# Rules database schema

The Pathfinder rules live in SQLite databases under this `data/` directory on the
**laptop hub only**. They are 500MB+ and are **git-ignored** — never committed, never
shipped in the APK. This file documents their shape so the hub, tests, and the rebuild
scripts all agree.

## Files (searched in this order; first match wins per edition)

| File | Contents |
|---|---|
| `pathfinder_rag.db` | **Unified 1e + 2e** — the primary DB. Rows carry a `system` column. |
| `pathfinder_god.db` | Combined "everything" DB (either edition). |
| `pathfinder_1e_rag.db` | Pathfinder 1e only. |
| `pathfinder_2e_rag.db` | Pathfinder 2e only. |

Configure a different directory with `PFGOD_DATA_DIR` (see `hub/.env.example`).

## Primary shape — the `rules` FTS5 table

The main schema is a single FTS5 table named `rules`:

| Column | Meaning |
|---|---|
| `system` | `"1E"` or `"2E"` (UPPERCASE — both hub and Spoke compare uppercase). |
| `category` | Canonical lowercase: `feat`, `spell`, `equipment`, `bestiary`, `action`, `background`, `ancestry`, `class`, `classfeature`, `ancestryfeature`, `heritage`, `archetype`, `deity`, `condition`, `skill`, `ritual`, `trait`, `hazard`, `boon`, `rule`, `affliction`, `technology`, `familiar abilities`, `campaign effects`. Book names are NEVER categories (they go in `source_book`). |
| `name` | The rule/entry name (e.g. `Flanking`, `Goblin Warrior`). |
| `source_book` | Where it came from (e.g. `Core Rulebook`, `Bestiary`). `Unknown Source` = legacy import, ranked last. |
| `raw_content` | Plain text (HTML stripped) — what RAG retrieves and feeds the LLM. |

Search ranking (hub `app/rag/retriever.py`, `raw_fallback.py`, Spoke `rulebook_db.dart`):
exact `name` match → FTS5 `rank` over known-source rows → FTS5 over `Unknown Source` rows,
deduped by lowercase name, 2E-first then 1E fallback.

Queried as full text:

```sql
SELECT system, category, name, source_book, raw_content
FROM rules
WHERE system = ?           -- '2e' first, then '1e' (the edition fallback)
  AND rules MATCH ?        -- FTS5 match expression
LIMIT ?;
```

## Alternate shapes the hub also understands

`hub/app/rag/search.py` auto-detects the table layout, so older/alternate builds keep working:

- **`rules_fts` + `rules`** — separate FTS index joined to a content table on `rules.id`.
- **`chunks(source, content)`** — a generic chunked-text FTS table.
- **`items(name, content)`** — a generic named-entry FTS table.
- A non-FTS `rules` table falls back to `LIKE` matching.

## Rebuilding

```bash
C:\venv-hub\venv\Scripts\python.exe hub/scripts/rebuild_rags.py
```

Pipeline (`hub/scripts/`, all Genesis-headed):
- `db_normalize.py` — canonical categories, book-like category repair
  (`Pathfinder Bestiary 3` → `bestiary` + source), HTML strip, longest-wins
  dedupe preferring known sources.
- `build_rag.py` — 1e side: fresh `data/pathfinder_rag.db.new`, normalize legacy 1E.
- `build_2e_rag.py` — 2e side: appends normalized legacy 2E.
- `rebuild_rags.py` — validates (`integrity_check`, counts), backs up live DB
  to `pathfinder_rag.db.bak`, swaps, `VACUUM` + `ANALYZE`.
- `importers/pf2ools_importer.py` — Pf2ools MIT JSON (`external/pf2ools-data`,
  backgrounds/conditions/skills with real sources; inserts + upgrades Unknown).
- `importers/psrd_importer.py` — official 1e PRD JSON (`external/psrd1e`,
  from devonjones/PSRD-Data tarball skipping Windows-illegal names).
- `importers/pathfinder_2_sqlite_importer.py` — jrmiller82 YAML (2e OGL).
- `scrapers/aon_2e_scraper.py`, `aon_1e_scraper.py`, `d20pfsrd_scraper.py` —
  rate-limited AoN/d20pfsrd fetchers (run targeted, not full-site).
- `sources.yaml` — source registry (priority, license, URLs).

After rebuilding the DB, re-bundle the phone asset and bump
`RulebookDb.bundleVersion` in `spoke/lib/services/rulebook_db.dart`:

```bash
# gzip -9 data/pathfinder_rag.db → spoke/assets/rules/pathfinder_rag.db.gz
```
