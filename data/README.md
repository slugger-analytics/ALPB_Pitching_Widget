# Data Guide

This repository does **not** publish private or proprietary ALPB source data.

## What is included publicly

- `data/sample/`
  - Small synthetic sample files
  - Safe to share publicly
  - Intended for smoke testing, demos, and reviewer setup

## What is not included publicly

- Full Pointstreak roster/stat payloads
- Full ALPB Trackman pitch-by-pitch data
- Any private API credentials

Those assets must be transferred privately or accessed through approved API keys.

## Reviewer workflow

For a public review, use the bundled sample mode:

```bash
cp .env.example .env
python -m python_app.app
```

The default `.env.example` sets `DATA_SOURCE=sample`, so no private data is required.

## Live data workflow

To reproduce the full private dashboard experience:

1. Copy `.env.example` to `.env`.
2. Set `DATA_SOURCE=live`.
3. Fill in:
   - `POINTSTREAK_API_KEY`
   - `ALPB_API_KEY`
4. Run the app or smoke-test scripts described in the main README.

## Sample file inventory

### `data/sample/pitchers.csv`

Expected columns:

- `playerid`
- `playerlinkid`
- `fname`
- `lname`
- `position`
- `height`
- `weight`
- `birthday`
- `bats`
- `throws`
- `hometown`
- `photo`
- `teamlinkid`
- `teamname`

### `data/sample/season_stats.csv`

Expected columns:

- `playerlinkid`
- `season`
- `team`
- `era`
- `whip`
- `ip`
- `so`
- `bb`
- `opp_avg`

### `data/sample/alpb_lookup.csv`

Expected columns:

- `fname`
- `lname`
- `player_id`
- `pitching_hand`

### `data/sample/pitches.csv`

Expected columns:

- `player_id`
- `game_date`
- `batter_side`
- `auto_pitch_type`
- `tagged_pitch_type`
- `rel_speed`
- `induced_vert_break`
- `horz_break`
- `plate_loc_side`
- `plate_loc_height`
- `balls`
- `strikes`

## Optional private snapshot location

If a future maintainer wants to work from secure local snapshots rather than live APIs, place those files under a local-only folder such as `data/private/` and keep that directory untracked.
