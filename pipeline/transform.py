"""Transform: turn raw match JSON into clean, queryable tables."""
import json
from datetime import datetime, timezone


def parse_match(payload: dict) -> dict:
    """Pure function: one raw match in, rows for each cleaned table out."""
    info = payload["info"]
    match_id = payload["metadata"]["matchId"]
    start = datetime.fromtimestamp(info["gameCreation"] / 1000, tz=timezone.utc)
    patch = ".".join(info.get("gameVersion", "").split(".")[:2])  # "16.22.1.2" -> "16.22"

    match_row = (match_id, start.isoformat(timespec="seconds"),
                 info.get("gameDuration", 0), patch, info.get("queueId"))
    participant_rows, rune_rows = [], []
    for p in info["participants"]:
        styles = {s.get("description"): s for s in p.get("perks", {}).get("styles", [])}
        primary, sub = styles.get("primaryStyle", {}), styles.get("subStyle", {})
        rune_ids = [s["perk"] for s in primary.get("selections", [])] + \
                   [s["perk"] for s in sub.get("selections", [])]
        riot_id = f"{p.get('riotIdGameName', '')}#{p.get('riotIdTagline', '')}"
        participant_rows.append((
            match_id, p["puuid"], riot_id, p.get("championName"),
            p.get("teamPosition") or None, p.get("teamId"), int(bool(p.get("win"))),
            p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0),
            primary.get("style"), sub.get("style"), rune_ids[0] if rune_ids else None))
        rune_rows += [(match_id, p["puuid"], slot, rune) for slot, rune in enumerate(rune_ids)]
    return {"match": match_row, "participants": participant_rows, "runes": rune_rows}


def rebuild(conn) -> int:
    """Rebuild every cleaned table from the raw layer. Returns matches processed."""
    for table in ("matches", "participants", "participant_runes"):
        conn.execute(f"DELETE FROM {table}")
    count = 0
    for (payload,) in conn.execute("SELECT payload FROM raw_matches").fetchall():
        rows = parse_match(json.loads(payload))
        conn.execute("INSERT INTO matches VALUES (?, ?, ?, ?, ?)", rows["match"])
        conn.executemany("INSERT INTO participants VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         rows["participants"])
        conn.executemany("INSERT INTO participant_runes VALUES (?, ?, ?, ?)", rows["runes"])
        count += 1
    conn.commit()
    return count
