"""Extract: pull data from Riot and store it untouched in the raw layer."""
import json
from datetime import datetime, timezone

import requests

DDRAGON = "https://ddragon.leagueoflegends.com"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sync_player(client, conn, riot_id: str, count: int = 50) -> dict:
    """Fetch a player's recent matches, skipping any already stored.

    Skipping stored matches makes the run incremental and safe to repeat:
    running it twice never duplicates data or wastes rate limit.
    """
    game_name, tag_line = riot_id.split("#", 1)
    account = client.get_account(game_name, tag_line)
    puuid = account["puuid"]
    conn.execute(
        "INSERT INTO players VALUES (?, ?, ?, ?) ON CONFLICT(puuid) DO UPDATE "
        "SET game_name = excluded.game_name, tag_line = excluded.tag_line",
        (puuid, account.get("gameName", game_name), account.get("tagLine", tag_line), _now()))

    match_ids, start = [], 0
    while len(match_ids) < count:  # the API returns at most 100 ids per call
        page = client.get_match_ids(puuid, start=start, count=min(100, count - len(match_ids)))
        if not page:
            break
        match_ids += page
        start += len(page)

    have = {row[0] for row in conn.execute("SELECT match_id FROM raw_matches")}
    new_ids = [m for m in match_ids if m not in have]
    for i, match_id in enumerate(new_ids, 1):
        payload = client.get_match(match_id)
        conn.execute("INSERT OR IGNORE INTO raw_matches VALUES (?, ?, ?)",
                     (match_id, _now(), json.dumps(payload)))
        conn.commit()  # commit each match so an interrupted run keeps its progress
        print(f"  {riot_id}: fetched {i}/{len(new_ids)}", end="\r")
    conn.commit()
    return {"player": riot_id, "found": len(match_ids), "new": len(new_ids)}


def sync_runes(conn, session=None) -> int:
    """Load rune names from Data Dragon (Riot's static data; needs no key)."""
    session = session or requests.Session()
    version = session.get(f"{DDRAGON}/api/versions.json", timeout=15).json()[0]
    trees = session.get(
        f"{DDRAGON}/cdn/{version}/data/en_US/runesReforged.json", timeout=15).json()
    return load_runes(conn, trees)


def load_runes(conn, trees: list[dict]) -> int:
    n = 0
    for tree in trees:
        conn.execute("INSERT OR REPLACE INTO rune_trees VALUES (?, ?)", (tree["id"], tree["name"]))
        for slot_index, slot in enumerate(tree["slots"]):
            for rune in slot["runes"]:
                conn.execute("INSERT OR REPLACE INTO runes VALUES (?, ?, ?, ?)",
                             (rune["id"], rune["name"], tree["id"], int(slot_index == 0)))
                n += 1
    conn.commit()
    return n
