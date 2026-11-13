"""SQLite schema. Three layers: raw JSON, cleaned tables, and views for analysis."""
import sqlite3
from pathlib import Path

SCHEMA = """
-- Tracked players
CREATE TABLE IF NOT EXISTS players (
    puuid TEXT PRIMARY KEY, game_name TEXT, tag_line TEXT, added_at TEXT);

-- Raw layer: the API response exactly as received. Never edited, so the
-- cleaned tables can always be rebuilt without calling the API again.
CREATE TABLE IF NOT EXISTS raw_matches (
    match_id TEXT PRIMARY KEY, fetched_at TEXT, payload TEXT);

-- Cleaned layer
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY, game_start_utc TEXT, duration_s INTEGER,
    patch TEXT, queue_id INTEGER);
CREATE TABLE IF NOT EXISTS participants (
    match_id TEXT, puuid TEXT, riot_id TEXT, champion TEXT, position TEXT,
    team_id INTEGER, win INTEGER, kills INTEGER, deaths INTEGER, assists INTEGER,
    primary_style INTEGER, sub_style INTEGER, keystone INTEGER,
    PRIMARY KEY (match_id, puuid));
CREATE TABLE IF NOT EXISTS participant_runes (
    match_id TEXT, puuid TEXT, slot INTEGER, rune_id INTEGER,
    PRIMARY KEY (match_id, puuid, slot));

-- Reference data from Data Dragon: rune and rune-tree names
CREATE TABLE IF NOT EXISTS runes (
    rune_id INTEGER PRIMARY KEY, name TEXT, tree_id INTEGER, is_keystone INTEGER);
CREATE TABLE IF NOT EXISTS rune_trees (tree_id INTEGER PRIMARY KEY, name TEXT);

-- Analysis layer: one row per game played by a tracked player.
-- Games under 5 minutes are remakes and are left out of win rates.
DROP VIEW IF EXISTS v_player_games;
CREATE VIEW v_player_games AS
SELECT pl.game_name || '#' || pl.tag_line AS player,
       m.match_id, m.game_start_utc, m.patch, m.queue_id, m.duration_s,
       p.puuid, p.champion, p.position, p.win, p.kills, p.deaths, p.assists,
       COALESCE(k.name, CAST(p.keystone AS TEXT)) AS keystone,
       COALESCE(t1.name, CAST(p.primary_style AS TEXT)) AS primary_tree,
       COALESCE(t2.name, CAST(p.sub_style AS TEXT)) AS secondary_tree
FROM participants p
JOIN players pl ON pl.puuid = p.puuid
JOIN matches m ON m.match_id = p.match_id
LEFT JOIN runes k ON k.rune_id = p.keystone
LEFT JOIN rune_trees t1 ON t1.tree_id = p.primary_style
LEFT JOIN rune_trees t2 ON t2.tree_id = p.sub_style
WHERE m.duration_s >= 300;
"""


def connect(path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn
