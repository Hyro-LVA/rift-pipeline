"""Dashboard:  streamlit run dashboard.py"""
import sqlite3

import streamlit as st

from pipeline import config, db, queries

st.set_page_config(page_title="Rift Pipeline", layout="wide")
st.title("Rift Pipeline: win rates and runes")

if not config.DB_PATH.exists():
    st.warning("No data yet. Run `python -m pipeline.run` first.")
    st.stop()

conn = db.connect(config.DB_PATH)
player_list = queries.players(conn)
if not player_list:
    st.warning("No players loaded yet. Run `python -m pipeline.run` first.")
    st.stop()

with st.sidebar:
    player = st.selectbox("Player", player_list)
    all_games = queries.games(conn, player)
    queue_ids = sorted(all_games["queue_id"].dropna().unique().tolist())
    queue = st.selectbox("Queue", [None] + queue_ids,
                         format_func=lambda q: "All queues" if q is None
                         else queries.QUEUES.get(int(q), f"Queue {int(q)}"))
    patches = sorted(all_games["patch"].unique().tolist(),
                     key=lambda p: [int(x) for x in p.split(".") if x.isdigit()], reverse=True)
    patch = st.selectbox("Patch", [None] + patches,
                         format_func=lambda p: "All patches" if p is None else p)
    min_games = st.slider("Minimum games", 1, 10, 2)

queue = int(queue) if queue is not None else None
games = queries.games(conn, player, queue, patch)
if games.empty:
    st.info("No games match these filters.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Games", len(games))
col2.metric("Win rate", f"{100 * games['win'].mean():.1f}%")
col3.metric("KDA", f"{(games['kills'].sum() + games['assists'].sum()) / max(games['deaths'].sum(), 1):.2f}")

args = dict(player=player, queue_id=queue, patch=patch, min_games=min_games)
tab_champ, tab_runes, tab_pages, tab_recent = st.tabs(
    ["Champions", "Keystones", "Rune pages", "Recent games"])

with tab_champ:
    by_champ = queries.winrate_by(conn, "champion", **args)
    st.dataframe(by_champ, use_container_width=True, hide_index=True)
    if not by_champ.empty:
        st.bar_chart(by_champ.set_index("champion")["win_rate"])

with tab_runes:
    st.subheader("By keystone")
    st.dataframe(queries.winrate_by(conn, "keystone", **args),
                 use_container_width=True, hide_index=True)
    st.subheader("By champion and keystone")
    st.dataframe(queries.winrate_by(conn, "champion, keystone", **args),
                 use_container_width=True, hide_index=True)

with tab_pages:
    st.dataframe(queries.rune_pages(conn, **args), use_container_width=True, hide_index=True)

with tab_recent:
    recent = games[["game_start_utc", "champion", "position", "win", "kills", "deaths",
                    "assists", "keystone", "secondary_tree", "patch"]].head(50)
    st.dataframe(recent, use_container_width=True, hide_index=True)
