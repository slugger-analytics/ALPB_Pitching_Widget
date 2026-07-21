"""
Diagnostic test for the 9 iScore pitchers who fail ALPB name matching.

Run with:
    python -m pytest tests/test_unmatched_pitchers.py -v -s

For each unmatched player the test:
  1. Queries the ALPB /players API with the raw iScore name.
  2. Tries common name variants (first-initial, nickname, ASCII fold, etc.)
  3. Prints what the API actually returns so we can spot the correct spelling.
  4. Passes if *any* variant finds a pitcher — failure means we need a manual alias.
"""

from __future__ import annotations

import re
import unicodedata

import pytest
import requests

from python_app.config import ALPB_API_KEY, ALPB_BASE_URL

# ---------------------------------------------------------------------------
# Players that the coverage test showed as unmatched (iScore name → team)
# ---------------------------------------------------------------------------
UNMATCHED = [
    ("Dylan",    "Banner",          "Gastonia Ghost Peppers"),
    ("Fin",      "Del Bonta-Smith", "High Point Rockers"),
    ("Fransisco","Mateo",           "Charleston Dirty Birds"),
    ("Issac",    "Fix",             "Southern Maryland Blue Crabs"),
    ("J.C.",     "Kiss",            "High Point Rockers"),
    ("JP",       "Massey",          "Southern Maryland Blue Crabs"),
    ("Joe",      "Testa",           "High Point Rockers"),
    ("Josimar",  "Cousins",         "Charleston Dirty Birds"),
    ("Thomas",   "Kane",            "Hagerstown Flying Boxcars"),
]

# ---------------------------------------------------------------------------
# Helpers (mirrors logic in api.py so we can test independently)
# ---------------------------------------------------------------------------
_ALPB_SESSION = requests.Session()
_ALPB_SESSION.headers["x-api-key"] = ALPB_API_KEY


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", _ascii(s).lower())).strip()


def _query(q: str) -> list[dict]:
    try:
        r = _ALPB_SESSION.get(f"{ALPB_BASE_URL}/players", params={"player_name": q}, timeout=10)
        r.raise_for_status()
        return r.json().get("data") or []
    except Exception as exc:
        print(f"    [API error for '{q}': {exc}]")
        return []


def _name_variants(fname: str, lname: str) -> list[tuple[str, str]]:
    """Return (query_string, description) pairs to try."""
    variants: list[tuple[str, str]] = []

    def _add(q, desc):
        variants.append((q.strip(), desc))

    # Standard "Last, First"
    _add(f"{lname}, {fname}", "raw")
    # ASCII-folded
    _add(f"{_ascii(lname)}, {_ascii(fname)}", "ascii-fold")
    # First initial only
    _add(f"{lname}, {fname[0]}.", "first-initial")
    _add(f"{_ascii(lname)}, {fname[0]}.", "ascii first-initial")
    # Hyphen → space in last name
    if "-" in lname:
        no_hyph = lname.replace("-", " ")
        _add(f"{no_hyph}, {fname}", "no-hyphen")
        _add(f"{no_hyph}", "last-only no-hyphen")
    # Last name only (broad search)
    _add(lname, "last-only")
    _add(_ascii(lname), "last-only ascii")
    # Dotless initials (J.C. → JC)
    fname_dotless = fname.replace(".", "")
    if fname_dotless != fname:
        _add(f"{lname}, {fname_dotless}", "dotless-initials")
    # Common misspellings
    if fname.lower() == "fransisco":
        _add(f"{lname}, Francisco", "Francisco spelling")

    return variants


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fname,lname,team", UNMATCHED)
def test_find_alpb_match(fname: str, lname: str, team: str, capsys):
    """Try every name variant; pass if any returns a pitcher record."""
    print(f"\n{'='*60}")
    print(f"Player : {fname} {lname}  ({team})")
    print(f"{'='*60}")

    found_pitcher: dict | None = None
    winning_query: str = ""

    for query, desc in _name_variants(fname, lname):
        results = _query(query)
        pitchers = [p for p in results if p.get("is_pitcher")]
        non_pitchers = [p for p in results if not p.get("is_pitcher")]

        if results:
            print(f"  [{desc}] query='{query}'")
            for p in results:
                pid    = p.get("player_id", "?")
                pname  = (
                    p.get("player_name")
                    or f"{p.get('player_first_name','')} {p.get('player_last_name','')}".strip()
                )
                hand   = p.get("player_pitching_handedness", "?")
                flag   = " <-- PITCHER" if p.get("is_pitcher") else ""
                print(f"    id={pid}  name='{pname}'  hand={hand}{flag}")

        if pitchers and not found_pitcher:
            found_pitcher = pitchers[0]
            winning_query = f"{desc}: '{query}'"

    if found_pitcher:
        pname = (
            found_pitcher.get("player_name")
            or f"{found_pitcher.get('player_first_name','')} {found_pitcher.get('player_last_name','')}".strip()
        )
        print(f"\n  MATCH via {winning_query}")
        print(f"  Suggested alias: '{fname} {lname}' -> '{pname}'")
        print(f"  player_id: {found_pitcher.get('player_id')}")
    else:
        print(f"\n  NO MATCH FOUND — may need a manual alias entry")

    # The test fails only if nothing was found at all, so we see all output first.
    assert found_pitcher is not None, (
        f"Could not find any ALPB pitcher record for '{fname} {lname}' ({team}). "
        "Add a manual name alias in api.py."
    )
