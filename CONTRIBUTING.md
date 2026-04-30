# Contributing Guide

## Workflow

- Do not commit directly to `main` for feature work.
- Use a short-lived branch per task.
- Keep public reviewer workflows working when you change data or UI code.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m python_app.app
```

Sample mode is the default reviewer path. For live mode, set `DATA_SOURCE=live` in `.env` and provide private API keys.

## Before Opening A PR

Run:

```bash
python3 scripts/smoke_test.py --data-source sample
```

If your change affects live APIs or deployment, also run:

```bash
python3 scripts/smoke_test.py --data-source live
```

Then summarize:

- what changed
- why it changed
- how you tested it

## Deployment Notes

- Deployment platform: Render
- Keep service config in `render.yaml` aligned with production settings.
- Keep secrets in environment settings only; never commit API keys.
