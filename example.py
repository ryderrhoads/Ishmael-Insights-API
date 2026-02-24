#!/usr/bin/env python3
import os
import time

from dotenv import load_dotenv

from ishmael_insights_api import IshmaelInsightsAPI, IshmaelInsightsAPIError

load_dotenv("EXAMPLE.env")


def main() -> int:
    api_key = os.getenv("API_KEY", "pk_live...")
    base_url = os.getenv("BASE_URL", "https://ishmaelinsights.com")
    client = IshmaelInsightsAPI(api_key=api_key, base_url=base_url)

    try:
        print("Auth check:")
        print(client.auth_check())

        print("\nPredictions query:")
        resp = client.get_predictions(
            time=int(time.time()),
            tag=["ncaab", "basketball"],
            tags_mode="all",
            limit=50,
        )
        print(resp)
    except IshmaelInsightsAPIError as e:
        print(f"API error: {e} payload={e.payload}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
