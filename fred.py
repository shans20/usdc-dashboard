"""
FRED client — fetch current Treasury yield for reserve income estimation.
Requires free API key from https://fred.stlouisfed.org/docs/api/fred/
"""

import requests
from config import FRED_API_KEY, FRED_SERIES_ID

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_treasury_yield():
    """
    Fetch the latest 3-month T-bill rate from FRED.
    Circle holds reserves primarily in short-duration Treasuries and repos,
    so the 3-month T-bill is the best proxy for their reserve yield.
    """
    if not FRED_API_KEY:
        return {"yield_pct": None, "error": "No FRED_API_KEY set. Get one free at https://fred.stlouisfed.org/docs/api/fred/"}

    params = {
        "series_id": FRED_SERIES_ID,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5,  # Get last 5 observations to handle missing data days
    }

    resp = requests.get(FRED_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    observations = data.get("observations", [])
    for obs in observations:
        val = obs.get("value", ".")
        if val != ".":  # FRED uses "." for missing data
            return {
                "yield_pct": float(val),
                "date": obs["date"],
                "series": FRED_SERIES_ID,
                "description": "3-Month Treasury Bill Rate",
            }

    return {"yield_pct": None, "error": "No recent data available"}


if __name__ == "__main__":
    data = get_treasury_yield()
    if data.get("yield_pct") is not None:
        print(f"\n3-Month T-Bill Rate: {data['yield_pct']:.2f}%")
        print(f"As of: {data['date']}")
    else:
        print(f"Error: {data.get('error')}")
