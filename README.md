# SLUGGER Pitching Widget

`SLUGGER Pitching Widget` is a Dash web application for reviewing ALPB pitcher performance from roster metadata, season-level stats, and pitch-by-pitch Trackman-style visualizations. The project was built to give coaches, analysts, and students a fast way to move from raw baseball data to a usable scouting dashboard and PDF handout.

## Live Deployment

- Production (Render): `https://slugger-pitching-widget-xfcw.onrender.com/`
- Hugging Face Space: [https://zora12345-slugger.hf.space/](https://zora12345-slugger.hf.space/)
This repository is organized as a small production-style Python app with:

- UI feature modules in `python_app/features/`
- API and caching utilities in `python_app/lib/`
- deployment configuration for Render
- a public sample-data mode so reviewers can run the project without private credentials

## What The App Does

- loads pitcher rosters and season stats
- resolves each pitcher to pitch-level data
- renders movement scatter plots, strike-zone heatmaps, and pitch-mix tables
- exports one-page or team PDF scouting reports

## Why It Matters

The app turns analyst-facing baseball data into a reviewer-friendly workflow:

- one app instead of multiple ad hoc notebooks
- consistent charts across the web UI and exported PDFs
- a cached data flow that reduces repeated vendor API calls

## Repository Structure

```text
.
├── CONTRIBUTING.md
├── HANDOFF.md
├── README.md
├── DEPLOYMENT_README.md
├── Dockerfile
├── render.yaml
├── requirements.txt
├── data/
│   ├── README.md
│   └── sample/
├── scripts/
│   ├── generate_sample_outputs.py
│   └── smoke_test.py
└── python_app/
    ├── app.py
    ├── config.py
    ├── requirements.txt
    ├── assets/
    ├── features/
    └── lib/
```

## Required Software Versions

- Python `3.11` recommended
- Python `3.12` also works for local development
- `pip` or another standard Python package installer

The production container uses `python:3.11-slim` in [Dockerfile](/Users/zora/pitcher/SLUGGER-Pitching-Widget/Dockerfile:1).

## Package Dependencies

The canonical dependency list lives in [python_app/requirements.txt](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/requirements.txt:1). Major libraries include:

- `dash`
- `dash-bootstrap-components`
- `pandas`
- `numpy`
- `scipy`
- `plotly`
- `matplotlib`
- `requests`
- `kaleido`
- `gunicorn`
- `python-dotenv`

Install everything from the repo root with:

```bash
pip install -r requirements.txt
```

## Quick Start For Reviewers

This is the fastest 5-minute setup path and does **not** require private API keys.

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Start the app.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m python_app.app
```

Open `http://localhost:8050`.

The default `.env.example` uses `DATA_SOURCE=sample`, so the dashboard runs against bundled synthetic sample data.

## Running With Private Live Data

The full production dashboard requires private API access.

1. Copy `.env.example` to `.env`.
2. Change `DATA_SOURCE=live`.
3. Fill in:
   - `POINTSTREAK_API_KEY`
   - `ALPB_API_KEY`
4. Optionally adjust:
   - `DEFAULT_SEASON_ID`
   - `POINTSTREAK_BASE_URL`
   - `ALPB_BASE_URL`
5. Run:

```bash
python -m python_app.app
```

## Data Requirements And Privacy

This project relies on private vendor/API data in production. That raw data is **not** committed to the public repository.

- Publicly included:
  - synthetic reviewer-safe files in `data/sample/`
- Not publicly included:
  - live Pointstreak data
  - live ALPB Trackman data
  - private credentials

See [data/README.md](/Users/zora/pitcher/SLUGGER-Pitching-Widget/data/README.md:1) for required filenames, expected columns, and transfer expectations.

If full data access is needed for grading or continuation, it should be transferred privately and securely rather than pushed to GitHub.

## Conditioning / Data Processing Pipeline

There is no separate offline ETL job in this repo; the dashboard conditions data at load time.

### Live mode

1. `python_app/lib/api.py`
   - pulls roster rows from Pointstreak
   - pulls season stats from Pointstreak
   - resolves player IDs and pitch pages from the ALPB API
2. `python_app/lib/conditioning.py`
   - normalizes roster columns
   - strips missing/invalid names
   - creates `full_name`
   - filters one-player season stats and pitch records for downstream use
3. `python_app/lib/cache.py`
   - memoizes roster, stats, player-ID lookups, and pitch records
4. `python_app/features/`
   - converts conditioned data into tables and visualizations

### Sample mode

1. `python_app/lib/sample_data.py`
   - loads synthetic CSVs from `data/sample/`
2. `python_app/lib/conditioning.py`
   - applies the same cleanup rules used by live mode

### Schema assumptions

- roster data includes first/last name, team, handedness, and player identifiers
- season stats can be filtered by `playerlinkid`
- pitch data includes pitch type, count, movement, and plate-location columns

Missing values are generally handled with empty strings for display fields and dropped rows for unusable plotting fields.

## Reproducing Main Outputs

### Public reviewer-safe reproduction

Run the sample smoke test:

```bash
python3 scripts/smoke_test.py --data-source sample
```

Generate representative sample outputs:

```bash
python3 scripts/generate_sample_outputs.py
```

This writes CSV summaries and HTML visualizations to `output/sample_review/`.

### Full private-data reproduction

If the presentation or report quotes player-specific live results:

1. set `DATA_SOURCE=live`
2. supply valid API keys in `.env`
3. verify connectivity with:

```bash
python3 scripts/smoke_test.py --data-source live
```

4. start the app and navigate to the same team/pitcher/season configuration used in the presentation

Because the underlying production data is private and changes over time, exact quoted live values cannot be bundled publicly in this repo.

## Validation / Evaluation

This repository does **not** contain a predictive model, so train/test evaluation is not applicable.

Instead, correctness is checked through:

- dashboard smoke tests in [scripts/smoke_test.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/scripts/smoke_test.py:1)
- visual sanity checks for plots and tables
- API health checks during deployment
- manual PDF export verification

## Compute Requirements And Runtime

- Sample mode starts in a few seconds on a laptop.
- Live mode startup time depends on vendor API latency and roster size.
- Team PDF generation can take noticeably longer than single-player PDF export.
- No GPU is required.

## Important Design Decisions

- Feature-level UI code is split across `python_app/features/` instead of one large Dash script.
- API logic lives in `python_app/lib/api.py` and is wrapped by `python_app/lib/cache.py`.
- Reviewer access is handled through `DATA_SOURCE=sample` rather than shipping private data.
- The same chart builders are reused between the live dashboard and PDF export to keep outputs consistent.

## Known Limitations

- The app depends on third-party APIs in live mode and cannot recover from upstream outages.
- Pitch-level plots are only as complete as the ALPB pitch feed.
- There is no automated end-to-end browser test suite yet.
- PDF generation depends on `kaleido`; missing local installs can reduce export fidelity.
- The attempted iScore migration is not included because the documented endpoints were returning server-side `500` errors during testing in late April 2026.

## Handoff Notes For Future Students

- Start in [HANDOFF.md](/Users/zora/pitcher/SLUGGER-Pitching-Widget/HANDOFF.md:1).
- Keep sample mode working; it is the easiest way for reviewers to validate the project.
- If vendor APIs change, update `python_app/lib/api.py`, `python_app/lib/conditioning.py`, and `scripts/smoke_test.py` together.
- If the team wants reproducible historical results, add a secure private snapshot workflow outside the public repo.

## Deployment

- Render configuration: [render.yaml](/Users/zora/pitcher/SLUGGER-Pitching-Widget/render.yaml:1)
- Deployment notes: [DEPLOYMENT_README.md](/Users/zora/pitcher/SLUGGER-Pitching-Widget/DEPLOYMENT_README.md:1)
- Health endpoint: `/healthz`

## Contact / Maintainer Notes

This repo is set up for handoff more than long-term product ownership. Future student maintainers should document any data-source, season, or deployment changes in `HANDOFF.md` and keep the README aligned with the live workflow.
