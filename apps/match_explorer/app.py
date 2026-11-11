"""StatsBomb Match Explorer: load one match and interrogate it.

Run from the repo root:
    streamlit run apps/match_explorer/app.py
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import data
import metrics as m
import plots

st.set_page_config(page_title="StatsBomb Match Explorer", page_icon="⚽", layout="wide")

DEFAULT_COMP = "Women's Super League"


# --------------------------------------------------------------------------- #
# Cached loaders
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading competitions…")
def load_competitions():
    return data.open_competitions()


@st.cache_data(show_spinner="Loading fixtures…")
def load_matches(cid, sid):
    return data.open_matches(cid, sid)


@st.cache_data(show_spinner="Loading match events…")
def load_open_match(match_id):
    return data.open_events(match_id), data.open_lineups(match_id)


@st.cache_data(show_spinner="Reading your file…")
def load_uploaded(events_bytes, lineup_bytes):
    ev = data.events_from_json(events_bytes)
    lu = data.lineups_from_json(lineup_bytes) if lineup_bytes else {}
    return ev, lu


def show(fig):
    st.pyplot(fig, clear_figure=True, width="stretch")
    plt.close(fig)


def team_label(team, color):
    return f"<span style='color:{color};font-weight:700'>{team}</span>"


def display_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Make list/dict columns printable so the table widget can show them."""
    out = df.copy()
    for c in out.columns:
        if out[c].map(lambda v: isinstance(v, (list, dict))).any():
            out[c] = out[c].map(lambda v: str(v) if isinstance(v, (list, dict)) else v)
    return out


# --------------------------------------------------------------------------- #
# Sidebar: choose the match
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("⚽ Load a match")
    source = st.radio("Data source", ["StatsBomb open data", "My own JSON file"],
                      help="Open data is fetched from StatsBomb's public GitHub. "
                           "Or load an events file you've downloaded.")
    ev = lineups = info = None

    if source == "StatsBomb open data":
        try:
            comps = load_competitions()
        except Exception as exc:
            st.error(f"Couldn't reach StatsBomb open data: {exc}")
            st.stop()
        comps["label"] = comps["competition_name"] + " (" + comps["country_name"] + ")"
        labels = sorted(comps["label"].unique())
        default = next((i for i, l in enumerate(labels) if DEFAULT_COMP in l), 0)
        comp_label = st.selectbox("Competition", labels, index=default)
        seasons = comps[comps["label"] == comp_label]
        season = st.selectbox("Season", seasons["season_name"].tolist())
        row = seasons[seasons["season_name"] == season].iloc[0]
        matches = load_matches(int(row.competition_id), int(row.season_id))
        if matches.empty:
            st.warning("No matches in this season.")
            st.stop()

        teams = sorted(set(matches.home_team) | set(matches.away_team))
        team_filter = st.selectbox("Filter by team (optional)", ["All teams"] + teams)
        if team_filter != "All teams":
            matches = matches[(matches.home_team == team_filter) | (matches.away_team == team_filter)]
        matches = matches.assign(label=matches.match_date + "  " + matches.home_team + " "
                                 + matches.home_score.astype(str) + "–" + matches.away_score.astype(str)
                                 + " " + matches.away_team)
        match_label = st.selectbox(f"Match ({len(matches)})", matches["label"].tolist())
        mrow = matches[matches["label"] == match_label].iloc[0]
        ev, lineups = load_open_match(int(mrow.match_id))
        info = data.match_info_from_row(mrow)
    else:
        up = st.file_uploader("Events JSON (required)", type="json",
                              help="A StatsBomb events file, e.g. data/events/3913173.json")
        up_lu = st.file_uploader("Lineups JSON (optional)", type="json")
        if up is None:
            st.info("Upload a StatsBomb **events** JSON to begin.")
        else:
            try:
                ev, lineups = load_uploaded(up.getvalue(), up_lu.getvalue() if up_lu else None)
                info = data.match_info_from_events(ev)
            except Exception as exc:
                st.error(f"Couldn't read that file: {exc}")

    st.divider()
    st.caption("Data: Hudl StatsBomb open data. Credit StatsBomb if you publish "
               "anything made with it.")

if ev is None:
    st.title("StatsBomb Match Explorer")
    st.write("Choose a match in the sidebar to start.")
    st.stop()

HOME, AWAY = info.home, info.away
COL = {HOME: plots.HOME_COLOR, AWAY: plots.AWAY_COLOR}
CMAP = {HOME: "Blues", AWAY: "Oranges"}
summary = m.team_summary(ev, [HOME, AWAY])

# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(f"## {team_label(HOME, COL[HOME])} &nbsp;{info.home_score if info.home_score is not None else ''}"
            f"–{info.away_score if info.away_score is not None else ''}&nbsp; {team_label(AWAY, COL[AWAY])}",
            unsafe_allow_html=True)
meta = " · ".join(str(x) for x in [info.competition, info.season, info.date, info.stadium] if x)
if meta:
    st.caption(meta)

c = st.columns(4)
for col, metric, fmt in zip(c, ["xG", "Shots", "Possession %", "Pass completion %"],
                            ["{:.2f}", "{:.0f}", "{:.0f}%", "{:.0f}%"]):
    col.metric(metric.replace(" %", ""),
               f"{fmt.format(summary.loc[metric, HOME])}  –  {fmt.format(summary.loc[metric, AWAY])}")

tab_over, tab_shots, tab_pass, tab_players, tab_events = st.tabs(
    ["📊 Overview", "🎯 Shots", "➡️ Passes", "👤 Players", "🔎 Event explorer"])

# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
with tab_over:
    left, right = st.columns([1, 1.6])
    with left:
        st.subheader("Team stats")
        tbl = summary.copy()
        tbl.columns = [HOME, AWAY]
        st.dataframe(tbl.map(lambda v: f"{v:g}"), width="stretch", height=810)
        with st.expander("How these are defined"):
            st.markdown(
                "- **Possession %**: share of in-play time on the ball (time between events, credited to the team in possession; stoppages over 20 s capped).\n"
                "- **Progressive pass**: completed open-play pass, starting outside the team's own 40%, "
                "that moves the ball at least 25% closer to the centre of the goal.\n"
                "- **Final-third entries**: completed passes into the final third.\n"
                "- **Box entries**: completed passes from outside the box ending inside it.\n"
                "- **Shots / xG** exclude any penalty shoot-out. Goals include own goals.")
    with right:
        st.subheader("xG race")
        show(plots.xg_race(ev, HOME, AWAY))
        st.caption("Running total of shot xG. Dots are goals, diamonds are own goals.")

        st.subheader("Key moments")
        km = ev[(ev.type == "Shot") & (ev.shot_outcome == "Goal") | (ev.type == "Own Goal For")
                | ev.foul_committed_card.notna() | ev.bad_behaviour_card.notna()
                | (ev.type == "Substitution")].copy()
        km = km[km.period <= 4]

        def describe(r):
            if r.type == "Shot":
                return f"⚽ Goal: {r.player} ({r.shot_statsbomb_xg:.2f} xG, {r.shot_body_part}, {r.shot_type})"
            if r.type == "Own Goal For":
                og = ev[(ev.type == "Own Goal Against") & (ev["index"] < r["index"] + 3)
                        & (ev["index"] > r["index"] - 3)]
                who = og.player.iloc[0] if len(og) else "opponent"
                return f"⚽ Own goal by {who}"
            if r.type == "Substitution":
                return f"🔁 {r.substitution_replacement} on for {r.player}"
            card = r.foul_committed_card if isinstance(r.foul_committed_card, str) else r.bad_behaviour_card
            return f"{'🟥' if card in m.RED_CARDS else '🟨'} {card}: {r.player}"

        km["Moment"] = km.apply(describe, axis=1)
        km["Min"] = km.minute.astype(str) + "'"
        st.dataframe(km[["Min", "team", "Moment"]].rename(columns={"team": "Team"}),
                     hide_index=True, width="stretch")

    if info.extra:
        with st.expander("Match details"):
            st.json({k: v for k, v in info.extra.items() if v not in ("", None)} |
                    ({"Referee": info.referee} if info.referee else {}))

# --------------------------------------------------------------------------- #
# Shots
# --------------------------------------------------------------------------- #
with tab_shots:
    s_all = m.shots(ev)
    f1, f2, f3, f4 = st.columns([1, 2, 2, 1])
    team_sel = f1.radio("Team", ["Both", HOME, AWAY], key="shot_team")
    s = s_all if team_sel == "Both" else s_all[s_all.team == team_sel]
    players_sel = f2.multiselect("Players", sorted(s.player.dropna().unique()), key="shot_players")
    outcomes_sel = f3.multiselect("Outcome", sorted(s.shot_outcome.dropna().unique()), key="shot_out")
    no_pens = f4.checkbox("Exclude penalties", key="shot_pens")
    if players_sel:
        s = s[s.player.isin(players_sel)]
    if outcomes_sel:
        s = s[s.shot_outcome.isin(outcomes_sel)]
    if no_pens:
        s = s[s.shot_type != "Penalty"]

    show(plots.shot_map(s, HOME, AWAY))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Shots", len(s))
    k2.metric("Goals", int((s.shot_outcome == "Goal").sum()))
    k3.metric("xG", f"{s.shot_statsbomb_xg.sum():.2f}")
    k4.metric("xG per shot", f"{s.shot_statsbomb_xg.mean():.3f}" if len(s) else "–")

    if team_sel != "Both":
        st.markdown("**Where the shots ended up** (view from behind the goal; shots well wide or high are left off)")
        show(plots.shot_end_map(s, COL[team_sel]))

    shot_cols = {"minute": "Min", "team": "Team", "player": "Player",
                 "shot_statsbomb_xg": "xG", "shot_outcome": "Outcome",
                 "shot_body_part": "Body part", "shot_type": "Type",
                 "shot_technique": "Technique", "play_pattern": "Play pattern",
                 "under_pressure": "Under pressure"}
    tbl = s[[c for c in shot_cols if c in s]].rename(columns=shot_cols)
    tbl["Under pressure"] = tbl.get("Under pressure", pd.Series(dtype=object)).fillna(False)
    st.dataframe(tbl, hide_index=True, width="stretch",
                 column_config={"xG": st.column_config.ProgressColumn(
                     "xG", min_value=0, max_value=1, format="%.2f")})
    st.download_button("Download shots as CSV", tbl.to_csv(index=False), "shots.csv", "text/csv")

# --------------------------------------------------------------------------- #
# Passes
# --------------------------------------------------------------------------- #
with tab_pass:
    p_all = m.passes(ev)
    a, b = st.columns([1, 3])
    team_p = a.radio("Team", [HOME, AWAY], key="pass_team")
    view = a.radio("View", ["Pass map", "Pass network"], key="pass_view")
    color = COL[team_p]

    if view == "Pass map":
        p = p_all[p_all.team == team_p]
        player_p = a.selectbox("Player", ["Whole team"] + sorted(p.player.dropna().unique()))
        kind = a.selectbox("Pass type", ["All passes", "Progressive", "Into final third",
                                         "Into the box", "Key passes (led to a shot)",
                                         "Crosses", "Set pieces only", "Open play only"])
        outcome = a.radio("Outcome", ["Both", "Complete", "Incomplete"], horizontal=True)
        under_p = a.checkbox("Only under pressure")
        tmax = int(m.match_end_time(ev)) + 1
        mins = a.slider("Minutes", 0, tmax, (0, tmax))

        if player_p != "Whole team":
            p = p[p.player == player_p]
        p = {"All passes": p, "Progressive": p[p.progressive],
             "Into final third": p[p.final_third_entry], "Into the box": p[p.box_entry],
             "Key passes (led to a shot)": p[p.key_pass],
             "Crosses": p[p.pass_cross.fillna(False).astype(bool)],
             "Set pieces only": p[p.set_piece], "Open play only": p[~p.set_piece]}[kind]
        if outcome != "Both":
            p = p[p.complete == (outcome == "Complete")]
        if under_p:
            p = p[p.under_pressure.fillna(False).astype(bool)]
        p = p[(p.time >= mins[0]) & (p.time <= mins[1])]

        with b:
            ttl = f"{player_p if player_p != 'Whole team' else team_p}: {kind.lower()}"
            show(plots.pass_map(p, color, ttl))
            if len(p):
                st.caption(f"{len(p)} passes · {100 * p.complete.mean():.0f}% complete · "
                           f"average length {p.pass_length.mean():.1f} m")
            top = (p[p.complete].groupby(["player", "pass_recipient"]).size()
                   .sort_values(ascending=False).head(10).rename("Passes").reset_index()
                   .rename(columns={"player": "From", "pass_recipient": "To"}))
            if len(top):
                st.markdown("**Most common completed combinations**")
                st.dataframe(top, hide_index=True, width="stretch")
    else:
        min_p = a.slider("Minimum passes to draw a link", 1, 15, 4)
        nodes, edges, cutoff = m.pass_network(ev, team_p, min_p)
        with b:
            show(plots.pass_network_plot(nodes, edges, color))
            until = "full match" if cutoff == float("inf") else f"up to the first change ({cutoff:.0f}')"
            st.caption(f"Completed passes between players, {until}, so one XI is shown. "
                       "Positions are each player's average pass and receive location.")
            if len(edges):
                st.dataframe(edges.rename(columns={"a": "Player", "b": "Player ", "count": "Passes"}),
                             hide_index=True, width="stretch")

# --------------------------------------------------------------------------- #
# Players
# --------------------------------------------------------------------------- #
with tab_players:
    pt = m.player_table(ev)
    if lineups:  # fill shirt numbers for substitutes from the lineups file
        shirts = {r.player_name: r.jersey_number for lu in lineups.values()
                  for r in lu.itertuples() if pd.notna(r.jersey_number)}
        pt["shirt"] = pt["shirt"].fillna(pt["player"].map(shirts))
    tf = st.radio("Team", ["Both", HOME, AWAY], horizontal=True, key="pl_team")
    view_pt = pt if tf == "Both" else pt[pt.team == tf]
    per90 = st.toggle("Show per 90 minutes", help="Players with under 20 minutes are hidden in per-90 view.")
    shown = view_pt.copy()
    count_cols = ["Touches", "Passes", "Prog. passes", "Key passes", "Assists", "Shots",
                  "Goals", "xG", "xA", "Dribbles", "Pressures", "Tackles",
                  "Interceptions", "Recoveries"]
    if per90:
        shown = shown[shown.minutes >= 20]
        shown[count_cols] = shown[count_cols].div(shown.minutes, axis=0).mul(90).round(2)
    st.dataframe(shown, hide_index=True, width="stretch", height=420,
                 column_config={"shirt": st.column_config.NumberColumn("No.", format="%d"),
                                "start_position": "Started as", "minutes": "Mins",
                                "player": "Player", "team": "Team"})
    st.download_button("Download player table as CSV", shown.to_csv(index=False),
                       "players.csv", "text/csv")

    st.divider()
    names = view_pt.player.tolist()
    if names:
        who = st.selectbox("Look at one player", names)
        prow = pt[pt.player == who].iloc[0]
        pcolor, pcmap = COL.get(prow.team, plots.HOME_COLOR), CMAP.get(prow.team, "Blues")
        st.markdown(f"### {who} &nbsp;<span style='color:{pcolor}'>{prow.team}</span>",
                    unsafe_allow_html=True)
        st.caption(f"{prow.start_position} · {int(prow.minutes)} minutes")
        q = st.columns(6)
        for col, k in zip(q, ["Touches", "Passes", "Pass %", "Shots", "xG", "Pressures"]):
            col.metric(k, f"{prow[k]:g}")
        pe = ev[ev.player == who]
        v1, v2 = st.columns(2)
        with v1:
            st.markdown("**Touch heatmap**")
            show(plots.touch_heatmap(pe[pe.type.isin(
                ["Pass", "Carry", "Shot", "Dribble", "Ball Receipt*", "Clearance",
                 "Interception", "Ball Recovery", "Miscontrol", "Duel", "Block",
                 "Foul Won", "Dispossessed", "Goal Keeper"])], pcmap))
        with v2:
            st.markdown("**Action map**")
            show(plots.action_map(pe, pcolor))
        st.markdown("**Passes**")
        show(plots.pass_map(m.passes(ev)[lambda d: d.player == who], pcolor))

        if lineups and prow.team in lineups:
            lu = lineups[prow.team]
            r = lu[lu.player_name == who]
            if len(r):
                with st.expander("Lineup record"):
                    st.json({"Shirt": r.iloc[0].get("jersey_number"),
                             "Country": r.iloc[0].get("country"),
                             "Positions": r.iloc[0].get("positions")}, expanded=False)

# --------------------------------------------------------------------------- #
# Event explorer
# --------------------------------------------------------------------------- #
with tab_events:
    st.caption("Every event in the match. Filter, pick columns, and download.")
    e1, e2, e3 = st.columns(3)
    types = e1.multiselect("Event types", sorted(ev.type.dropna().unique()),
                           default=["Shot"] if "Shot" in set(ev.type) else None)
    teams_f = e2.multiselect("Teams", [HOME, AWAY])
    pool = ev if not teams_f else ev[ev.team.isin(teams_f)]
    players_f = e3.multiselect("Players", sorted(pool.player.dropna().unique()))
    e4, e5, e6 = st.columns(3)
    periods = e4.multiselect("Periods", sorted(ev.period.unique()))
    tmax = int(m.match_end_time(ev)) + 1
    trange = e5.slider("Minutes", 0, max(tmax, 1), (0, max(tmax, 1)), key="ev_mins")
    pressure = e6.selectbox("Under pressure", ["Any", "Yes", "No"])

    f = ev
    if types:
        f = f[f.type.isin(types)]
    if teams_f:
        f = f[f.team.isin(teams_f)]
    if players_f:
        f = f[f.player.isin(players_f)]
    if periods:
        f = f[f.period.isin(periods)]
    f = f[(f.time >= trange[0]) & (f.time <= trange[1])]
    if pressure != "Any":
        f = f[f.under_pressure.fillna(False).astype(bool) == (pressure == "Yes")]

    # Default columns: core ones plus any column with data for the chosen types.
    core = ["index", "period", "minute", "second", "team", "player", "type",
            "position", "play_pattern", "x", "y", "under_pressure"]
    prefixes = tuple(t.lower().replace(" ", "_").replace("*", "") for t in (types or []))
    extra = [c for c in f.columns if prefixes and c.startswith(prefixes)
             and f[c].notna().any() and not c.endswith("_id")
             and c not in ("shot_freeze_frame",)]
    all_cols = [c for c in ev.columns if c not in ("tactics",)]
    cols = st.multiselect("Columns", all_cols, default=[c for c in core + extra if c in all_cols])
    st.write(f"**{len(f):,}** events")
    out = display_frame(f[cols]) if cols else display_frame(f)
    st.dataframe(out, hide_index=True, width="stretch", height=480)
    st.download_button("Download these events as CSV", out.to_csv(index=False),
                       "events.csv", "text/csv")
