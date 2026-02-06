"""
ALPB Trackman API client.

Fetches pitcher info and pitch-by-pitch data from the ALPB Trackman API.
Equivalent to getALPBdata.R and getALPBpitches.R.
"""

import requests
import pandas as pd

ALPB_API_KEY = "IuHgm3smV65kbC6lMlMLz80DOeEkGSiV6USoQhvZ"
ALPB_BASE_URL = "https://1ywv9dczq5.execute-api.us-east-2.amazonaws.com/ALPBAPI"


def get_alpb_pitcher_info(fname, lname):
    """
    Look up a pitcher on the ALPB Trackman API by name.

    Returns a dict with 'player_id' and 'pitching_hand',
    or None if the player is not found or is not a pitcher.
    """
    query_name = f"{lname}, {fname}"
    url = f"{ALPB_BASE_URL}/players"
    headers = {"x-api-key": ALPB_API_KEY}
    params = {"player_name": query_name}

    try:
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()
        parsed = res.json()

        player = parsed.get("data", [None])[0]
        if player is not None and player.get("is_pitcher"):
            return {
                "player_id": player["player_id"],
                "pitching_hand": player.get("player_pitching_handedness", "Unknown"),
            }
    except Exception:
        pass

    return None


def get_alpb_pitches(player_id):
    """
    Retrieve all pitch-by-pitch data for a pitcher from the ALPB Trackman API.
    Handles pagination automatically.

    Returns a DataFrame with pitch data columns, or None if unavailable.
    """
    if not player_id:
        return None

    url = f"{ALPB_BASE_URL}/pitches"
    headers = {"x-api-key": ALPB_API_KEY}

    # First page
    try:
        res = requests.get(url, headers=headers, params={"pitcher_id": player_id, "page": 1})
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

    # Remaining pages
    for page in range(2, total_pages + 1):
        try:
            res = requests.get(
                url,
                headers=headers,
                params={"pitcher_id": player_id, "page": page},
            )
            if res.status_code == 200:
                page_data = res.json().get("data", [])
                all_data.extend(page_data)
        except Exception:
            continue

    df = pd.DataFrame(all_data)
    return df
