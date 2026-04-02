---
title: SLUGGER Pitching Widget
emoji: ⚾
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
---

# ALPB Pitching Widget

The **Atlantic League of Professional Baseball (ALPB) Pitching Widget** is an app for analyzing pitching performance with Trackman and Pointstreak data.

## Live App

- Hugging Face (production): https://zora12345-slugger.hf.space

## Features

- Pitcher profile and player metadata
- Season statistics (ERA, WHIP, strikeouts, etc.)
- Interactive charts:
  - Break vs. velocity
  - iVB vs. HB
  - Strike zone heatmaps
  - Pitch type usage
- PDF one-sheet export

## Local Run (Dash)

The production app is implemented in `python_app/` using [Dash](https://dash.plotly.com/).

```bash
git clone https://github.com/tanx3036/ALPB_Pitching_Widget.git
cd ALPB_Pitching_Widget
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_app/requirements.txt
python python_app/app.py
```

Then open `http://localhost:8050`.

## Environment Variables

Set these values in your environment (or deployment platform secrets):

- `POINTSTREAK_API_KEY`
- `ALPB_API_KEY`
- `POINTSTREAK_BASE_URL` (optional)
- `ALPB_BASE_URL` (optional)
- `DEFAULT_SEASON_ID` (optional)
- `DASH_DEBUG` (optional; default `false`)

You can copy from `.env.example` to get started quickly.

## Deployment

- Primary: Hugging Face Spaces (Docker), current production link above.
- Alternate: Render Web Service.
- Deployment automation: both platforms can auto-redeploy on push (platform-managed, not GitHub Pages Actions).
- Full deployment walkthrough: `DEPLOYMENT_README.md`.

## Project Structure

```text
.
├── DEPLOYMENT_README.md
├── Dockerfile
├── render.yaml
└── python_app/
    ├── app.py
    ├── requirements.txt
    ├── assets/
    ├── features/
    └── lib/
```

## Collaboration Workflow

- Use feature branches for changes.
- Open a pull request before merging to `main`.
- Keep deployment notes updated in `DEPLOYMENT_README.md`.
