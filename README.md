# Ishmael Insights API (Python)

Small Python SDK for the Ishmael Insights public API.

## Install

```bash
pip install -e .
```

## Quickstart

```python
from ishmael_insights_api import IshmaelInsightsAPI

client = IshmaelInsightsAPI(api_key="pk_live_...")

auth = client.auth_check()
print(auth)

preds = client.get_predictions(
    time=1700000000,
    tag=["ncaab", "basketball"],
    tags_mode="all",
    limit=50,
)
print(preds.get("count"), "rows")
```

## Endpoints wrapped

- `POST /api/v1/auth/check` → `auth_check()`
- `GET /api/v1/predictions` → `get_predictions(...)`
- `GET /api/v1/games` → `get_games(...)`
- `GET /api/v1/teams` → `get_teams(...)`
- `GET /api/v1/team` → `get_team(...)`

> Note: games/teams/team methods are included so this package is ready once those endpoints are live.

## Dev

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python example.py
```
