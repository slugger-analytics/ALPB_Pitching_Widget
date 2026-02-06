"""
ALPB Trackman API client.

Fetches pitcher info and pitch-by-pitch data from the ALPB Trackman API.
Equivalent to getALPBdata.R and getALPBpitches.R.
"""

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

ALPB_API_KEY = "IuHgm3smV65kbC6lMlMLz80DOeEkGSiV6USoQhvZ"
ALPB_BASE_URL = "https://1ywv9dczq5.execute-api.us-east-2.amazonaws.com/ALPBAPI"

# Reuse connections across API calls (major latency fix)
_session = requests.Session()
_session.headers.update({"x-api-key": ALPB_API_KEY})


def get_alpb_pitcher_info(fname, lname):
    """
    Look up a pitcher on the ALPB Trackman API by name.

    Returns a dict with 'player_id' and 'pitching_hand',
    or None if the player is not found or is not a pitcher.
    """
    query_name = f"{lname}, {fname}"
    url = f"{ALPB_BASE_URL}/players"
    params = {"player_name": query_name}

    try:
        res = _session.get(url, params=params)
        res.raise_for_status()
        parsed = res.json()

        data = parsed.get("data")
        if not data or not isinstance(data, list) or len(data) == 0:
            return None

        player = data[0]
        if player is not None and player.get("is_pitcher"):
            return {
                "player_id": player["player_id"],
                "pitching_hand": player.get("player_pitching_handedness", "Unknown"),
            }
    except Exception:
        pass

    return None


def _fetch_page(url, player_id, page):
    """Fetch a single page of pitch data."""
    try:
        res = _session.get(url, params={"pitcher_id": player_id, "page": page})
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception:
        pass
    return []


def get_alpb_pitches(player_id):
    """
    Retrieve all pitch-by-pitch data for a pitcher from the ALPB Trackman API.
    Handles pagination automatically with parallel page fetching.

    Returns a DataFrame with pitch data columns, or None if unavailable.
    """
    if not player_id:
        return None

    url = f"{ALPB_BASE_URL}/pitches"

    # First page (need it to discover total page count)
    try:
        res = _session.get(url, params={"pitcher_id": player_id, "page": 1})
        if res.status_code != 200:
            return None
        parsed = res.json()
    except Exception:
        return None

    data = parsed.get("data")
    if not data:
        return None

    all_data = list(data)
    total_pages = parsed.get("meta", {}).get("total", 1)

    # Fetch remaining pages in parallel
    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(_fetch_page, url, player_id, page): page
                for page in range(2, total_pages + 1)
            }
            for future in as_completed(futures):
                page_data = future.result()
                if page_data:
                    all_data.extend(page_data)

    df = pd.DataFrame(all_data)
    return df
