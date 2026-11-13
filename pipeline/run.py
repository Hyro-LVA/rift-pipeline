"""Run the whole pipeline:  python -m pipeline.run"""
import argparse

from . import config, db, extract, transform
from .riot_client import RiotAuthError, RiotClient, RiotNotFound


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull League matches and rebuild the tables.")
    parser.add_argument("--count", type=int, help="matches per player (overrides .env)")
    parser.add_argument("--skip-extract", action="store_true",
                        help="rebuild tables from stored raw data without calling Riot")
    args = parser.parse_args()

    conn = db.connect(config.DB_PATH)
    if not args.skip_extract:
        settings = config.get_settings()
        client = RiotClient(settings.api_key, settings.routing)
        print(f"Loaded {extract.sync_runes(conn)} runes from Data Dragon")
        for riot_id in settings.riot_ids:
            try:
                result = extract.sync_player(client, conn, riot_id, args.count or settings.match_count)
                print(f"{riot_id}: {result['found']} recent matches, {result['new']} new      ")
            except RiotNotFound:
                print(f"{riot_id}: not found. Check the spelling and tagline.")
            except RiotAuthError as err:
                raise SystemExit(str(err))

    print(f"Transformed {transform.rebuild(conn)} matches into {config.DB_PATH}")
    print("Next: streamlit run dashboard.py")


if __name__ == "__main__":
    main()
