# Ishmael Insights API (Python)

Python SDK for the Ishmael Insights public API (`/api/v1`).

## Install

Local editable install (for development in this repo):

```bash
pip install -e .
```

Install in another project directly from GitHub:

```bash
pip install "ishmael-insights-api @ git+https://github.com/ryderrhoads/Ishmael-Insights-API.git@main"
```

Pin to a tag/commit (recommended for production):

```bash
pip install "ishmael-insights-api @ git+https://github.com/ryderrhoads/Ishmael-Insights-API.git@v0.2.2"
# or pin to an exact commit
pip install "ishmael-insights-api @ git+https://github.com/ryderrhoads/Ishmael-Insights-API.git@<commit_sha>"
```

`requirements.txt` example:

```txt
ishmael-insights-api @ git+https://github.com/ryderrhoads/Ishmael-Insights-API.git@main
```

## Quickstart

```python
from ishmael_insights_api import IshmaelInsightsAPI

client = IshmaelInsightsAPI(api_key="pk_live_...")

auth = client.auth_check()
print(auth)

preds = client.get_predictions(
    time=1700000000,
    tag=["cbb"],
    tags_mode="any",
    limit=50,
)
print(preds.get("count"), "rows")

# Date-based games query (recommended for "today" workflows)
games = client.get_games(
    league="cbb",
    game_date="2026-02-24",
    timezone="America/Los_Angeles",
    limit=200,
)
print(games.get("count"), "games")
```

## Endpoints wrapped

- `POST /api/v1/auth/check` → `auth_check()`
- `GET /api/v1/predictions` → `get_predictions(...)`, `iter_predictions(...)`
- `GET /api/v1/games` → `get_games(...)`, `iter_games(...)`
- `GET /api/v1/game` → `get_game(...)`
- `GET /api/v1/teams` → `get_teams(...)`, `iter_teams(...)`
- `GET /api/v1/team` → `get_team(...)`

`get_games(...)` / `iter_games(...)` support two query modes:

1. **Date mode (recommended):**
   - `league`, `game_date`
   - optional `timezone` (IANA, e.g. `America/Los_Angeles`)
2. **Time-range mode (legacy/back-compat):**
   - `league`, `start_date`, `end_date`

## CBB CSV export sample

One script fetches all CBB teams, today's CBB games, and latest CBB model predictions, then exports CSVs:

```bash
python examples/export_cbb_snapshot_csv.py
```

Output files (default `exports/`):

- `cbb_teams.csv`
- `cbb_games_today.csv`
- `cbb_predictions_latest.csv`
- `cbb_predictions_for_today_games.csv` (queried directly by each exported game `condition_id`)

You can override via env vars:

- `API_KEY`
- `BASE_URL` (default `https://ishmaelinsights.com`)
- `LEAGUE` (default `cbb`)
- `OUT_DIR` (default `exports`)
- `TIMEZONE` (default `America/Los_Angeles`)
- `TARGET_DATE` / `DATE` (`YYYY-MM-DD`, default = current date in `TIMEZONE`)

The exporter uses **local-day filtering** (with timezone) to avoid UTC day-boundary drift pulling yesterday/tomorrow games.

## Dev

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python example.py
python examples/export_cbb_snapshot_csv.py
```
