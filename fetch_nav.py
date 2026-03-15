"""
Fetch job vacancy data from NAV's pam-stilling-feed API.

Paginates through the public job ads feed, extracts STYRK-08 codes from each
vacancy, and aggregates the number of active ads per code at both 4-digit
and 2-digit levels.

Saves results to nav_data.json keyed by STYRK-08 code.

Usage:
    uv run python fetch_nav.py
    uv run python fetch_nav.py --force
    uv run python fetch_nav.py --max-pages 50
"""

import argparse
import json
import os
import time

import httpx

TOKEN_URL = "https://pam-stilling-feed.nav.no/api/publicToken"
FEED_URL = "https://pam-stilling-feed.nav.no/api/v1/feed"
OUTPUT_FILE = "nav_data.json"
REQUEST_TIMEOUT = 30
PAGE_DELAY = 0.1


def get_token(client):
    """Fetch a public access token from the NAV API."""
    response = client.get(TOKEN_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text.strip().strip('"')


def fetch_feed_page(client, url, token):
    """Fetch a single page of the job ads feed. Returns the parsed JSON."""
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def extract_styrk_codes(vacancy):
    """Extract 4-digit STYRK-08 codes from a vacancy's categoryList."""
    codes = set()
    category_list = vacancy.get("categoryList", [])
    for cat in category_list:
        cat_type = cat.get("categoryType", "")
        if "STYRK" in cat_type.upper():
            code = cat.get("code", "")
            # Keep only valid 4-digit STYRK codes
            if code and len(code) == 4 and code.isdigit():
                codes.add(code)
    return codes


def fetch_vacancies(client, max_pages):
    """Paginate through the feed and collect STYRK code counts."""
    print("Fetching public token...")
    token = get_token(client)

    counts_4digit = {}
    total_ads = 0
    total_with_styrk = 0
    page = 0
    next_url = FEED_URL

    while next_url and page < max_pages:
        try:
            data = fetch_feed_page(client, next_url, token)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403) and page > 0:
                # Token may have expired — retry once with a fresh token
                print("  Token expired, refreshing...")
                token = get_token(client)
                data = fetch_feed_page(client, next_url, token)
            else:
                raise

        page += 1

        # The feed returns items under 'content' or as a list
        items = data.get("content", data.get("items", []))
        if isinstance(data, list):
            items = data

        if not items:
            break

        for vacancy in items:
            total_ads += 1
            codes = extract_styrk_codes(vacancy)
            if codes:
                total_with_styrk += 1
            for code in codes:
                counts_4digit[code] = counts_4digit.get(code, 0) + 1

        if page % 10 == 0:
            print(f"  Page {page}: {total_ads} ads processed, {len(counts_4digit)} unique STYRK codes")

        # Follow pagination link
        next_url = data.get("next", data.get("nextUrl", None))
        if not next_url:
            # Some APIs use _links or pageInfo
            links = data.get("_links", {})
            if isinstance(links, dict) and "next" in links:
                next_link = links["next"]
                next_url = next_link.get("href", None) if isinstance(next_link, dict) else next_link
            else:
                break

        time.sleep(PAGE_DELAY)

    print(f"\nDone: {page} pages, {total_ads} ads, {total_with_styrk} with STYRK codes")
    return counts_4digit


def aggregate(counts_4digit):
    """Build aggregated data at 4-digit and 2-digit levels."""
    data = {}

    # 4-digit entries
    for code, count in sorted(counts_4digit.items()):
        data[code] = {"code": code, "vacancies": count}

    # 2-digit aggregation
    counts_2digit = {}
    for code, count in counts_4digit.items():
        prefix = code[:2]
        counts_2digit[prefix] = counts_2digit.get(prefix, 0) + count

    for code, count in sorted(counts_2digit.items()):
        data[code] = {"code": code, "vacancies": count}

    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-pages", type=int, default=100,
                        help="Maximum number of feed pages to fetch (default: 100)")
    args = parser.parse_args()

    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Already have {len(existing)} entries in {OUTPUT_FILE}. Use --force to re-download.")
        return

    with httpx.Client() as client:
        counts_4digit = fetch_vacancies(client, args.max_pages)

    data = aggregate(counts_4digit)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    n4 = sum(1 for k in data if len(k) == 4)
    n2 = sum(1 for k in data if len(k) == 2)
    print(f"\nWrote {len(data)} entries to {OUTPUT_FILE}")
    print(f"  4-digit codes: {n4}")
    print(f"  2-digit codes: {n2}")


if __name__ == "__main__":
    main()
