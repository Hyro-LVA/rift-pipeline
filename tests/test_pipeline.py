"""End-to-end test using a fake Riot client, so no key or network is needed."""
from pipeline import db, extract, queries, transform

ME = "puuid-me"
TREES = [
    {"id": 8100, "name": "Domination", "slots": [
        {"runes": [{"id": 8112, "name": "Electrocute"}]},
        {"runes": [{"id": 8143, "name": "Sudden Impact"}]},
        {"runes": [{"id": 8138, "name": "Eyeball Collection"}]},
        {"runes": [{"id": 8135, "name": "Treasure Hunter"}]}]},
    {"id": 8000, "name": "Precision", "slots": [
        {"runes": [{"id": 8010, "name": "Conqueror"}]},
        {"runes": [{"id": 9111, "name": "Triumph"}]},
        {"runes": [{"id": 9104, "name": "Legend: Alacrity"}]},
        {"runes": [{"id": 8014, "name": "Coup de Grace"}]}]},
]


def perks(primary, sub):
    ids = {8100: [8112, 8143, 8138, 8135], 8000: [8010, 9111, 9104, 8014]}
    return {"styles": [
        {"description": "primaryStyle", "style": primary,
         "selections": [{"perk": r} for r in ids[primary]]},
        {"description": "subStyle", "style": sub,
         "selections": [{"perk": r} for r in ids[sub][1:3]]}]}


def make_match(n, champion, win, primary, duration=1800):
    sub = 8000 if primary == 8100 else 8100
    me = {"puuid": ME, "riotIdGameName": "Hyro4209", "riotIdTagline": "NA1",
          "championName": champion, "teamPosition": "MIDDLE", "teamId": 100, "win": win,
          "kills": 5, "deaths": 2, "assists": 7, "perks": perks(primary, sub)}
    others = [{"puuid": f"other-{n}-{i}", "riotIdGameName": f"P{i}", "riotIdTagline": "NA1",
               "championName": "Garen", "teamPosition": "TOP", "teamId": 100 if i < 4 else 200,
               "win": win if i < 4 else not win, "kills": 1, "deaths": 1, "assists": 1,
               "perks": perks(8000, 8100)} for i in range(9)]
    return {"metadata": {"matchId": f"NA1_{n}"},
            "info": {"gameCreation": 1_760_000_000_000 + n * 3_600_000,
                     "gameDuration": duration, "gameVersion": "16.22.555.1234",
                     "queueId": 420, "participants": [me] + others}}


MATCHES = {m["metadata"]["matchId"]: m for m in [
    make_match(1, "Ahri", True, 8100), make_match(2, "Ahri", True, 8100),
    make_match(3, "Ahri", False, 8100), make_match(4, "Yasuo", False, 8000),
    make_match(5, "Yasuo", True, 8000, duration=200),  # remake: must be excluded
]}


class FakeClient:
    def __init__(self):
        self.match_calls = 0

    def get_account(self, game_name, tag_line):
        return {"puuid": ME, "gameName": game_name, "tagLine": tag_line}

    def get_match_ids(self, puuid, start=0, count=100):
        return list(MATCHES)[start:start + count]

    def get_match(self, match_id):
        self.match_calls += 1
        return MATCHES[match_id]


def build():
    conn = db.connect(":memory:")
    client = FakeClient()
    extract.load_runes(conn, TREES)
    result = extract.sync_player(client, conn, "Hyro4209#NA1", count=50)
    transform.rebuild(conn)
    return conn, client, result


def test_extract_is_incremental():
    conn, client, result = build()
    assert result == {"player": "Hyro4209#NA1", "found": 5, "new": 5}
    again = extract.sync_player(client, conn, "Hyro4209#NA1", count=50)
    assert again["new"] == 0 and client.match_calls == 5


def test_transform_row_counts_and_patch():
    conn, _, _ = build()
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0] == 50
    assert conn.execute("SELECT COUNT(*) FROM participant_runes").fetchone()[0] == 300
    assert conn.execute("SELECT DISTINCT patch FROM matches").fetchall() == [("16.22",)]
    transform.rebuild(conn)  # rebuilding must not duplicate rows
    assert conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0] == 50


def test_winrates_exclude_remakes():
    conn, _, _ = build()
    champs = queries.winrate_by(conn, "champion", "Hyro4209#NA1").set_index("champion")
    assert champs.loc["Ahri", "games"] == 3 and champs.loc["Ahri", "win_rate"] == 66.7
    assert champs.loc["Yasuo", "games"] == 1 and champs.loc["Yasuo", "win_rate"] == 0.0
    keys = queries.winrate_by(conn, "keystone", "Hyro4209#NA1").set_index("keystone")
    assert keys.loc["Electrocute", "wins"] == 2 and keys.loc["Conqueror", "games"] == 1
    assert queries.winrate_by(conn, "champion", "Hyro4209#NA1", min_games=2).shape[0] == 1


def test_rune_pages_named_in_order():
    conn, _, _ = build()
    pages = queries.rune_pages(conn, "Hyro4209#NA1")
    ahri = pages[pages["champion"] == "Ahri"].iloc[0]
    assert ahri["rune_page"] == ("Electrocute / Sudden Impact / Eyeball Collection / "
                                 "Treasure Hunter / Triumph / Legend: Alacrity")
    assert ahri["games"] == 3
