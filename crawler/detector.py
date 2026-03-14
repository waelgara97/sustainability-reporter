"""Score links to decide if they are likely sustainability reports."""

import re

from config import SCORE_THRESHOLD


def score_link(url: str, anchor_text: str) -> int:
    """
    Return an integer score. Higher = more likely to be a sustainability report.
    The threshold for "good enough" is set in config.py (default: 2).
    """
    url = (url or "").lower()
    anchor = (anchor_text or "").lower()
    score = 0

    # URL rules
    if "sustainability" in url:
        score += 3
    if "esg" in url:
        score += 3
    if "csr" in url:
        score += 2
    if "responsibility" in url:
        score += 2
    if "climate" in url:
        score += 1
    if "environment" in url:
        score += 1
    if url.rstrip("/").endswith(".pdf"):
        score += 2
    if re.search(r"\b(201[89]|202[0-5])\b", url):
        score += 1
    if "annual-report" in url:
        score += 1

    # Anchor text rules
    if "sustainability report" in anchor:
        score += 3
    if "annual report" in anchor:
        score += 1

    return score


def passes_threshold(url: str, anchor_text: str) -> bool:
    """True if score_link meets or exceeds SCORE_THRESHOLD."""
    return score_link(url, anchor_text) >= SCORE_THRESHOLD
