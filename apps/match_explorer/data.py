"""Data loading for the Match Explorer.

Two sources, one output shape:
  * StatsBomb open data, fetched with statsbombpy
  * a StatsBomb events JSON file you already have (e.g. from data/raw/)

Both are returned as a flat pandas DataFrame with statsbombpy's column names
(``type``, ``team``, ``player``, ``location``, ``shot_statsbomb_xg``,
``pass_end_location``, ...), so the rest of the app never needs to know where
the data came from.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field

import pandas as pd

warnings.filterwarnings("ignore", module="statsbombpy")

# Columns whose nested structure is worth keeping as-is rather than flattening.
_KEEP_RAW = {"tactics", "freeze_frame", "related_events", "location",
             "end_location"}


@dataclass
class MatchInfo:
    home: str
    away: str
    home_score: int | None = None
    away_score: int | None = None
    date: str = ""
    competition: str = ""
    season: str = ""
    stadium: str = ""
    referee: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        if self.home_score is None:
            return f"{self.home} v {self.away}"
        return f"{self.home} {self.home_score}–{self.away_score} {self.away}"


# --------------------------------------------------------------------------- #
# StatsBomb open data (statsbombpy)
# --------------------------------------------------------------------------- #
def open_competitions() -> pd.DataFrame:
    from statsbombpy import sb
    comps = sb.competitions()
    return comps.sort_values(["competition_name", "season_name"],
                             ascending=[True, False]).reset_index(drop=True)


def open_matches(competition_id: int, season_id: int) -> pd.DataFrame:
    from statsbombpy import sb
    m = sb.matches(competition_id=competition_id, season_id=season_id)
    return m.sort_values(["match_date", "kick_off"]).reset_index(drop=True)


def open_events(match_id: int) -> pd.DataFrame:
    from statsbombpy import sb
    ev = sb.events(match_id=match_id)
    return tidy_events(ev)


def open_lineups(match_id: int) -> dict[str, pd.DataFrame]:
    from statsbombpy import sb
    try:
        return sb.lineups(match_id=match_id)
    except Exception:  # lineups are optional
        return {}


def match_info_from_row(row: pd.Series) -> MatchInfo:
    def g(key, default=""):
        val = row.get(key, default)
        return default if pd.isna(val) else val

    return MatchInfo(
        home=g("home_team"), away=g("away_team"),
        home_score=int(row["home_score"]) if pd.notna(row.get("home_score")) else None,
        away_score=int(row["away_score"]) if pd.notna(row.get("away_score")) else None,
        date=str(g("match_date")), competition=g("competition"),
        season=g("season"), stadium=g("stadium"), referee=g("referee"),
        extra={"Kick-off": g("kick_off"), "Week": g("match_week"),
               "Stage": g("competition_stage"),
               "Home manager": g("home_managers"),
               "Away manager": g("away_managers")},
    )


# --------------------------------------------------------------------------- #
# Local StatsBomb JSON
# --------------------------------------------------------------------------- #
def _flatten_event(ev: dict) -> dict:
    """Flatten one raw StatsBomb event the way statsbombpy does.

    ``{"type": {"id": 16, "name": "Shot"}}``      -> ``type="Shot"``
    ``{"shot": {"outcome": {"name": "Goal"}}}``   -> ``shot_outcome="Goal"``
    ``{"pass": {"recipient": {"id": 1, ...}}}``   -> ``pass_recipient``, ``pass_recipient_id``
    """
    out: dict = {}

    def put(key: str, val):
        if isinstance(val, dict) and "name" in val and "id" in val:
            out[key] = val["name"]
            out[f"{key}_id"] = val["id"]
        elif isinstance(val, dict) and key.split("_")[-1] not in _KEEP_RAW \
                and key not in _KEEP_RAW:
            for k, v in val.items():
                put(f"{key}_{k}", v)
        else:
            out[key] = val

    for k, v in ev.items():
        if k in _KEEP_RAW:
            out[k] = v
        else:
            put(k, v)
    return out


def events_from_json(raw: bytes | str | list) -> pd.DataFrame:
    """Build an events DataFrame from a StatsBomb events JSON file."""
    if isinstance(raw, (bytes, str)):
        raw = json.loads(raw)
    if not isinstance(raw, list) or not raw or "type" not in raw[0]:
        raise ValueError("This doesn't look like a StatsBomb events file "
                         "(expected a list of events with a 'type' field).")
    return tidy_events(pd.DataFrame([_flatten_event(e) for e in raw]))


def lineups_from_json(raw: bytes | str | list) -> dict[str, pd.DataFrame]:
    if isinstance(raw, (bytes, str)):
        raw = json.loads(raw)
    out = {}
    for team in raw:
        rows = [{"player_id": p["player_id"], "player_name": p["player_name"],
                 "player_nickname": p.get("player_nickname"),
                 "jersey_number": p.get("jersey_number"),
                 "country": (p.get("country") or {}).get("name"),
                 "positions": p.get("positions", [])}
                for p in team.get("lineup", [])]
        out[team["team_name"]] = pd.DataFrame(rows)
    return out


def match_info_from_events(ev: pd.DataFrame) -> MatchInfo:
    """Best guess at teams and score when we only have the events file."""
    xi = ev[ev["type"] == "Starting XI"]
    teams = xi["team"].tolist() if len(xi) >= 2 else ev["team"].dropna().unique().tolist()
    home, away = (teams + ["Team 1", "Team 2"])[:2]
    goals = goals_by_team(ev)
    return MatchInfo(home=home, away=away,
                     home_score=goals.get(home, 0), away_score=goals.get(away, 0))


# --------------------------------------------------------------------------- #
# Shared tidy-up
# --------------------------------------------------------------------------- #
def tidy_events(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.sort_values("index").reset_index(drop=True)
    for col in ("location", "pass_end_location", "carry_end_location",
                "shot_end_location"):
        if col not in ev:
            ev[col] = None
    ev["x"] = ev["location"].map(lambda v: v[0] if isinstance(v, list) else None)
    ev["y"] = ev["location"].map(lambda v: v[1] if isinstance(v, list) else None)
    for col, prefix in (("pass_end_location", "pass_end"),
                        ("carry_end_location", "carry_end"),
                        ("shot_end_location", "shot_end")):
        ev[f"{prefix}_x"] = ev[col].map(lambda v: v[0] if isinstance(v, list) else None)
        ev[f"{prefix}_y"] = ev[col].map(lambda v: v[1] if isinstance(v, list) else None)
    # Match clock as a float, with stoppage time kept in its own period.
    ev["time"] = ev["minute"] + ev["second"] / 60
    # Columns that some matches lack but the app relies on.
    for col in ("shot_statsbomb_xg", "shot_outcome", "pass_outcome",
                "pass_recipient", "pass_type", "pass_shot_assist",
                "pass_goal_assist", "under_pressure", "dribble_outcome",
                "duel_type", "duel_outcome", "substitution_replacement",
                "foul_committed_card", "bad_behaviour_card", "tactics",
                "shot_type", "shot_body_part", "pass_cross", "duration"):
        if col not in ev:
            ev[col] = None
    return ev


def goals_by_team(ev: pd.DataFrame) -> dict[str, int]:
    """Goals per team: shot goals (outside a shoot-out) plus own goals for."""
    shots = ev[(ev["type"] == "Shot") & (ev["period"] <= 4)]
    goals = shots[shots["shot_outcome"] == "Goal"].groupby("team").size()
    ogs = ev[ev["type"] == "Own Goal For"].groupby("team").size()
    return goals.add(ogs, fill_value=0).astype(int).to_dict()
