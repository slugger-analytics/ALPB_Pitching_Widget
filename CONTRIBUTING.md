# Contributing Guide

## Branching and Merge Requests

- Do not commit directly to `main` for feature work.
- Create a branch per task (example: `feature/pdf-fix`, `fix/render-deploy`).
- Open a pull request to `main` with:
  - what changed
  - why it changed
  - how it was tested

## Local Repro Steps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_app/requirements.txt
export POINTSTREAK_API_KEY=...
export ALPB_API_KEY=...
python python_app/app.py
```

Open `http://localhost:8050` and verify app load + PDF export.

## Deployment Notes

- Deployment platform: Render
- Keep service config in `render.yaml` aligned with production settings
- Keep secrets in Render environment settings only; never commit keys
