"""Settings, read from a local .env file so the API key never lives in code."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "rift.db"


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into os.environ (real env vars win)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass
class Settings:
    api_key: str
    riot_ids: list[str]
    routing: str
    match_count: int


def get_settings() -> Settings:
    load_env()
    key = os.environ.get("RIOT_API_KEY", "")
    if not key or "paste-your-key" in key:
        raise SystemExit("RIOT_API_KEY is missing. Copy .env.example to .env and add your key.")
    ids = [x.strip() for x in os.environ.get("RIOT_IDS", "").split(",") if x.strip()]
    for riot_id in ids:
        if "#" not in riot_id:
            raise SystemExit(f"Riot ID '{riot_id}' needs its tagline, like Name#NA1.")
    if not ids:
        raise SystemExit("RIOT_IDS is empty. Add at least one Riot ID to .env.")
    return Settings(
        api_key=key,
        riot_ids=ids,
        routing=os.environ.get("RIOT_ROUTING", "americas"),
        match_count=int(os.environ.get("MATCH_COUNT", "50")),
    )
