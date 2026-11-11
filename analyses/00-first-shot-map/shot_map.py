"""WSL shot map from StatsBomb open data.

Liverpool WFC 4-3 Chelsea FCW, 1 May 2024 (WSL 2023/24).
Data: Hudl StatsBomb open data (https://github.com/statsbomb/open-data).

    pip install statsbombpy mplsoccer
    python shot_map.py
"""
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")

from matplotlib.lines import Line2D
from mplsoccer import Pitch
from statsbombpy import sb

MATCH_ID = 3913173
HOME, AWAY = "Liverpool WFC", "Chelsea FCW"
SHORT = {HOME: "Liverpool", AWAY: "Chelsea"}
FINAL_SCORE = (4, 3)  # Chelsea's third was a Liverpool own goal (82')
COLORS = {HOME: "#eb6834", AWAY: "#2a78d6"}   # validated categorical slots 2 and 1
SURFACE, INK, MUTED, LINE = "#fcfcfb", "#1f1f1e", "#6b6a64", "#c3c2b7"


def marker_area(xg):
    return 60 + xg * 1400


events = sb.events(match_id=MATCH_ID)
shots = events[events["type"] == "Shot"].copy()
shots = shots[shots["period"] <= 4]  # exclude any penalty shoot-out
shots["x"] = shots["location"].str[0]
shots["y"] = shots["location"].str[1]
shots["goal"] = shots["shot_outcome"] == "Goal"
own_goals = events[events["type"] == "Own Goal For"].groupby("team").size()

# StatsBomb y runs top-to-bottom, so negative y is the space above the pitch.
pitch = Pitch(pitch_type="statsbomb", pitch_color=SURFACE, line_color=LINE,
              linewidth=1.2, goal_type="box", pad_top=30, pad_bottom=14,
              pad_left=4, pad_right=4)
fig, ax = pitch.draw(figsize=(12, 9.5))
fig.set_facecolor(SURFACE)

summary = {}
for team, s in shots.groupby("team"):
    s = s.copy()
    if team == HOME:  # home attacks left so both teams share one pitch
        s["x"] = 120 - s["x"]
        s["y"] = 80 - s["y"]
    c = COLORS[team]
    miss, goal = s[~s["goal"]], s[s["goal"]]
    pitch.scatter(miss.x, miss.y, s=marker_area(miss["shot_statsbomb_xg"]), ax=ax,
                  facecolors="none", edgecolors=c, linewidth=1.6, alpha=0.9, zorder=3)
    pitch.scatter(goal.x, goal.y, s=marker_area(goal["shot_statsbomb_xg"]), ax=ax,
                  color=c, edgecolors=SURFACE, linewidth=2, zorder=4)
    summary[team] = (int(s["goal"].sum()), len(s), s["shot_statsbomb_xg"].sum())

# Header
ax.text(60, -24, f"{SHORT[HOME]} {FINAL_SCORE[0]}–{FINAL_SCORE[1]} {SHORT[AWAY]}",
        ha="center", va="center", fontsize=22, fontweight="bold", color=INK)
ax.text(60, -18, "Women's Super League 2023/24 · 1 May 2024 · every shot, sized by xG",
        ha="center", va="center", fontsize=12, color=MUTED)
for team, x, ha in [(HOME, 0, "left"), (AWAY, 120, "right")]:
    g, n, xg = summary[team]
    og = int(own_goals.get(team, 0))
    stats = f"{n} shots · {xg:.2f} xG · {g} goals" + (f" + {og} OG" if og else "")
    ax.text(x, -9, SHORT[team], ha=ha, va="center", fontsize=15,
            fontweight="bold", color=COLORS[team])
    ax.text(x, -4, stats, ha=ha, va="center", fontsize=11.5, color=INK)
ax.text(42, -6.5, "◀ attacking", ha="center", va="center", fontsize=10, color=MUTED)
ax.text(78, -6.5, "attacking ▶", ha="center", va="center", fontsize=10, color=MUTED)

# Legend: size keys drawn at the same scale as the data markers
handles = [
    Line2D([], [], marker="o", ls="", markersize=11, markerfacecolor=MUTED,
           markeredgecolor=MUTED, label="Goal"),
    Line2D([], [], marker="o", ls="", markersize=11, markerfacecolor="none",
           markeredgecolor=MUTED, markeredgewidth=1.6, label="No goal"),
    Line2D([], [], marker="o", ls="", markersize=marker_area(0.05) ** 0.5,
           markerfacecolor="none", markeredgecolor=MUTED, label="0.05 xG"),
    Line2D([], [], marker="o", ls="", markersize=marker_area(0.5) ** 0.5,
           markerfacecolor="none", markeredgecolor=MUTED, label="0.5 xG"),
]
ax.legend(handles=handles, loc="center", bbox_to_anchor=(0.5, 0.085), ncol=4,
          frameon=False, fontsize=11, labelcolor=INK, handletextpad=0.6,
          columnspacing=2.2, borderaxespad=0)
ax.text(60, 91, "Data: Hudl StatsBomb open data  ·  Viz: Dr Lee Skrypchuk (statsbombpy + mplsoccer)",
        ha="center", va="center", fontsize=9.5, color=MUTED)

fig.savefig(Path(__file__).with_name("wsl_shot_map.png"), dpi=200, facecolor=SURFACE, bbox_inches="tight")
print(summary)
