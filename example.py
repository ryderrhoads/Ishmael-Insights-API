#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from datetime import datetime

from dotenv import load_dotenv

from ishmael_insights_api import IshmaelInsightsAPI, IshmaelInsightsAPIError

load_dotenv("EXAMPLE.env")


def main() -> int:
    api_key = os.getenv("API_KEY", "pk_live...")
    base_url = os.getenv("BASE_URL", "https://ishmaelinsights.com")
    client = IshmaelInsightsAPI(api_key=api_key, base_url=base_url)

    today = datetime.now().date().isoformat()

    try:
        print("Auth check:")
        print(client.auth_check())

        print("\nPredictions query:")
        preds = client.get_predictions(
            time=int(time.time()),
            tag=["cbb"],
            tags_mode="any",
            limit=10,
        )
        print(preds)

        print("\nToday's CBB games:")
        games = client.get_games(
            league="cbb",
            game_date=today,
            timezone="America/Los_Angeles",
            limit=5,
        )
        print(games)

    except IshmaelInsightsAPIError as e:
        print(f"API error: {e} payload={e.payload}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
