"""Analysis queries used by the dashboard. Each returns a pandas DataFrame."""
import pandas as pd

QUEUES = {420: "Ranked Solo/Duo", 440: "Ranked Flex", 400: "Normal Draft",
          430: "Normal Blind", 490: "Quickplay", 450: "ARAM"}


def _where(player, queue_id, patch):
    clauses, params = ["player = ?"], [player]
    if queue_id is not None:
        clauses.append("queue_id = ?"); params.append(queue_id)
    if patch is not None:
        clauses.append("patch = ?"); params.append(patch)
    return " AND ".join(clauses), params


def players(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT game_name || '#' || tag_line FROM players ORDER BY 1")]


def games(conn, player, queue_id=None, patch=None) -> pd.DataFrame:
    where, params = _where(player, queue_id, patch)
    return pd.read_sql_query(
        f"SELECT * FROM v_player_games WHERE {where} ORDER BY game_start_utc DESC",
        conn, params=params)


def winrate_by(conn, column, player, queue_id=None, patch=None, min_games=1) -> pd.DataFrame:
    """Games, wins and win rate grouped by one column of v_player_games."""
    allowed = {"champion", "keystone", "primary_tree", "position", "patch",
               "champion, keystone"}
    if column not in allowed:
        raise ValueError(f"column must be one of {sorted(allowed)}")
    where, params = _where(player, queue_id, patch)
    return pd.read_sql_query(
        f"""SELECT {column}, COUNT(*) AS games, SUM(win) AS wins,
                   ROUND(100.0 * SUM(win) / COUNT(*), 1) AS win_rate,
                   ROUND(1.0 * (SUM(kills) + SUM(assists)) / MAX(SUM(deaths), 1), 2) AS kda
            FROM v_player_games WHERE {where}
            GROUP BY {column} HAVING COUNT(*) >= ?
            ORDER BY games DESC, win_rate DESC""",
        conn, params=params + [min_games])


def rune_pages(conn, player, queue_id=None, patch=None, min_games=1) -> pd.DataFrame:
    """Win rate for each full rune page (all six runes) a player has used."""
    where, params = _where(player, queue_id, patch)
    return pd.read_sql_query(
        f"""WITH pages AS (
                SELECT pr.match_id, pr.puuid,
                       GROUP_CONCAT(COALESCE(r.name, pr.rune_id), ' / ') AS rune_page
                FROM (SELECT * FROM participant_runes ORDER BY match_id, puuid, slot) pr
                LEFT JOIN runes r ON r.rune_id = pr.rune_id
                GROUP BY pr.match_id, pr.puuid)
            SELECT g.champion, pages.rune_page, COUNT(*) AS games, SUM(g.win) AS wins,
                   ROUND(100.0 * SUM(g.win) / COUNT(*), 1) AS win_rate
            FROM v_player_games g
            JOIN pages ON pages.match_id = g.match_id AND pages.puuid = g.puuid
            WHERE {where}
            GROUP BY g.champion, pages.rune_page HAVING COUNT(*) >= ?
            ORDER BY games DESC, win_rate DESC""",
        conn, params=params + [min_games])
