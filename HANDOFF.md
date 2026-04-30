# Handoff Notes

## Current Project Status

The Dash application is functional and organized for reviewer handoff. The repository now supports:

- a public `sample` mode for quick startup without credentials
- a private `live` mode for the full Pointstreak + ALPB workflow
- smoke-test and sample-output scripts
- cleaner documentation for setup, deployment, and data access

## What Works

- app boot in sample mode
- app boot in live mode when valid API keys are available
- roster loading and player selection
- season-stat table rendering
- pitch movement scatter plots
- strike-zone heatmaps
- pitch-split table
- single-player and team PDF export
- Render deployment configuration

## What Is Partially Completed

- live reproducibility still depends on private API uptime and current vendor schemas
- the project has smoke tests, but not a full browser-based regression suite
- sample mode demonstrates the workflow but does not reproduce the full private production dataset

## What Was Tried But Did Not Work

- An iScore API migration was investigated in April 2026.
- Production, staging, and dev iScore endpoints repeatedly returned `HTTP 500` on public routes and even on Swagger/OpenAPI routes.
- Because the upstream service was unstable, no iScore integration was merged into this repo.

## Known Bugs Or Limitations

- Live mode can fail silently if upstream vendor payloads change unexpectedly.
- PDF export relies on external rendering dependencies and can be slower for full-team reports.
- The app currently loads roster data at startup rather than via a background refresh job.
- There is no built-in credential validation screen; failures surface as empty data or missing sections.

## Natural Next Steps

1. Add lightweight automated tests around PDF export and cache behavior.
2. Add a secure private snapshot workflow for fixed historical review datasets.
3. If iScore becomes stable, evaluate whether it can replace only the roster/stat layer or the full pitch layer.
4. Consider adding a small `docs/` folder with screenshots for future reviewers.

## Important Files

- [README.md](/Users/zora/pitcher/SLUGGER-Pitching-Widget/README.md:1)
  - primary reviewer-facing setup and reproduction guide
- [data/README.md](/Users/zora/pitcher/SLUGGER-Pitching-Widget/data/README.md:1)
  - sample-data schema and privacy notes
- [python_app/app.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/app.py:1)
  - Dash entrypoint and top-level layout
- [python_app/config.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/config.py:1)
  - environment configuration
- [python_app/lib/api.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/lib/api.py:1)
  - live API clients plus data-source routing
- [python_app/lib/conditioning.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/lib/conditioning.py:1)
  - shared data-cleaning helpers
- [python_app/lib/sample_data.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/lib/sample_data.py:1)
  - offline reviewer-safe data provider
- [python_app/lib/cache.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/lib/cache.py:1)
  - in-memory cache for roster, stats, IDs, and pitch data
- [python_app/features/](/Users/zora/pitcher/SLUGGER-Pitching-Widget/python_app/features)
  - modular UI/visualization logic
- [scripts/smoke_test.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/scripts/smoke_test.py:1)
  - quick correctness check
- [scripts/generate_sample_outputs.py](/Users/zora/pitcher/SLUGGER-Pitching-Widget/scripts/generate_sample_outputs.py:1)
  - writes reviewer-safe sample outputs

## How To Update Or Extend The Project

- For API changes:
  - update `python_app/lib/api.py`
  - update `python_app/lib/conditioning.py` if schemas change
  - rerun `scripts/smoke_test.py`
- For UI changes:
  - keep new charts or cards inside `python_app/features/`
  - avoid moving data-fetch logic into Dash callbacks
- For sample-mode maintenance:
  - keep `data/sample/` aligned with the minimal columns required by the app

## Deployment Notes

- Render is the current deployment target.
- Health checks should use `/healthz`.
- Keep secrets only in the hosting platform environment, never in Git.
- If the live deployment URL changes, update both `README.md` and `DEPLOYMENT_README.md`.
