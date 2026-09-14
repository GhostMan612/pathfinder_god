-- ============================================================
-- As Above, So Below. As Within, So Without.
-- The Future Dictates the Past and the Past is Always Present.
-- ============================================================

-- Campaign & Continuity Database Schema
-- Run this on campaign.db (separate from pathfinder_rag.db)

-- ──────────────────────────────────────────────────────────────
-- Core Campaign
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT 'Unnamed Campaign',
    edition TEXT NOT NULL DEFAULT '2e',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ──────────────────────────────────────────────────────────────
-- Session Log (append-only, one row per session)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    session_num INTEGER NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    summary TEXT,                    -- 500-word narrative summary
    facts_json TEXT,                 -- JSON array of {fact, category, confidence}
    raw_log TEXT,                    -- Full chat log (optional, for debugging)
    UNIQUE(campaign_id, session_num)
);

-- ──────────────────────────────────────────────────────────────
-- Entities extracted by Continuity Keeper
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS npcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    alias TEXT,
    role TEXT CHECK(role IN ('ally','enemy','neutral','unknown')) DEFAULT 'unknown',
    level INTEGER,
    ancestry TEXT,
    class TEXT,
    location_id INTEGER REFERENCES locations(id),
    disposition TEXT CHECK(disposition IN ('friendly','hostile','wary','unknown')) DEFAULT 'unknown',
    notes TEXT,
    first_seen_session INTEGER,
    last_seen_session INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('settlement','dungeon','wilderness','planar','other')) DEFAULT 'other',
    parent_id INTEGER REFERENCES locations(id),
    description TEXT,
    facts_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('weapon','armor','consumable','magic','artifact','currency','other')) DEFAULT 'other',
    level INTEGER,
    traits_json TEXT,           -- JSON array of traits
    holder_id INTEGER REFERENCES npcs(id),
    location_id INTEGER REFERENCES locations(id),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT CHECK(status IN ('active','completed','failed','on_hold')) DEFAULT 'active',
    giver_id INTEGER REFERENCES npcs(id),
    description TEXT,
    objectives_json TEXT,      -- JSON array of {description, completed}
    rewards_json TEXT,         -- JSON array
    started_session INTEGER,
    completed_session INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS player_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    session_num INTEGER NOT NULL,
    decision TEXT NOT NULL,
    context TEXT,
    consequences_json TEXT,    -- JSON array of known outcomes
    made_by TEXT,              -- Player name or "party"
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ──────────────────────────────────────────────────────────────
-- Party / Player Characters (synced from Spoke)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS party_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    player_name TEXT,
    class TEXT,
    level INTEGER DEFAULT 1,
    ancestry TEXT,
    background TEXT,
    stats_json TEXT,           -- Full character sheet JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(campaign_id, name)
);

-- ──────────────────────────────────────────────────────────────
-- Indexes for common queries
-- ──────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_sessions_campaign ON sessions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_npcs_campaign ON npcs(campaign_id);
CREATE INDEX IF NOT EXISTS idx_locations_campaign ON locations(campaign_id);
CREATE INDEX IF NOT EXISTS idx_items_campaign ON items(campaign_id);
CREATE INDEX IF NOT EXISTS idx_quests_campaign ON quests(campaign_id);
CREATE INDEX IF NOT EXISTS idx_decisions_campaign ON player_decisions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_party_campaign ON party_members(campaign_id);
CREATE INDEX IF NOT EXISTS idx_npcs_name ON npcs(name);
CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_quests_name ON quests(name);

-- ──────────────────────────────────────────────────────────────
-- Triggers for updated_at
-- ──────────────────────────────────────────────────────────────

CREATE TRIGGER IF NOT EXISTS trigger_campaigns_updated
AFTER UPDATE ON campaigns
BEGIN
    UPDATE campaigns SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trigger_npcs_updated
AFTER UPDATE ON npcs
BEGIN
    UPDATE npcs SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trigger_locations_updated
AFTER UPDATE ON locations
BEGIN
    UPDATE locations SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trigger_items_updated
AFTER UPDATE ON items
BEGIN
    UPDATE items SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trigger_quests_updated
AFTER UPDATE ON quests
BEGIN
    UPDATE quests SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trigger_party_updated
AFTER UPDATE ON party_members
BEGIN
    UPDATE party_members SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- ──────────────────────────────────────────────────────────────
-- Session Notes (for export/import)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS session_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    session_num INTEGER NOT NULL,
    note_type TEXT CHECK(note_type IN ('gm','player','system')) DEFAULT 'gm',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(campaign_id, session_num, id)
);

CREATE INDEX IF NOT EXISTS idx_session_notes_campaign ON session_notes(campaign_id);
CREATE INDEX IF NOT EXISTS idx_session_notes_session ON session_notes(campaign_id, session_num);