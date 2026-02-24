from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

import requests

from .errors import IshmaelInsightsAPIError


DEFAULT_BASE_URL = "https://ishmaelinsights.com"


def _isoish(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _csv(values: str | Iterable[Any] | None) -> str | None:
    if values is None:
        return None
    if isinstance(values, str):
        v = values.strip()
        return v or None
    out = [str(v).strip() for v in values if str(v).strip()]
    return ",".join(out) if out else None


class IshmaelInsightsAPI:
    """Small Python client for Ishmael Insights public API."""

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
            "User-Agent": "ishmael-insights-api-python/0.1.0",
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

    def auth_check(self) -> dict[str, Any]:
        return self._request("POST", "/auth/check")

    def get_predictions(
        self,
        *,
        time: int | str | datetime,
        slug: str | None = None,
        condition_id: str | None = None,
        team_id: str | int | None = None,
        tag: str | Iterable[str] | None = None,
        tags_mode: str | None = None,
        cursor: str | None = None,
        limit: int | None = 50,
    ) -> dict[str, Any]:
        params = {
            "time": int(time.timestamp()) if isinstance(time, datetime) else time,
            "slug": slug,
            "condition_id": condition_id,
            "team_id": str(team_id) if team_id is not None else None,
            "tag": _csv(tag),
            "tags_mode": tags_mode,
            "cursor": cursor,
            "limit": limit,
        }
        return self._request("GET", "/predictions", params=params)

    def get_games(
        self,
        *,
        league: str,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        team_ids: str | Iterable[str | int] | None = None,
        limit: int | None = 50,
        min_volume: float | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "league": league,
            "start_date": _isoish(start_date),
            "end_date": _isoish(end_date),
            "team_ids": _csv(team_ids),
            "limit": limit,
            "min_volume": min_volume,
            "cursor": cursor,
        }
        return self._request("GET", "/games", params=params)

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

    def get_team(
        self,
        *,
        team_id: str | int | None = None,
        name: str | None = None,
        abbreviation: str | None = None,
    ) -> dict[str, Any]:
        if not any([team_id, name, abbreviation]):
            raise ValueError("Provide one of: team_id, name, abbreviation")
        params = {
            "team_id": str(team_id) if team_id is not None else None,
            "name": name,
            "abbreviation": abbreviation,
        }
        return self._request("GET", "/team", params=params)
