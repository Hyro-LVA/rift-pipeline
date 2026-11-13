# Rift Pipeline

A small data pipeline for League of Legends match history. It pulls matches from
the Riot Games API, stores the raw responses in SQLite, transforms them into clean
tables, and shows win rates by champion, keystone and rune page in a dashboard.

```
Riot API ──extract──> raw_matches (JSON) ──transform──> matches / participants /
Data Dragon ────────> runes, rune_trees                  participant_runes
                                                              │
                                             v_player_games (view) ──> dashboard
```

## Setup (GitHub Codespaces)

Everything runs in the browser, with nothing to install.

1. On the repository page, click **Code**, open the **Codespaces** tab, and click
   **Create codespace on main**. Packages install and a `.env` file is created
   automatically while it loads.
2. Open `.env` from the file list and paste your key from
   https://developer.riotgames.com, then set your Riot ID with its tagline (the part
   after the `#` in your client, for example `Hyro4209#NA1`).

`.env` is ignored by Git, so the key is never published. Development keys expire
every 24 hours, so regenerate and re-paste when a run says the key was rejected.

## Run

In the codespace terminal:

```bash
python -m pipeline.run          # pull new matches and rebuild the tables
streamlit run dashboard.py      # start the dashboard; it opens in a new tab
python -m pytest                # run the tests (no key or internet needed)
```

Useful options: `python -m pipeline.run --count 100` pulls more history, and
`--skip-extract` rebuilds the tables from stored raw data without calling Riot.
The first run of 50 matches takes about a minute because of the rate limit.

To run locally instead, install Python 3.10+, run `pip install -r requirements.txt`,
copy `.env.example` to `.env`, and use the same commands.

## How it works

| File | Job |
| --- | --- |
| `pipeline/config.py` | Reads settings and the API key from `.env` |
| `pipeline/riot_client.py` | Calls the Riot API with throttling and retries on 429 and 5xx |
| `pipeline/extract.py` | Fetches only matches not already stored and saves raw JSON |
| `pipeline/transform.py` | Parses raw JSON into `matches`, `participants`, `participant_runes` |
| `pipeline/db.py` | SQLite schema and the `v_player_games` analysis view |
| `pipeline/queries.py` | SQL for win rates by champion, keystone and rune page |
| `dashboard.py` | Streamlit dashboard |
| `tests/test_pipeline.py` | End-to-end test with a fake API client |

Design choices:

- **Raw layer kept separate.** API responses are stored unmodified, so the cleaned
  tables can be rebuilt after a schema change without spending rate limit.
- **Incremental and idempotent.** Each run fetches only new match IDs, and running
  it twice never duplicates rows.
- **Rate-limit aware.** One request every 1.25 seconds stays inside the development
  key's 100 requests per 2 minutes, and 429 responses honor `Retry-After`.
- **Remakes excluded.** Games shorter than 5 minutes are left out of win rates.

## Limits

This tracks the players listed in `.env`, not the whole ladder. Site-wide champion
win rates need millions of matches and a production API key.

Rift Pipeline isn't endorsed by Riot Games and doesn't reflect the views or opinions
of Riot Games or anyone officially involved in producing or managing Riot Games
properties.
