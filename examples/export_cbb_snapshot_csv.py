#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ishmael_insights_api import IshmaelInsightsAPI, IshmaelInsightsAPIError

try:
    from dotenv import load_dotenv
except Exception:  # optional dependency
    load_dotenv = None


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    # Preserve first-seen field order while adding new keys encountered later.
    fieldnames: list[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if load_dotenv:
        load_dotenv("EXAMPLE.env")
    else:
        _load_env_file(Path("EXAMPLE.env"))

    api_key = os.getenv("API_KEY", "").strip()
    base_url = os.getenv("BASE_URL", "https://ishmaelinsights.com").strip()
    league = os.getenv("LEAGUE", "cbb").strip().lower()
    out_dir = Path(os.getenv("OUT_DIR", "exports"))

    if not api_key:
        print("Missing API_KEY. Set it in EXAMPLE.env or environment.")
        return 1

    client = IshmaelInsightsAPI(api_key=api_key, base_url=base_url)

    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    end_utc = start_utc + timedelta(days=1) - timedelta(seconds=1)

    try:
        print(f"Fetching all {league.upper()} teams...")
        teams = list(client.iter_teams(league=league))

        print(f"Fetching today's {league.upper()} games...")
        games = list(
            client.iter_games(
                league=league,
                start_date=start_utc,
                end_date=end_utc,
            )
        )

        print(f"Fetching latest {league.upper()} model predictions...")
        predictions = list(client.iter_predictions(time=int(time.time()), tag=league))

        today_condition_ids = {
            str(g.get("condition_id", "")).strip()
            for g in games
            if g.get("condition_id")
        }
        today_predictions = [
            p for p in predictions if str(p.get("condition_id", "")).strip() in today_condition_ids
        ]

        teams_csv = out_dir / f"{league}_teams.csv"
        games_csv = out_dir / f"{league}_games_today.csv"
        preds_csv = out_dir / f"{league}_predictions_latest.csv"
        today_preds_csv = out_dir / f"{league}_predictions_for_today_games.csv"

        _write_csv(teams_csv, teams)
        _write_csv(games_csv, games)
        _write_csv(preds_csv, predictions)
        _write_csv(today_preds_csv, today_predictions)

        print("Done:")
        print(f"- teams: {len(teams)} -> {teams_csv}")
        print(f"- games today: {len(games)} -> {games_csv}")
        print(f"- predictions (latest): {len(predictions)} -> {preds_csv}")
        print(f"- predictions (today's games): {len(today_predictions)} -> {today_preds_csv}")
        return 0

    except IshmaelInsightsAPIError as e:
        print(f"API error: {e} payload={e.payload}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
