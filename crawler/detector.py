"""Score links to decide if they are likely sustainability reports."""

import re

from config import CURRENT_YEAR, SCORE_THRESHOLD

_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
_MIN_YEAR = 2015


def extract_publication_year(url: str, text_snippet: str = "") -> int | None:
    """
    Infer publication year from URL first, then from text_snippet.
    Valid years: 2015 <= year <= CURRENT_YEAR. If multiple valid years, return max().
    Returns None if none valid.
    """
    def valid_years(s: str) -> list[int]:
        if not s:
            return []
        years = [int(m) for m in _YEAR_PATTERN.findall(s)]
        return [y for y in years if _MIN_YEAR <= y <= CURRENT_YEAR]

    from_url = valid_years(url or "")
    if from_url:
        return max(from_url)
    from_snippet = valid_years(text_snippet or "")
    if from_snippet:
        return max(from_snippet)
    return None


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
    # Match any year from 2018 up to and including the current year
    earliest_year = 2018
    year_pattern = "|".join(str(y) for y in range(earliest_year, CURRENT_YEAR + 1))
    if re.search(rf"\b({year_pattern})\b", url):
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
