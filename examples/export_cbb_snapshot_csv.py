#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ishmael_insights_api import IshmaelInsightsAPI, IshmaelInsightsAPIError

try:
    from dotenv import load_dotenv
except Exception:  # optional dependency
    load_dotenv = None


_SLUG_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})$")


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


def _resolve_timezone() -> ZoneInfo:
    tz_name = os.getenv("TIMEZONE", "America/Los_Angeles").strip() or "America/Los_Angeles"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        print(f"Warning: invalid TIMEZONE={tz_name!r}. Falling back to America/Los_Angeles")
        return ZoneInfo("America/Los_Angeles")


def _resolve_target_date(tz: ZoneInfo) -> date:
    raw = (os.getenv("TARGET_DATE") or os.getenv("DATE") or "").strip()
    if raw:
        try:
            return date.fromisoformat(raw)
        except Exception:
            print(f"Warning: invalid TARGET_DATE/DATE={raw!r}. Falling back to current date in {tz.key}.")
    return datetime.now(tz).date()


def _slug_date(slug: str | None) -> str | None:
    s = str(slug or "").strip()
    if not s:
        return None
    m = _SLUG_DATE_RE.search(s)
    return m.group(1) if m else None


def _game_is_on_target_day(game: dict, *, target_date_iso: str, tz: ZoneInfo) -> bool:
    # Primary: game_time interpreted in requested timezone.
    gt = game.get("game_time")
    if gt is not None:
        try:
            local_day = datetime.fromtimestamp(int(gt), tz=timezone.utc).astimezone(tz).date().isoformat()
            if local_day == target_date_iso:
                return True
        except Exception:
            pass

    # Fallback: some docs have mismatched game_time; slug usually carries YYYY-MM-DD.
    return _slug_date(game.get("slug")) == target_date_iso


def _fetch_predictions_for_condition_ids(
    client: IshmaelInsightsAPI,
    *,
    decision_time: int,
    condition_ids: set[str],
) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for cid in sorted(c for c in condition_ids if c):
        payload = client.get_predictions(time=decision_time, condition_id=cid, limit=100)
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            key = (str(item.get("condition_id") or ""), str(item.get("outcome") or ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(item)

    return out


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

    tz = _resolve_timezone()
    target_day = _resolve_target_date(tz)
    target_day_iso = target_day.isoformat()

    # Wide query window + strict local-day filtering:
    # catches normal rows by game_time and outliers where game_time can drift.
    start_local = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)
    end_local = datetime(target_day.year, target_day.month, target_day.day, 23, 59, 59, tzinfo=tz)
    query_start = start_local - timedelta(hours=24)
    query_end = end_local + timedelta(hours=24)

    client = IshmaelInsightsAPI(api_key=api_key, base_url=base_url)

    try:
        print(f"Timezone: {tz.key}")
        print(f"Target date: {target_day_iso}")
        print(
            "Game query window (epoch): "
            f"{int(query_start.timestamp())} -> {int(query_end.timestamp())}"
        )

        print(f"Fetching all {league.upper()} teams...")
        teams = list(client.iter_teams(league=league))

        print(f"Fetching {league.upper()} games near target day...")
        raw_games = list(
            client.iter_games(
                league=league,
                start_date=int(query_start.timestamp()),
                end_date=int(query_end.timestamp()),
            )
        )

        games = [
            g
            for g in raw_games
            if _game_is_on_target_day(g, target_date_iso=target_day_iso, tz=tz)
        ]

        # Deduplicate by condition_id (stable if same row appears more than once).
        by_cid: dict[str, dict] = {}
        for g in games:
            cid = str(g.get("condition_id") or "").strip()
            if cid:
                by_cid[cid] = g
        games = list(by_cid.values()) if by_cid else games

        decision_time = int(time.time())

        print(f"Fetching latest {league.upper()} model predictions (tag-scoped)...")
        predictions = list(client.iter_predictions(time=decision_time, tag=league))

        today_condition_ids = {
            str(g.get("condition_id", "")).strip()
            for g in games
            if g.get("condition_id")
        }

        print("Fetching predictions specifically for today's game condition_ids...")
        today_predictions = _fetch_predictions_for_condition_ids(
            client,
            decision_time=decision_time,
            condition_ids=today_condition_ids,
        )

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
        print(f"- games on {target_day_iso}: {len(games)} -> {games_csv}")
        print(f"- predictions (latest): {len(predictions)} -> {preds_csv}")
        print(f"- predictions (target day's games): {len(today_predictions)} -> {today_preds_csv}")
        return 0

    except IshmaelInsightsAPIError as e:
        print(f"API error: {e} payload={e.payload}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
