# ALPB Pitching Widget

The **Atlantic League of Professional Baseball (ALPB) Pitching Widget** is an app for analyzing pitching performance with Trackman and Pointstreak data.

## Features

- Pitcher profile and player metadata
- Season statistics (ERA, WHIP, strikeouts, etc.)
- Interactive charts:
  - Break vs. velocity
  - iVB vs. HB
  - Strike zone heatmaps  
  - Pitch type usage
- PDF one-sheet export

## Python App (Dash)

The production app is implemented in `python_app/` using [Dash](https://dash.plotly.com/).

### Local Run

```bash
git clone https://github.com/tanx3036/SLUGGER-Pitching-Widget.git
cd SLUGGER-Pitching-Widget
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_app/requirements.txt
python python_app/app.py
```

Then open `http://localhost:8050`.

## GitHub Pages

This repo includes a GitHub Pages deployment workflow for a static project page under `docs/`.

- Workflow file: `.github/workflows/pages.yml`
- Static page source: `docs/index.html`
- Publish trigger: push to `main` (or manual workflow dispatch)

### Enable Pages in Repository Settings

1. Go to **Settings** -> **Pages**.
2. Under **Build and deployment**, choose **Source: GitHub Actions**.
3. Push to `main` and wait for the **Deploy GitHub Pages** workflow to finish.

## Notes

- GitHub Pages can host static content only.
- The Dash app itself still runs as a Python web service (local machine or a cloud host).

## Project Structure

```text
.
├── .github/workflows/pages.yml
├── docs/index.html
└── python_app/
    ├── app.py
    ├── requirements.txt
    ├── assets/
    ├── features/
    └── lib/
```
