"""
Monthly query quota tracker for the Brave Search API free tier.

Usage is persisted in a JSON file so it survives app restarts.
The counter resets automatically at the start of each calendar month.

Free tier: ~1,000 queries/month.
Hard stop:  950 queries/month (MONTHLY_QUERY_LIMIT in config.py).
"""

import json
import os
from datetime import datetime
from pathlib import Path

from config import MONTHLY_QUERY_LIMIT

_QUOTA_FILE = Path("./storage/quota.json")


def _load() -> dict:
    """Load quota state from disk, or return a fresh state."""
    if _QUOTA_FILE.exists():
        try:
            data = json.loads(_QUOTA_FILE.read_text())
            # Reset if we've rolled into a new month
            now = datetime.now()
            if data.get("year") != now.year or data.get("month") != now.month:
                return _fresh(now)
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    return _fresh(datetime.now())


def _fresh(now: datetime) -> dict:
    return {"year": now.year, "month": now.month, "used": 0}


def _save(state: dict) -> None:
    _QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _QUOTA_FILE.write_text(json.dumps(state))


def get_usage() -> dict:
    """
    Return current quota state.

    Returns a dict with keys:
        used      — queries used this month
        limit     — hard stop (MONTHLY_QUERY_LIMIT)
        remaining — queries still available
        month     — current month (1-12)
        year      — current year
    """
    state = _load()
    return {
        "used": state["used"],
        "limit": MONTHLY_QUERY_LIMIT,
        "remaining": max(0, MONTHLY_QUERY_LIMIT - state["used"]),
        "month": state["month"],
        "year": state["year"],
    }


def check_quota(n: int) -> None:
    """
    Raise a RuntimeError if running *n* queries would exceed the monthly limit.

    Call this before starting a crawl batch.
    """
    state = _load()
    remaining = MONTHLY_QUERY_LIMIT - state["used"]
    if n > remaining:
        raise RuntimeError(
            f"Monthly quota would be exceeded: {n} companies requested but only "
            f"{remaining} queries remain this month (limit: {MONTHLY_QUERY_LIMIT}). "
            f"Upload a smaller batch or wait until next month."
        )


def record_queries(n: int) -> None:
    """
    Increment the used-query counter by *n* after a successful search batch.
    """
    state = _load()
    state["used"] += n
    _save(state)
