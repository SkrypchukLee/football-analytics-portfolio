"""Match-level metrics computed from a tidy StatsBomb events DataFrame.

All coordinates are StatsBomb's 120 x 80 pitch, with every team's events
already oriented so they attack left to right.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GOAL = np.array([120.0, 40.0])
ON_TARGET = {"Goal", "Saved", "Saved To Post"}
RED_CARDS = {"Red Card", "Second Yellow"}
# Events that aren't play and would stretch a possession across a stoppage.
ADMIN_EVENTS = {"Starting XI", "Half Start", "Half End", "Substitution",
                "Tactical Shift", "Injury Stoppage", "Player Off", "Player On",
                "Referee Ball-Drop", "Bad Behaviour", "Own Goal For",
                "Own Goal Against"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def shots(ev: pd.DataFrame) -> pd.DataFrame:
    """Shots in normal and extra time (no penalty shoot-out)."""
    return ev[(ev["type"] == "Shot") & (ev["period"] <= 4)].copy()


def passes(ev: pd.DataFrame) -> pd.DataFrame:
    p = ev[ev["type"] == "Pass"].copy()
    p["complete"] = p["pass_outcome"].isna()
    p["set_piece"] = p["pass_type"].isin(
        ["Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"])
    start = np.c_[p["x"], p["y"]].astype(float)
    end = np.c_[p["pass_end_x"], p["pass_end_y"]].astype(float)
    d0 = np.linalg.norm(GOAL - start, axis=1)
    d1 = np.linalg.norm(GOAL - end, axis=1)
    # Progressive: completed open-play pass that moves the ball at least 25%
    # closer to the centre of the goal, starting outside the team's own 40%.
    p["progressive"] = p["complete"] & ~p["set_piece"] & (p["x"] >= 48) & (d1 <= 0.75 * d0)
    p["final_third_entry"] = p["complete"] & (p["x"] < 80) & (p["pass_end_x"] >= 80)
    p["box_entry"] = p["complete"] & (p["pass_end_x"] >= 102) & p["pass_end_y"].between(18, 62) \
        & ~((p["x"] >= 102) & p["y"].between(18, 62))
    p["key_pass"] = p["pass_shot_assist"].fillna(False).astype(bool) \
        | p["pass_goal_assist"].fillna(False).astype(bool)
    return p


def _seconds(ts: pd.Series) -> pd.Series:
    t = pd.to_timedelta(ts)
    return t.dt.total_seconds()


def possession_share(ev: pd.DataFrame, max_gap: float = 20.0) -> dict[str, float]:
    """Share of in-play time each team had the ball.

    Each event's time runs until the next event in the same period and is
    credited to the team in possession. Gaps longer than ``max_gap`` seconds
    (stoppages) are capped so dead time doesn't dominate.
    """
    e = ev[(ev["period"] <= 4) & ~ev["type"].isin(ADMIN_EVENTS)].copy()
    e["t"] = _seconds(e["timestamp"])
    e = e.sort_values(["period", "t", "index"])
    gap = e.groupby("period")["t"].shift(-1) - e["t"]
    e["gap"] = gap.fillna(0).clip(lower=0, upper=max_gap)
    by_team = e.groupby("possession_team")["gap"].sum()
    return (by_team / by_team.sum()).to_dict()


# --------------------------------------------------------------------------- #
# Team level
# --------------------------------------------------------------------------- #
def team_summary(ev: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    """One column per team, one row per metric."""
    s, p = shots(ev), passes(ev)
    poss = possession_share(ev)
    own_goals_for = ev[ev["type"] == "Own Goal For"].groupby("team").size()
    rows = {}
    for t in teams:
        ts, tp, te = s[s.team == t], p[p.team == t], ev[ev.team == t]
        goals = int((ts.shot_outcome == "Goal").sum() + own_goals_for.get(t, 0))
        np_ts = ts[ts.shot_type != "Penalty"]
        rows[t] = {
            "Goals": goals,
            "xG": round(ts.shot_statsbomb_xg.sum(), 2),
            "Non-penalty xG": round(np_ts.shot_statsbomb_xg.sum(), 2),
            "Shots": len(ts),
            "Shots on target": int(ts.shot_outcome.isin(ON_TARGET).sum()),
            "xG per shot": round(ts.shot_statsbomb_xg.mean(), 3) if len(ts) else 0,
            "Possession %": round(100 * poss.get(t, 0), 1),
            "Passes": len(tp),
            "Pass completion %": round(100 * tp.complete.mean(), 1) if len(tp) else 0,
            "Progressive passes": int(tp.progressive.sum()),
            "Final-third entries": int(tp.final_third_entry.sum()),
            "Box entries": int(tp.box_entry.sum()),
            "Crosses": int(tp.pass_cross.fillna(False).astype(bool).sum()),
            "Corners": int((tp.pass_type == "Corner").sum()),
            "Dribbles completed": int(((te.type == "Dribble") & (te.dribble_outcome == "Complete")).sum()),
            "Pressures": int((te.type == "Pressure").sum()),
            "Tackles": int(((te.type == "Duel") & (te.duel_type == "Tackle")).sum()),
            "Interceptions": int((te.type == "Interception").sum()),
            "Ball recoveries": int((te.type == "Ball Recovery").sum()),
            "Fouls committed": int((te.type == "Foul Committed").sum()),
            "Yellow cards": int(te.foul_committed_card.eq("Yellow Card").sum()
                                + te.bad_behaviour_card.eq("Yellow Card").sum()),
            "Red cards": int(te.foul_committed_card.isin(RED_CARDS).sum()
                             + te.bad_behaviour_card.isin(RED_CARDS).sum()),
        }
    return pd.DataFrame(rows)


def xg_timeline(ev: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    """Shots with running xG per team, in match order."""
    s = shots(ev).sort_values("index")
    s["cum_xg"] = s.groupby("team")["shot_statsbomb_xg"].cumsum()
    og = ev[ev["type"] == "Own Goal For"][["team", "minute", "second", "time", "period"]]
    s = s[s.team.isin(teams)]
    return s, og


def match_end_time(ev: pd.DataFrame) -> float:
    e = ev[ev["period"] <= 4]
    return float(e["time"].max()) if len(e) else 90.0


# --------------------------------------------------------------------------- #
# Player level
# --------------------------------------------------------------------------- #
def player_minutes(ev: pd.DataFrame) -> pd.DataFrame:
    """Minutes on the pitch from Starting XI, substitutions and red cards."""
    end = match_end_time(ev)
    on, off, team_of, pos_of, shirt = {}, {}, {}, {}, {}
    for _, r in ev[ev["type"] == "Starting XI"].iterrows():
        tac = r["tactics"] if isinstance(r["tactics"], dict) else {}
        for p in tac.get("lineup", []):
            name = p["player"]["name"]
            on[name], team_of[name] = 0.0, r["team"]
            pos_of[name], shirt[name] = p["position"]["name"], p.get("jersey_number")
    for _, r in ev[ev["type"] == "Substitution"].iterrows():
        off[r["player"]] = r["time"]
        rep = r["substitution_replacement"]
        if isinstance(rep, str):
            on[rep], team_of[rep] = r["time"], r["team"]
    cards = ev[ev["foul_committed_card"].isin(RED_CARDS) | ev["bad_behaviour_card"].isin(RED_CARDS)]
    for _, r in cards.iterrows():
        off[r["player"]] = min(off.get(r["player"], end), r["time"])
    rows = [{"player": n, "team": team_of[n], "shirt": shirt.get(n),
             "start_position": pos_of.get(n, "Sub"), "on": on[n],
             "minutes": round(off.get(n, end) - on[n])} for n in on]
    return pd.DataFrame(rows)


def player_table(ev: pd.DataFrame) -> pd.DataFrame:
    s, p = shots(ev), passes(ev)
    mins = player_minutes(ev)
    players = ev.dropna(subset=["player"]).groupby("player")["team"].first()
    df = pd.DataFrame({"team": players})
    df.index.name = "player"

    def count(mask, frame=ev):
        return frame[mask].groupby("player").size()

    df["Touches"] = ev[ev["x"].notna() & ev["type"].isin(
        ["Pass", "Carry", "Shot", "Dribble", "Ball Receipt*", "Clearance",
         "Interception", "Ball Recovery", "Miscontrol", "Duel", "Block",
         "Goal Keeper", "Foul Won", "Dispossessed"])].groupby("player").size()
    df["Passes"] = p.groupby("player").size()
    df["Pass %"] = (100 * p.groupby("player")["complete"].mean()).round(0)
    df["Prog. passes"] = p[p.progressive].groupby("player").size()
    df["Key passes"] = p[p.key_pass].groupby("player").size()
    df["Assists"] = p[p.pass_goal_assist.fillna(False).astype(bool)].groupby("player").size()
    df["Shots"] = s.groupby("player").size()
    df["Goals"] = s[s.shot_outcome == "Goal"].groupby("player").size()
    df["xG"] = s.groupby("player")["shot_statsbomb_xg"].sum().round(2)
    df["xA"] = _xa(ev, p).round(2)
    df["Dribbles"] = count((ev.type == "Dribble") & (ev.dribble_outcome == "Complete"))
    df["Pressures"] = count(ev.type == "Pressure")
    df["Tackles"] = count((ev.type == "Duel") & (ev.duel_type == "Tackle"))
    df["Interceptions"] = count(ev.type == "Interception")
    df["Recoveries"] = count(ev.type == "Ball Recovery")
    df = df.reset_index().merge(mins.drop(columns="team"), on="player", how="left")
    num = df.columns.difference(["player", "team", "start_position", "shirt", "on"])
    df[num] = df[num].fillna(0)
    df["start_position"] = df["start_position"].fillna("Sub")
    lead = ["player", "team", "shirt", "start_position", "minutes"]
    df = df[lead + [c for c in df.columns if c not in lead + ["on"]]]
    return df.sort_values(["team", "minutes"], ascending=[True, False]).reset_index(drop=True)


def _xa(ev: pd.DataFrame, p: pd.DataFrame) -> pd.Series:
    """Expected assists: xG of the shot each key pass set up, credited to the passer."""
    s = shots(ev)
    if "shot_key_pass_id" not in s:
        return pd.Series(dtype=float)
    kp = s.dropna(subset=["shot_key_pass_id"])[["shot_key_pass_id", "shot_statsbomb_xg"]]
    m = kp.merge(p[["id", "player"]], left_on="shot_key_pass_id", right_on="id")
    return m.groupby("player")["shot_statsbomb_xg"].sum()


# --------------------------------------------------------------------------- #
# Pass network
# --------------------------------------------------------------------------- #
def pass_network(ev: pd.DataFrame, team: str, min_passes: int = 3):
    """Average positions and pass links up to the team's first substitution
    (or red card), so the shape reflects one consistent XI."""
    te = ev[ev.team == team]
    breaks = te[(te.type == "Substitution") | te.foul_committed_card.isin(RED_CARDS)
                | te.bad_behaviour_card.isin(RED_CARDS)]
    cutoff = breaks["time"].min() if len(breaks) else np.inf
    p = passes(ev)
    p = p[(p.team == team) & p.complete & p.pass_recipient.notna() & (p.time < cutoff)]
    rec = p[["pass_recipient", "pass_end_x", "pass_end_y"]].rename(
        columns={"pass_recipient": "player", "pass_end_x": "x", "pass_end_y": "y"})
    pos = pd.concat([p[["player", "x", "y"]], rec])
    nodes = pos.groupby("player").agg(x=("x", "mean"), y=("y", "mean"))
    nodes["passes"] = p.groupby("player").size().reindex(nodes.index).fillna(0)
    pair = p.apply(lambda r: tuple(sorted((r["player"], r["pass_recipient"]))), axis=1)
    edges = pair.value_counts().rename("count").reset_index()
    edges[["a", "b"]] = pd.DataFrame(edges["index"].tolist() if "index" in edges
                                     else edges.iloc[:, 0].tolist(), index=edges.index)
    edges = edges[edges["count"] >= min_passes][["a", "b", "count"]]
    edges = edges[edges.a.isin(nodes.index) & edges.b.isin(nodes.index)]
    return nodes.reset_index(), edges.reset_index(drop=True), cutoff
