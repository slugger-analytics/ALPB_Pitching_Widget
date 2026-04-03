# SLUGGER Pitching Widget Deployment Guide

## 1. Deployment Goal

Provide a reproducible deployment path for the Dash app and maintain one stable public URL for review.

## 2. Deployment Platform

- Platform: **Render**
- Service type: **Web Service**
- URL format: `https://<your-render-service>.onrender.com`

## 3. Required Files in Repository

- `render.yaml` (Blueprint config)
- `python_app/requirements.txt`
- `python_app/app.py` (exposes `server = app.server`)

## 4. Deploy with Render Blueprint (Recommended)

1. Push latest code to GitHub.
2. In Render dashboard, click `New +` -> `Blueprint`.
3. Connect and select this repository.
4. Render reads `render.yaml` and provisions the web service.
5. In service environment variables, set:
   - `POINTSTREAK_API_KEY`
   - `ALPB_API_KEY`
   - `DASH_DEBUG=false`
6. Deploy.

## 5. Manual Render Setup (Fallback)

If Blueprint is not used, configure the service manually:

- Runtime: `Python`
- Build command: `pip install -r python_app/requirements.txt`
- Start command: `gunicorn python_app.app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- Health check path: `/healthz`

Required secrets:
- `POINTSTREAK_API_KEY`
- `ALPB_API_KEY`

Optional overrides:
- `POINTSTREAK_BASE_URL`
- `ALPB_BASE_URL`
- `DEFAULT_SEASON_ID`
- `DASH_DEBUG`

## 6. Post-Deploy Validation Checklist

1. Service URL returns HTTP 200.
2. `/healthz` returns `{"status":"ok"}`.
3. Team/player dropdowns load real data.
4. PDF export succeeds.

## 7. Handoff Notes (Next Maintainer)

- Keep `autoDeploy` enabled for main branch deployment automation.
- If service URL changes, update both:
  - `README.md` (`Live App` section)
  - this `DEPLOYMENT_README.md` (`Deployment Platform` section)
- Keep API keys only in Render environment settings; do not commit credentials.

## 8. Why Static Pages Were Removed

This project is backend-driven (Dash + server-side PDF generation), so static-site deployment was removed. Deployment is managed on Render.
