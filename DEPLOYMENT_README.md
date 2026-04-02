# SLUGGER Pitching Widget Deployment Guide

## 1. Deployment Goal

Provide a reproducible deployment process for the Dash app and keep one stable public URL for demos/checkpoints.

## 2. Current Production URL

- Hugging Face Space (active): https://zora12345-slugger.hf.space

## 3. Platform Options

### A) Hugging Face Spaces (Primary)

Use this when you need the existing live app link used in class/checkpoint review.

1. Open or create Space `Zora12345/Slugger`.
2. Set SDK to `Docker`.
3. Push this repository or upload files (`Dockerfile`, `python_app/`, `README.md`, etc.).
4. In `Settings -> Variables and secrets`, add:
   - `POINTSTREAK_API_KEY`
   - `ALPB_API_KEY`
5. Rebuild the Space.
6. Validate:
   - App home page loads.
   - `/healthz` returns `{"status":"ok"}`.
   - PDF download works in UI.
7. Optional automation:
   - If connected to GitHub, Space can auto-build on new pushes.

### B) Render Web Service (Backup)

Use this as an alternate deployment target.

1. Create a new Web Service on Render.
2. Connect this GitHub repository.
3. Keep `render.yaml` in repo root (Blueprint config).
4. Ensure env vars are set in Render:
   - `POINTSTREAK_API_KEY`
   - `ALPB_API_KEY`
   - `DASH_DEBUG=false`
5. Deploy and verify endpoint health.
6. Optional automation:
   - Keep `autoDeploy: true` in `render.yaml` to auto-deploy on each push.

## 4. Required Environment Variables

- `POINTSTREAK_API_KEY`
- `ALPB_API_KEY`
- Optional overrides:
  - `POINTSTREAK_BASE_URL`
  - `ALPB_BASE_URL`
  - `DEFAULT_SEASON_ID`
  - `DASH_DEBUG`

## 5. Notes for Handoff (Next Maintainer)

- Preferred live link to share: **https://zora12345-slugger.hf.space**
- If you redeploy and URL changes, update both:
  - `README.md` (`Live App` section)
  - this `DEPLOYMENT_README.md` (`Current Production URL` section)
- Keep secrets only in platform settings; do not commit real API keys.

## 6. Why GitHub Pages CI/CD Was Removed

This project is backend-driven (Dash + server-side PDF export), so static GitHub Pages CI/CD was removed. Runtime deployment is now documented for Hugging Face and Render only.
