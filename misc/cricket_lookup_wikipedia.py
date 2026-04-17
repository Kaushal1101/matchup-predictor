#!/usr/bin/env python3

from __future__ import annotations

import csv
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "cricket-lookup/1.0 (educational script)"
}

CSV_PATH = Path("data/processed/players.csv")
BACKUP_PATH = Path("data/processed/players.csv.bak")
NAME_COLUMNS = ["unique_name", "name_x", "name_y"]

HANDEDNESS_PATTERNS = [
    re.compile(r"\bright[-\s]?handed\b", re.I),
    re.compile(r"\bleft[-\s]?handed\b", re.I),
]

BOWLING_PATTERNS = [
    re.compile(r"\bright[-\s]?arm\s+fast[-\s]?medium\b", re.I),
    re.compile(r"\bright[-\s]?arm\s+medium[-\s]?fast\b", re.I),
    re.compile(r"\bright[-\s]?arm\s+fast\b", re.I),
    re.compile(r"\bright[-\s]?arm\s+medium\b", re.I),
    re.compile(r"\bright[-\s]?arm\s+off[-\s]?break\b", re.I),
    re.compile(r"\bleft[-\s]?arm\s+fast[-\s]?medium\b", re.I),
    re.compile(r"\bleft[-\s]?arm\s+medium[-\s]?fast\b", re.I),
    re.compile(r"\bleft[-\s]?arm\s+fast\b", re.I),
    re.compile(r"\bleft[-\s]?arm\s+medium\b", re.I),
    re.compile(r"\bslow\s+left[-\s]?arm\s+orthodox\b", re.I),
    re.compile(r"\bleft[-\s]?arm\s+wrist[-\s]?spin\b", re.I),
    re.compile(r"\bleg[-\s]?break(?:\s+googly)?\b", re.I),
    re.compile(r"\blegbreak(?:\s+googly)?\b", re.I),
]


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_missing(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.lower() in {"nan", "none", "null", "na", "n/a"}


def canonical_handedness(text: str) -> str:
    t = normalize_spaces(text).lower()
    if "right" in t:
        return "Right"
    if "left" in t:
        return "Left"
    return "Unknown"


def canonical_bowling(text: str) -> str:
    t = normalize_spaces(text)
    replacements = {
        "Right arm": "Right-arm",
        "Left arm": "Left-arm",
        "right arm": "Right-arm",
        "left arm": "Left-arm",
        "Right handed": "Right-handed",
        "Left handed": "Left-handed",
        "right handed": "Right-handed",
        "left handed": "Left-handed",
        "fast medium": "fast-medium",
        "medium fast": "medium-fast",
        "off break": "off-break",
        "wrist spin": "wrist-spin",
        "leg break": "legbreak",
    }
    for old, new in replacements.items():
        t = t.replace(old, new)
    return normalize_spaces(t)


def fetch_html(url: str, session: requests.Session) -> str:
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.text


def page_exists(html: str) -> bool:
    lowered = html.lower()
    return (
        "wikipedia does not have an article with this exact name" not in lowered
        and 'class="noarticletext"' not in lowered
        and "may refer to:" not in lowered
    )


def direct_wikipedia_url(player_name: str) -> str:
    title = player_name.strip().replace(" ", "_")
    return f"https://en.wikipedia.org/wiki/{quote(title, safe='_()')}"


def search_wikipedia_via_browser(
    player_name: str,
    session: requests.Session,
) -> Optional[str]:
    search_url = f"https://en.wikipedia.org/w/index.php?search={quote(player_name)}"
    r = session.get(search_url, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    if "/wiki/" in r.url and "search=" not in r.url:
        return r.url

    first = soup.select_one(".mw-search-result-heading a")
    if first and first.get("href"):
        href = first["href"]
        if href.startswith("/wiki/"):
            return "https://en.wikipedia.org" + href

    return None


def extract_from_text(text: str) -> Tuple[str, str]:
    batting = "Unknown"
    bowling = "Unknown"

    for pat in HANDEDNESS_PATTERNS:
        m = pat.search(text)
        if m:
            batting = canonical_handedness(m.group(0))
            break

    for pat in BOWLING_PATTERNS:
        m = pat.search(text)
        if m:
            bowling = canonical_bowling(m.group(0))
            break

    return batting, bowling


def extract_from_infobox(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    infobox = soup.select_one("table.infobox")

    if infobox is None:
        page_text = normalize_spaces(soup.get_text(" ", strip=True))
        return extract_from_text(page_text)

    batting_value = None
    bowling_value = None

    for row in infobox.select("tr"):
        th = row.find("th")
        td = row.find("td")
        if not th or not td:
            continue

        key = normalize_spaces(th.get_text(" ", strip=True)).lower()
        value = normalize_spaces(td.get_text(" ", strip=True))

        if key == "batting" and batting_value is None:
            batting_value = value
        elif key == "bowling" and bowling_value is None:
            bowling_value = value

    batting = canonical_handedness(batting_value) if batting_value else "Unknown"
    bowling = canonical_bowling(bowling_value) if bowling_value else "Unknown"

    if batting == "Unknown" or bowling == "Unknown":
        page_text = normalize_spaces(soup.get_text(" ", strip=True))
        fb_batting, fb_bowling = extract_from_text(page_text)
        if batting == "Unknown":
            batting = fb_batting
        if bowling == "Unknown":
            bowling = fb_bowling

    return batting, bowling


def scrape_player_name(player_name: str, session: requests.Session) -> Optional[Tuple[str, str]]:
    try:
        wiki_url = direct_wikipedia_url(player_name)
        html = fetch_html(wiki_url, session)

        if not page_exists(html):
            fallback_url = search_wikipedia_via_browser(player_name, session)
            if not fallback_url:
                return None
            html = fetch_html(fallback_url, session)

        batting, bowling = extract_from_infobox(html)

        if batting == "Unknown" and bowling == "Unknown":
            return None

        return batting, bowling

    except Exception:
        return None


def candidate_names(row: dict) -> list[str]:
    names: list[str] = []
    for col in NAME_COLUMNS:
        value = row.get(col)
        if is_missing(value):
            continue
        cleaned = normalize_spaces(str(value))
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names


def load_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def write_rows(csv_path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if not CSV_PATH.exists():
        print(f"CSV file not found: {CSV_PATH}", file=sys.stderr)
        return 1

    try:
        rows, fieldnames = load_rows(CSV_PATH)
    except Exception as e:
        print(f"Failed to read CSV: {e}", file=sys.stderr)
        return 1

    if "batting" not in fieldnames:
        fieldnames.append("batting")
    if "bowling" not in fieldnames:
        fieldnames.append("bowling")

    try:
        shutil.copy2(CSV_PATH, BACKUP_PATH)
        print(f"Backup created at {BACKUP_PATH}")
    except Exception as e:
        print(f"Failed to create backup: {e}", file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(HEADERS)

    total = len(rows)
    matched = 0
    skipped = 0
    started = time.perf_counter()

    for i, row in enumerate(rows, start=1):
        names_to_try = candidate_names(row)
        result = None

        for name in names_to_try:
            result = scrape_player_name(name, session)
            if result is not None:
                break

        if result is not None:
            batting, bowling = result
            row["batting"] = batting
            row["bowling"] = bowling
            matched += 1
            print(f"[{i}/{total}] matched -> batting={batting}, bowling={bowling}")
        else:
            row["batting"] = row.get("batting", "") or ""
            row["bowling"] = row.get("bowling", "") or ""
            skipped += 1
            print(f"[{i}/{total}] skipped")

    try:
        write_rows(CSV_PATH, rows, fieldnames)
    except Exception as e:
        print(f"Failed to write CSV: {e}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - started
    print()
    print(f"Done. Updated {CSV_PATH}")
    print(f"Matched: {matched}")
    print(f"Skipped: {skipped}")
    print(f"Runtime: {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())