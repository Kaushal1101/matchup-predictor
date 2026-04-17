#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
import time
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup

WIKI_API = "https://en.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "cricket-lookup/1.0 (educational script)"
}

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

def wiki_search_title(player_name: str, session: requests.Session, debug: bool = False) -> Optional[str]:
    queries = [
        player_name,
        f"{player_name} cricketer",
    ]

    for query in queries:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
        }
        r = session.get(WIKI_API, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        results = data.get("query", {}).get("search", [])
        if debug:
            print(f"[debug] query={query!r} results={[x.get('title') for x in results[:5]]}")

        if not results:
            continue

        lowered_name = player_name.strip().lower()

        for item in results:
            title = (item.get("title") or "").strip()
            if title.lower() == lowered_name:
                return title

        first_title = (results[0].get("title") or "").strip()
        if first_title:
            return first_title

    return None

def fetch_parsed_html(title: str, session: requests.Session) -> str:
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "utf8": 1,
    }
    r = session.get(WIKI_API, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    if "error" in data:
        raise RuntimeError(f"Wikipedia parse error: {data['error']}")

    return data["parse"]["text"]["*"]

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

def extract_from_infobox(html: str, debug: bool = False) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    infobox = soup.select_one("table.infobox")

    if infobox is None:
        if debug:
            print("[debug] No infobox found, falling back to page text")
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

        if debug:
            print(f"[debug] infobox row: {key} -> {value}")

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

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("player_name")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(HEADERS)

    api_calls = 0
    pages_visited = 0
    started = time.perf_counter()

    try:
        title = wiki_search_title(args.player_name, session, debug=args.debug)
        api_calls += 1

        if not title:
            elapsed = time.perf_counter() - started
            print("=== RESULT ===")
            print(f"Resolved player   : {args.player_name}")
            print("Batting hand      : Unknown")
            print("Bowling style     : Unknown")
            print(f"Runtime (seconds) : {elapsed:.2f}")
            print(f"API calls         : {api_calls}")
            print(f"Pages visited     : {pages_visited}")
            print("Notes             : No Wikipedia result found.")
            return 0

        if args.debug:
            print(f"[debug] Selected title: {title}")

        html = fetch_parsed_html(title, session)
        api_calls += 1
        pages_visited += 1

        batting, bowling = extract_from_infobox(html, debug=args.debug)
        elapsed = time.perf_counter() - started

        page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

        print("=== RESULT ===")
        print(f"Resolved player   : {title}")
        print(f"Batting hand      : {batting}")
        print(f"Bowling style     : {bowling}")
        print(f"Runtime (seconds) : {elapsed:.2f}")
        print(f"API calls         : {api_calls}")
        print(f"Pages visited     : {pages_visited}")
        print(f"Source            : {page_url}")
        return 0

    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())