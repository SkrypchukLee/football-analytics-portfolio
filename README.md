# Football Analytics Portfolio

**Human factors meets football.** Using event data, tracking data and match video to understand how players perceive, decide and act on the pitch, and turning that into insight a coach or recruiter can use.

---

## About me

I'm Dr Lee Skrypchuk, a human factors researcher with 20+ years in industry (currently Senior Technical Specialist in Human Machine Interface at Jaguar Land Rover). My work and PhD (Cambridge) focus on situation awareness, cognitive load, decision-making and human-automation interaction. I also coach a grassroots girls' team in Coventry.

This repo is where I apply that background to football: the same questions I ask about drivers ("what did they see, what did they expect, why did they choose that?") asked about players.

## My angle

Most football analytics describes *what* happened. I'm interested in *why* players make the choices they do:

- **Scanning and perception**: how much space and how many options a player has when they receive the ball, and how that shapes what they do next
- **Decision-making under pressure**: how pressure, time and context relate to pass choice and outcome
- **Decision speed**: how quickly players act after receiving the ball, measured from match video
- **Coaching translation**: presenting findings in plain language for coaches and players, not just data scientists

## Analyses

| # | Analysis | Question it answers | Status |
|---|----------|---------------------|--------|
| 1 | Team profile (WSL) | What does an opposition coach need to know about this team? | Planned: Dec 2026 |
| 2 | Midfielder comparison | How do three midfielders compare on progression, pressing and chance involvement? | Planned: Dec 2026 |
| 3 | Scanning and decision-making | Do midfielders with more space and options choose progressive passes more often? | Planned: Feb 2027 |
| 4 | Grassroots case study | What did using data change for a U16 girls' squad? | Planned: Mar 2027 |
| 5 | Recruitment shortlist | Who fits a defined role, and why? | Planned: Apr 2027 |

Each analysis lives in its own folder with a notebook, the charts, and a short write-up. Links to the published blog posts will be added here as they go live.

## Apps

| App | What it does |
|-----|--------------|
| [Match Explorer](apps/match_explorer/) | Load any StatsBomb match (open data or your own JSON) and explore team stats, xG race, shots, passes, pass networks, players and raw events. `streamlit run apps/match_explorer/app.py` |

## Repository structure

```
football-analytics-portfolio/
├── README.md
├── notes/                 # Learning notes (StatsBomb course, glossary of metrics)
├── apps/
│   └── match_explorer/    # Streamlit app for exploring one match
├── analyses/
│   ├── 00-first-shot-map/
│   ├── 01-team-profile/
│   ├── 02-player-comparison/
│   ├── 03-scanning-decisions/
│   ├── 04-grassroots-case-study/
│   └── 05-recruitment/
├── src/                   # Reusable helpers (data loading, plotting)
├── requirements.txt
└── LICENSE
```

## Tools and data

- **Python**: pandas, numpy, matplotlib, scikit-learn / statsmodels
- **[statsbombpy](https://github.com/statsbomb/statsbombpy)**: loading StatsBomb open data
- **[mplsoccer](https://github.com/andrewRowlinson/mplsoccer)**: pitch plots, pass networks, shot maps, radars
- **[StatsBomb Open Data](https://github.com/statsbomb/open-data)**: free event and 360 freeze-frame data, including the Women's Super League
- **Match video**: my own [football video analysis tool](https://github.com/SkrypchukLee/LeesFootballAnalysisTool) for grassroots footage

## Getting started

```bash
git clone https://github.com/SkrypchukLee/football-analytics-portfolio.git
cd football-analytics-portfolio
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter lab
```

## Learning log

- [ ] Hudl StatsBomb *Introduction to Football Analytics* course (Nov 2026)
- [ ] Friends of Tracking videos on event and tracking data
- [ ] Glossary of key metrics: xG, xT, PPDA, field tilt, progressive passes, possession value
- [x] First plot: [WSL shot map](analyses/00-first-shot-map/) with statsbombpy and mplsoccer
- [x] [Match Explorer](apps/match_explorer/) app for interrogating a single match

## Data and ethics

- Analyses using StatsBomb open data credit StatsBomb as their terms require.
- Grassroots and youth footage is only used with the agreement of the club and parents. All players are fully anonymised: no names, no faces.

## Contact

- GitHub: [@SkrypchukLee](https://github.com/SkrypchukLee)
- LinkedIn: *add link*
- Blog: *add link*

Always happy to talk football, data, or how people make decisions under pressure.

---

<sub>Data provided by StatsBomb (Hudl).</sub>
