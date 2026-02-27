from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .errors import IshmaelInsightsAPIError


DEFAULT_BASE_URL = "https://ishmaelinsights.com"


def _isoish(value: str | int | float | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _unixish(value: int | float | str | datetime) -> int | float | str:
    if isinstance(value, datetime):
        return int(value.timestamp())
    return value


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    s = str(value).strip()
    if not s:
        raise ValueError("game_date cannot be empty")

    # Fast path for YYYY-MM-DD and ISO-like strings.
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return date.fromisoformat(s[:10])

    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid game_date: {value!r}") from exc


def _local_day_epoch_bounds(day: date, timezone_name: str | None) -> tuple[int, int]:
    tz = timezone_name or "UTC"
    try:
        zone = ZoneInfo(tz)
    except Exception:
        zone = ZoneInfo("UTC")

    start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=zone)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return int(start.timestamp()), int(end.timestamp())


def _csv(values: str | Iterable[Any] | None) -> str | None:
    if values is None:
        return None
    if isinstance(values, str):
        v = values.strip()
        return v or None
    out = [str(v).strip() for v in values if str(v).strip()]
    return ",".join(out) if out else None


class IshmaelInsightsAPI:
    """Python client for the Ishmael Insights public API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def api_root(self) -> str:
        if self.base_url.endswith("/api/v1"):
            return self.base_url
        return f"{self.base_url}/api/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "User-Agent": "ishmael-insights-api-python/0.2.4",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_root}/{path.lstrip('/')}"
        response = self.session.request(
            method,
            url,
            headers=self._headers(),
            params={k: v for k, v in (params or {}).items() if v is not None},
            json=json_body,
            timeout=self.timeout,
        )

        payload: dict[str, Any] | str | None = None
        message = response.reason
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = str(payload.get("error") or payload.get("message") or message)
        except Exception:
            payload = response.text
            if isinstance(payload, str) and payload.strip():
                message = payload[:200]

        if response.status_code >= 400:
            raise IshmaelInsightsAPIError(response.status_code, message, payload)

        if isinstance(payload, dict):
            return payload
        return {"ok": True, "raw": payload}

    def _iter_items(
        self,
        path: str,
        *,
        base_params: dict[str, Any],
        page_limit: int = 500,
        cursor: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        next_cursor = cursor
        while True:
            params = dict(base_params)
            params["limit"] = page_limit
            params["cursor"] = next_cursor
            payload = self._request("GET", path, params=params)
            items = payload.get("items")
            if not isinstance(items, list):
                return
            for item in items:
                if isinstance(item, dict):
                    yield item
                else:
                    yield {"value": item}
            next_cursor = payload.get("next_cursor")
            if not next_cursor:
                return

    def auth_check(self) -> dict[str, Any]:
        return self._request("POST", "/auth/check")

    def get_predictions(
        self,
        *,
        time: int | float | str | datetime,
        slug: str | None = None,
        condition_id: str | None = None,
        team_id: str | int | None = None,
        tag: str | Iterable[str] | None = None,
        tags_mode: str | None = None,
        cursor: str | None = None,
        limit: int | None = 50,
    ) -> dict[str, Any]:
        params = {
            "time": _unixish(time),
            "slug": slug,
            "condition_id": condition_id,
            "team_id": str(team_id) if team_id is not None else None,
            "tag": _csv(tag),
            "tags_mode": tags_mode,
            "cursor": cursor,
            "limit": limit,
        }
        return self._request("GET", "/predictions", params=params)

    def iter_predictions(
        self,
        *,
        time: int | float | str | datetime,
        slug: str | None = None,
        condition_id: str | None = None,
        team_id: str | int | None = None,
        tag: str | Iterable[str] | None = None,
        tags_mode: str | None = None,
        page_limit: int = 500,
        cursor: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        params = {
            "time": _unixish(time),
            "slug": slug,
            "condition_id": condition_id,
            "team_id": str(team_id) if team_id is not None else None,
            "tag": _csv(tag),
            "tags_mode": tags_mode,
        }
        return self._iter_items(
            "/predictions",
            base_params=params,
            page_limit=page_limit,
            cursor=cursor,
        )

    def get_predictions_history(
        self,
        *,
        condition_id: str,
        strategy_id: str | None = None,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        if not condition_id:
            raise ValueError("condition_id is required")
        params = {
            "condition_id": condition_id,
            "strategy_id": strategy_id,
            "outcome": outcome,
        }
        return self._request("GET", "/predictions-history", params=params)

    def get_price_history(
        self,
        *,
        condition_id: str,
    ) -> dict[str, Any]:
        if not condition_id:
            raise ValueError("condition_id is required")
        return self._request("GET", "/price-history", params={"condition_id": condition_id})

    def get_games(
        self,
        *,
        league: str,
        game_date: str | date | datetime | None = None,
        timezone: str | None = None,
        start_date: str | int | float | date | datetime | None = None,
        end_date: str | int | float | date | datetime | None = None,
        team_ids: str | Iterable[str | int] | None = None,
        limit: int | None = 50,
        min_volume: float | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        if game_date is None and (start_date is None or end_date is None):
            raise ValueError("Provide game_date OR both start_date and end_date")

        params = {
            "league": league,
            "game_date": _isoish(game_date) if game_date is not None else None,
            "timezone": timezone,
            "start_date": _isoish(start_date) if start_date is not None else None,
            "end_date": _isoish(end_date) if end_date is not None else None,
            "team_ids": _csv(team_ids),
            "limit": limit,
            "min_volume": min_volume,
            "cursor": cursor,
        }

        try:
            return self._request("GET", "/games", params=params)
        except IshmaelInsightsAPIError as exc:
            # Backward-compat fallback for older server deployments that don't
            # support `game_date` yet and require start/end timestamps.
            if (
                game_date is not None
                and start_date is None
                and end_date is None
                and exc.status_code == 400
                and "start_date and end_date" in str(exc.message).lower()
            ):
                day = _coerce_date(game_date)
                start_ts, end_ts = _local_day_epoch_bounds(day, timezone)
                fallback_params = {
                    **params,
                    "game_date": None,
                    "timezone": None,
                    "start_date": start_ts,
                    "end_date": end_ts,
                }
                return self._request("GET", "/games", params=fallback_params)
            raise

    def iter_games(
        self,
        *,
        league: str,
        game_date: str | date | datetime | None = None,
        timezone: str | None = None,
        start_date: str | int | float | date | datetime | None = None,
        end_date: str | int | float | date | datetime | None = None,
        team_ids: str | Iterable[str | int] | None = None,
        min_volume: float | None = None,
        page_limit: int = 500,
        cursor: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        if game_date is None and (start_date is None or end_date is None):
            raise ValueError("Provide game_date OR both start_date and end_date")

        next_cursor = cursor
        while True:
            payload = self.get_games(
                league=league,
                game_date=game_date,
                timezone=timezone,
                start_date=start_date,
                end_date=end_date,
                team_ids=team_ids,
                limit=page_limit,
                min_volume=min_volume,
                cursor=next_cursor,
            )
            items = payload.get("items")
            if not isinstance(items, list):
                return
            for item in items:
                if isinstance(item, dict):
                    yield item
                else:
                    yield {"value": item}
            next_cursor = payload.get("next_cursor")
            if not next_cursor:
                return

    def get_game(
        self,
        *,
        condition_id: str | None = None,
        league: str | None = None,
        game_date: str | int | float | date | datetime | None = None,
        team_a_id: int | str | None = None,
        team_b_id: int | str | None = None,
    ) -> dict[str, Any]:
        has_condition = bool(condition_id)
        has_composite = all(v is not None for v in (league, game_date, team_a_id, team_b_id))
        if not has_condition and not has_composite:
            raise ValueError(
                "Provide either condition_id OR all of league, game_date, team_a_id, team_b_id"
            )

        params = {
            "condition_id": condition_id,
            "league": league,
            "game_date": _isoish(game_date) if game_date is not None else None,
            "team_a_id": str(team_a_id) if team_a_id is not None else None,
            "team_b_id": str(team_b_id) if team_b_id is not None else None,
        }
        return self._request("GET", "/game", params=params)

    def get_teams(
        self,
        *,
        league: str,
        limit: int | None = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "league": league,
            "limit": limit,
            "cursor": cursor,
        }
        return self._request("GET", "/teams", params=params)

    def iter_teams(
        self,
        *,
        league: str,
        page_limit: int = 500,
        cursor: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        params = {"league": league}
        return self._iter_items(
            "/teams",
            base_params=params,
            page_limit=page_limit,
            cursor=cursor,
        )

    def get_team(
        self,
        *,
        team_id: str | int | None = None,
        name: str | None = None,
        abbreviation: str | None = None,
        league: str | None = None,
    ) -> dict[str, Any]:
        if not any([team_id, name, abbreviation]):
            raise ValueError("Provide one of: team_id, name, abbreviation")
        params = {
            "team_id": str(team_id) if team_id is not None else None,
            "name": name,
            "abbreviation": abbreviation,
            "league": league,
        }
        return self._request("GET", "/team", params=params)

    def get_markets(
        self,
        *,
        source: str | None = "all",
        status: str | None = None,
        q: str | None = None,
        search: str | None = None,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "source": source,
            "status": status,
            "q": q,
            "search": search,
            "limit": limit,
            "cursor": cursor,
        }
        return self._request("GET", "/markets", params=params)

    def iter_markets(
        self,
        *,
        source: str | None = "all",
        status: str | None = None,
        q: str | None = None,
        search: str | None = None,
        page_limit: int = 500,
        cursor: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        params = {
            "source": source,
            "status": status,
            "q": q,
            "search": search,
        }
        return self._iter_items(
            "/markets",
            base_params=params,
            page_limit=page_limit,
            cursor=cursor,
        )

    def get_market(
        self,
        *,
        source: str | None = None,
        condition_id: str | None = None,
        slug: str | None = None,
        ticker: str | None = None,
        polymarket_id: int | str | None = None,
    ) -> dict[str, Any]:
        if not any([condition_id, slug, ticker, polymarket_id is not None]):
            raise ValueError("Provide one of: condition_id, slug, ticker, polymarket_id")

        params = {
            "source": source,
            "condition_id": condition_id,
            "slug": slug,
            "ticker": ticker,
            "polymarket_id": str(polymarket_id) if polymarket_id is not None else None,
        }
        return self._request("GET", "/market", params=params)
