# ALPB Pitching Widget

The **Atlantic League of Professional Baseball (ALPB) Pitching Widget** is a Dash application for analyzing pitcher performance with Pointstreak and ALPB Trackman data.

## Live App

- Production (Render): `https://<your-render-service>.onrender.com`

## Features

- Pitcher profile and player metadata
- Season statistics (ERA, WHIP, strikeouts, etc.)
- Interactive charts:
  - Break vs. velocity
  - iVB vs. HB
  - Strike zone heatmaps
  - Pitch type usage
- PDF one-sheet export

## Local Run

```bash
git clone https://github.com/slugger-analytics/ALPB_Pitching_Widget.git
cd ALPB_Pitching_Widget
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_app/requirements.txt
python python_app/app.py
```

Open `http://localhost:8050`.

Port behavior:
- Local default: `8050`
- Cloud runtime: uses `PORT` from the hosting platform

## Environment Variables

Set these values locally or in Render environment settings:

- `POINTSTREAK_API_KEY` (required)
- `ALPB_API_KEY` (required)
- `POINTSTREAK_BASE_URL` (optional)
- `ALPB_BASE_URL` (optional)
- `DEFAULT_SEASON_ID` (optional)
- `DASH_DEBUG` (optional; default `false`)

Use `.env.example` as a template for local development.

## Render Deployment Setup

### Option A: Blueprint Deploy (recommended)

1. Push this repository to GitHub.
2. In Render, click `New +` -> `Blueprint`.
3. Select this repository.
4. Render reads `render.yaml` and creates the web service.
5. Add required secrets:
   - `POINTSTREAK_API_KEY`
   - `ALPB_API_KEY`
6. Trigger deploy.
7. Verify:
   - App homepage loads
   - `https://<your-render-service>.onrender.com/healthz` returns `{"status":"ok"}`
   - PDF export works from UI

### Option B: Manual Web Service

1. In Render, click `New +` -> `Web Service`.
2. Connect this repository and set:
   - Runtime: `Python`
   - Build Command: `pip install -r python_app/requirements.txt`
   - Start Command: `gunicorn python_app.app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
3. Add required environment variables.
4. Deploy and verify `/healthz`.

Auto-deploy can stay enabled so each push to `main` triggers a new Render deploy.

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
