"""Pitch and chart figures for the Match Explorer (matplotlib + mplsoccer)."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from mplsoccer import Pitch, VerticalPitch

import metrics as m

# Two categorical slots validated for colour-blind separation (home, away).
HOME_COLOR, AWAY_COLOR = "#2a78d6", "#eb6834"
SURFACE, INK, MUTED, LINE, GRID = "#fcfcfb", "#1f1f1e", "#6b6a64", "#c3c2b7", "#e1e0d9"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": LINE, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
})


def _pitch(**kw) -> Pitch:
    base = dict(pitch_type="statsbomb", pitch_color=SURFACE, line_color=LINE,
                linewidth=1.1, goal_type="box")
    base.update(kw)
    return Pitch(**base)


def _xg_size(xg):
    return 50 + np.asarray(xg, dtype=float) * 1300


def _xg_legend(ax, y=-0.02):
    h = [Line2D([], [], marker="o", ls="", markersize=10, markerfacecolor=MUTED,
                markeredgecolor=MUTED, label="Goal"),
         Line2D([], [], marker="o", ls="", markersize=10, markerfacecolor="none",
                markeredgecolor=MUTED, markeredgewidth=1.5, label="No goal"),
         Line2D([], [], marker="o", ls="", markersize=_xg_size(0.05) ** 0.5,
                markerfacecolor="none", markeredgecolor=MUTED, label="0.05 xG"),
         Line2D([], [], marker="o", ls="", markersize=_xg_size(0.5) ** 0.5,
                markerfacecolor="none", markeredgecolor=MUTED, label="0.5 xG")]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, y), ncol=4,
              frameon=False, fontsize=10, handletextpad=0.5, columnspacing=1.8)


# --------------------------------------------------------------------------- #
# Shots
# --------------------------------------------------------------------------- #
def shot_map(shots: pd.DataFrame, home: str, away: str):
    """Both teams on one pitch: home attacking left, away attacking right."""
    pitch = _pitch(pad_top=8, pad_bottom=12)
    fig, ax = pitch.draw(figsize=(11, 7.6))
    for team, color, flip in ((home, HOME_COLOR, True), (away, AWAY_COLOR, False)):
        s = shots[shots.team == team]
        if s.empty:
            continue
        x = 120 - s.x if flip else s.x
        y = 80 - s.y if flip else s.y
        goal = (s.shot_outcome == "Goal").to_numpy()
        size = _xg_size(s.shot_statsbomb_xg.fillna(0))
        pitch.scatter(x[~goal], y[~goal], s=size[~goal], ax=ax, facecolors="none",
                      edgecolors=color, linewidth=1.5, zorder=3)
        pitch.scatter(x[goal], y[goal], s=size[goal], ax=ax, color=color,
                      edgecolors=SURFACE, linewidth=2, zorder=4)
    ax.text(1, -3, f"◀ {home}", color=HOME_COLOR, fontsize=12, fontweight="bold", va="center")
    ax.text(119, -3, f"{away} ▶", color=AWAY_COLOR, fontsize=12, fontweight="bold",
            va="center", ha="right")
    _xg_legend(ax)
    return fig


def shot_end_map(shots: pd.DataFrame, color: str):
    """Where shots ended up, seen from behind the goal (on-target view)."""
    fig, ax = plt.subplots(figsize=(6, 2.6))
    ax.add_patch(plt.Rectangle((36, 0), 8, 2.67, fill=False, ec=INK, lw=2))
    s = shots.dropna(subset=["shot_end_y"])
    z = s["shot_end_location"].map(lambda v: v[2] if isinstance(v, list) and len(v) > 2 else np.nan)
    keep = z.notna() & s.shot_end_y.between(30, 50) & (z <= 4)
    s, z = s[keep], z[keep]
    goal = (s.shot_outcome == "Goal").to_numpy()
    size = _xg_size(s.shot_statsbomb_xg.fillna(0)) * 0.5
    ax.scatter(s.shot_end_y[~goal], z[~goal], s=size[~goal], facecolors="none",
               edgecolors=color, linewidths=1.4)
    ax.scatter(s.shot_end_y[goal], z[goal], s=size[goal], color=color,
               edgecolors=SURFACE, linewidths=1.5)
    ax.set_xlim(31, 49); ax.set_ylim(0, 4); ax.set_aspect("equal")
    ax.invert_xaxis()  # view from behind the goal, as the shooter sees it
    ax.axis("off")
    ax.axhline(0, color=LINE, lw=1)
    return fig


# --------------------------------------------------------------------------- #
# xG race
# --------------------------------------------------------------------------- #
def xg_race(ev: pd.DataFrame, home: str, away: str):
    s, og = m.xg_timeline(ev, [home, away])
    end = m.match_end_time(ev)
    fig, ax = plt.subplots(figsize=(8, 4))
    top = 0
    for team, color, opp in ((home, HOME_COLOR, away), (away, AWAY_COLOR, home)):
        ts = s[s.team == team]
        t = np.r_[0, ts.time, end]
        y = np.r_[0, ts.cum_xg, ts.cum_xg.iloc[-1] if len(ts) else 0]
        ax.step(t, y, where="post", color=color, lw=2, label=team)
        g = ts[ts.shot_outcome == "Goal"]
        ax.scatter(g.time, g.cum_xg, s=90, color=color, edgecolors=SURFACE,
                   linewidths=2, zorder=4)
        for _, r in g.iterrows():
            ax.annotate(f"{r['player'].split()[-1]} {r['minute']}'", (r.time, r.cum_xg),
                        xytext=(0, 9), textcoords="offset points", ha="center",
                        fontsize=8.5, color=INK)
        # Own goals scored *for* this team sit on its line at that moment.
        for _, r in og[og.team == team].iterrows():
            yv = ts[ts.time <= r.time].cum_xg.max() if (ts.time <= r.time).any() else 0
            ax.scatter(r.time, yv, s=90, marker="D", color=color, edgecolors=SURFACE,
                       linewidths=2, zorder=4)
            ax.annotate(f"OG {r['minute']}'", (r.time, yv), xytext=(0, 9),
                        textcoords="offset points", ha="center", fontsize=8.5)
        top = max(top, y.max())
    ax.axvline(45, color=GRID, lw=1, zorder=0)
    ax.set_xlim(0, end + 1); ax.set_ylim(0, top * 1.25 + 0.1)
    ax.set_xlabel("Minute"); ax.set_ylabel("Cumulative xG")
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# Passes
# --------------------------------------------------------------------------- #
def pass_map(p: pd.DataFrame, color: str, title: str = ""):
    pitch = _pitch(pad_bottom=6)
    fig, ax = pitch.draw(figsize=(11, 7.4))
    ok, bad = p[p.complete], p[~p.complete]
    pitch.arrows(bad.x, bad.y, bad.pass_end_x, bad.pass_end_y, ax=ax, color=MUTED,
                 alpha=0.45, width=1.4, headwidth=4, headlength=4, zorder=2)
    pitch.arrows(ok.x, ok.y, ok.pass_end_x, ok.pass_end_y, ax=ax, color=color,
                 width=1.6, headwidth=4, headlength=4, zorder=3)
    h = [Line2D([], [], color=color, lw=2, label=f"Complete ({len(ok)})"),
         Line2D([], [], color=MUTED, lw=2, alpha=0.6, label=f"Incomplete ({len(bad)})")]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=2,
              frameon=False, fontsize=10)
    ax.text(60, -2.5, "attacking ▶", ha="center", color=MUTED, fontsize=9)
    if title:
        ax.set_title(title, color=INK, fontsize=13, loc="left")
    return fig


def pass_network_plot(nodes: pd.DataFrame, edges: pd.DataFrame, color: str):
    pitch = _pitch(pad_bottom=2)
    fig, ax = pitch.draw(figsize=(11, 7.4))
    if nodes.empty:
        return fig
    pos = nodes.set_index("player")
    if not edges.empty:
        w = edges["count"] / edges["count"].max()
        for (_, e), wi in zip(edges.iterrows(), w):
            a, b = pos.loc[e.a], pos.loc[e.b]
            pitch.lines(a.x, a.y, b.x, b.y, ax=ax, color=color, lw=1 + 7 * wi,
                        alpha=0.25 + 0.6 * wi, zorder=2)
    size = 150 + 1100 * nodes.passes / max(nodes.passes.max(), 1)
    pitch.scatter(nodes.x, nodes.y, s=size, ax=ax, color=color, edgecolors=SURFACE,
                  linewidth=2, zorder=3)
    for _, n in nodes.iterrows():
        pitch.annotate(n.player.split()[-1], (n.x, n.y - 3.6), ax=ax, ha="center",
                       va="center", fontsize=9, color=INK, zorder=4,
                       bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.8))
    ax.text(60, 82.5, "attacking ▶   node size = passes made · line width = passes between the pair",
            ha="center", color=MUTED, fontsize=9)
    return fig


# --------------------------------------------------------------------------- #
# Player
# --------------------------------------------------------------------------- #
def touch_heatmap(pe: pd.DataFrame, color_map: str = "Blues"):
    pitch = _pitch(line_zorder=2, pad_bottom=2)
    fig, ax = pitch.draw(figsize=(7, 5))
    t = pe.dropna(subset=["x"])
    if len(t) >= 3:
        stats = pitch.bin_statistic(t.x, t.y, statistic="count", bins=(12, 8))
        pitch.heatmap(stats, ax=ax, cmap=color_map, edgecolors=SURFACE, lw=1, alpha=0.9)
    pitch.scatter(t.x, t.y, ax=ax, s=14, color=INK, alpha=0.35, zorder=3)
    ax.text(60, 82.5, f"attacking ▶   {len(t)} on-ball actions", ha="center",
            color=MUTED, fontsize=9)
    return fig


ACTION_STYLE = {  # type -> (marker, label)
    "Shot": ("*", "Shot"), "Dribble": ("D", "Dribble"), "Pressure": ("^", "Pressure"),
    "Duel": ("s", "Duel / tackle"), "Interception": ("P", "Interception"),
    "Ball Recovery": ("o", "Recovery"), "Clearance": ("X", "Clearance"),
}


def action_map(pe: pd.DataFrame, color: str):
    """Shots, dribbles and defensive actions, one marker shape per action."""
    pitch = _pitch(pad_bottom=10)
    fig, ax = pitch.draw(figsize=(7, 5))
    handles = []
    for t, (mk, label) in ACTION_STYLE.items():
        d = pe[(pe.type == t) & pe.x.notna()]
        if d.empty:
            continue
        pitch.scatter(d.x, d.y, ax=ax, marker=mk, s=110, color=color,
                      edgecolors=SURFACE, linewidth=1, alpha=0.85, zorder=3)
        handles.append(Line2D([], [], marker=mk, ls="", color=color, markersize=9,
                              label=f"{label} ({len(d)})"))
    if handles:
        ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0),
                  ncol=min(3, len(handles)), frameon=False, fontsize=9)
    return fig
