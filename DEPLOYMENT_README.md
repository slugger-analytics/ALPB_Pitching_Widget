# SLUGGER Pitching Widget Deployment Guide

## 1. Deployment Goal

Provide one public URL for the current `Dash + Python` app version.

Because this app has backend logic and server-side PDF generation, `GitHub Pages` is not suitable for production deployment.

## 2. Final Deployment Choice

- Platform: `Hugging Face Spaces`
- Type: `Docker Space`
- Public URL format: `https://<space-name>.hf.space`

Current target Space:

- `Zora12345/Slugger`

## 3. What Was Changed in This Repo

The repository was updated for Space deployment:

- Added `Dockerfile` to run the Dash app with `gunicorn`.
- Added `.dockerignore` to keep image build clean.
- Updated `README.md` metadata for Hugging Face Space (`sdk: docker`, `app_port: 7860`).
- Updated app startup so cloud environments use `PORT`.
- Added `/healthz` endpoint for runtime health checks.
- Moved API keys out of source code to environment variables in `python_app/config.py`.

## 4. Required Secrets

Configure these in Hugging Face Space settings (Secrets):

- `POINTSTREAK_API_KEY`
- `ALPB_API_KEY`

Both values must be set before the app can load live data.

## 5. Step-by-Step Deployment (UI Flow)

1. Create or open the Space on Hugging Face.
2. Set Space SDK to `Docker` (if creating a new Space).
3. Upload/push project files (`Dockerfile`, `README.md`, `python_app/`, etc.).
4. Go to `Settings -> Variables and secrets`.
5. Add:
   - `POINTSTREAK_API_KEY`
   - `ALPB_API_KEY`
6. Restart/rebuild the Space.
7. Verify:
   - Main app URL loads.
   - `https://<space-name>.hf.space/healthz` returns `{"status":"ok"}`.
   - PDF download works from the UI.

## 6. Common Issues and Fixes

### Issue A: Callback error on PDF download

Symptom:

- Frontend shows `Callback error updating download-pdf.data`.

Fix applied:

- Added safer checks for missing pitch-tag columns in PDF pipeline.
- Added exception guard in PDF download callback to avoid 500 crashes.

### Issue B: Push rejected due binary files

Symptom:

- Hugging Face pre-receive hook rejects push with old binary objects from git history.

Fix:

- Push from a clean history snapshot (new git history) or upload via Space web UI.

## 7. Hugging Face Free Limits (Important)

Hugging Face Space is not unlimited on free tier:

- Free `CPU Basic` has resource limits (CPU, RAM, disk).
- Free Spaces can sleep when inactive.
- Disk on Spaces is ephemeral by default.

So the platform is free to start, but it still has runtime/storage/lifecycle limits.

Official docs:

- Spaces lifecycle and sleep on free hardware: https://huggingface.co/docs/hub/main/en/spaces-overview
- Spaces disk behavior (ephemeral by default): https://huggingface.co/docs/hub/spaces-storage
- Docker Space config (`sdk: docker`, `app_port`): https://huggingface.co/docs/hub/en/spaces-sdks-docker
- Space YAML config reference: https://huggingface.co/docs/hub/en/spaces-config-reference

## 8. Submission Link

Use your final public Space URL, for example:

- `https://zora12345-slugger.hf.space`
