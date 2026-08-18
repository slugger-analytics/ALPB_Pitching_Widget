# SLUGGER Pitching Widget

`SLUGGER Pitching Widget` is a Dash web application for reviewing ALPB pitcher performance from roster metadata, season-level stats, and pitch-by-pitch Trackman visualizations. It gives coaches, analysts, and scouts a fast way to move from raw baseball data to a usable scouting dashboard and PDF handout.

## What The App Does

- Loads pitcher rosters and season stats from iScore
- Resolves each pitcher to pitch-level Trackman data via the ALPB API
- Renders movement scatter plots, strike-zone heatmaps, and pitch-mix tables
- Exports one-page or full-team PDF scouting reports

## Why It Matters

- One app instead of multiple ad hoc notebooks
- Consistent charts across the web UI and exported PDFs
- A cached data flow that reduces repeated vendor API calls

## Repository Structure

```text
.
├── CONTRIBUTING.md
├── HANDOFF.md
├── README.md
├── Dockerfile
├── requirements.txt
├── output/
├── scripts/
└── python_app/
    ├── app.py
    ├── config.py
    ├── assets/
    ├── features/
    └── lib/
```

## Required Software Versions

- Python `3.11` recommended (`3.12` also works for local development)
- `pip` or another standard Python package installer

## Package Dependencies

Major libraries:

- `dash`, `dash-bootstrap-components`
- `pandas`, `numpy`, `scipy`
- `plotly`, `matplotlib`
- `requests`, `python-dotenv`
- `kaleido`, `gunicorn`

Install from the repo root:

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
python -m python_app.app
```

Open `http://localhost:8050`.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `ALPB_API_KEY` | ALPB Trackman API key |
| `ALPB_BASE_URL` | ALPB API base URL |
| `ISCORE_BASE_URL` | iScore API base URL |
| `ISCORE_LEAGUE_GUID` | iScore league GUID for the current ALPB season |
| `ISCORE_SEASON_GUID` | iScore season GUID for stat lookups |

## Data Flow

1. **`python_app/lib/api.py`** — fetches roster and season stats from iScore; resolves pitcher names to ALPB Trackman IDs; pulls pitch-by-pitch data
2. **`python_app/lib/cache.py`** — memoizes roster, stats, player-ID lookups, and pitch records
3. **`python_app/features/`** — converts cached data into tables and visualizations

## Deployment

The app runs as a Docker container. Build and run locally:

```bash
docker build -t slugger-widget .
docker run -p 7860:7860 --env-file .env slugger-widget
```

Health endpoint: `/healthz`

## Known Limitations

- The app depends on third-party APIs and cannot recover from upstream outages
- Pitch-level plots are only as complete as the ALPB Trackman feed
- ~5 pitchers per season are unmatched between iScore and ALPB due to name differences
- PDF generation depends on `kaleido`

## Contact / Maintainer Notes

Future maintainers should document any data-source, season, or deployment changes in `HANDOFF.md` and keep the README aligned with the live workflow.
