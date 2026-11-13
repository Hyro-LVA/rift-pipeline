"""Thin wrapper around the Riot API: auth header, rate limiting and retries."""
import time
from urllib.parse import quote

import requests


class RiotAuthError(Exception):
    """The key was rejected. Development keys expire every 24 hours."""


class RiotNotFound(Exception):
    """The player or match does not exist."""


class RiotClient:
    # A development key allows 100 requests per 2 minutes, so one request
    # every 1.25 seconds stays under the limit without tracking a window.
    def __init__(self, api_key: str, routing: str = "americas",
                 min_interval: float = 1.25, session=None):
        self.base = f"https://{routing}.api.riotgames.com"
        self.min_interval = min_interval
        self.session = session or requests.Session()
        self.session.headers.update({"X-Riot-Token": api_key})
        self._last_call = 0.0

    def _get(self, path: str, params: dict | None = None):
        for attempt in range(5):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            resp = self.session.get(self.base + path, params=params, timeout=15)

            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:  # rate limited: Riot says how long to wait
                time.sleep(int(resp.headers.get("Retry-After", "10")) + 1)
                continue
            if resp.status_code in (401, 403):
                raise RiotAuthError("Riot rejected the API key. Regenerate it and update .env.")
            if resp.status_code == 404:
                raise RiotNotFound(path)
            if resp.status_code >= 500:  # Riot-side hiccup: back off and retry
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
        raise RuntimeError(f"Gave up on {path} after 5 attempts")

    def get_account(self, game_name: str, tag_line: str) -> dict:
        return self._get(
            f"/riot/account/v1/accounts/by-riot-id/{quote(game_name)}/{quote(tag_line)}")

    def get_match_ids(self, puuid: str, start: int = 0, count: int = 100) -> list[str]:
        return self._get(f"/lol/match/v5/matches/by-puuid/{puuid}/ids",
                         {"start": start, "count": count})

    def get_match(self, match_id: str) -> dict:
        return self._get(f"/lol/match/v5/matches/{match_id}")
