"""
Fetch occupation descriptions from the utdanning.no API.

Downloads all ~550 occupation descriptions with their STYRK-08 codes,
descriptions, education requirements, and metadata. Saves to yrker.json.

Usage:
    uv run python fetch_occupations.py
    uv run python fetch_occupations.py --force  # re-download even if cached
"""

import argparse
import json
import re
import httpx

API_URL = "https://utdanning.no/api/v1/data_norge--yrkesbeskrivelse"
OUTPUT_FILE = "yrker.json"


def slugify(title):
    """Create a URL-friendly slug from a Norwegian title."""
    s = title.lower()
    # Replace Norwegian characters
    s = s.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    # Replace non-alphanumeric with hyphens
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# Manual overrides for occupations whose utdanning.no URL doesn't match the title
URL_OVERRIDES = {
    "Snekker": "trevaresnekker",
    "Fagoperatør i akvakultur (fiskeoppdretter)": "fiskeoppdretter",
    "Brønnoperatør for elektriske kabeloperasjoner": "bronnoperator_elektriske_kabeloperasjoner",
    "Brønnoperatør for mekaniske kabeloperasjoner": "bronnoperator_mekaniske_kabeloperasjoner",
}


def url_slug(title, api_id):
    """Build correct utdanning.no URL slug from title.

    Utdanning.no URLs use a title-based slug: lowercase, spaces→underscores,
    keep hyphens, æ→ae, ø→o, å→a, parenthesized content kept with
    surrounding parens removed. Uses manual overrides for known edge cases.
    """
    if title in URL_OVERRIDES:
        return URL_OVERRIDES[title]

    s = title.lower()
    s = s.replace("æ", "ae").replace("ø", "o").replace("å", "a")
    # Special chars: ü→u, á→a, ô→o, é→e
    s = s.replace("ü", "u").replace("á", "a").replace("ô", "o").replace("é", "e")
    # Remove parens but keep content: "Bilmekaniker (lette kjøretøy)" → "bilmekaniker lette kjoretoy"
    s = s.replace("(", "").replace(")", "")
    # Replace / with space
    s = s.replace("/", " ")
    # Replace spaces with underscores, keep hyphens
    s = s.replace(" ", "_")
    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s)
    # Remove any remaining non-alphanumeric except hyphens and underscores
    s = re.sub(r"[^a-z0-9_-]", "", s)
    s = s.strip("_")
    return s


def strip_html(html):
    """Remove HTML tags and clean up whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    import os
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Already have {len(existing)} occupations in {OUTPUT_FILE}. Use --force to re-download.")
        return

    print(f"Fetching occupation list from {API_URL}...")
    response = httpx.get(API_URL, timeout=60)
    response.raise_for_status()
    url_list = response.json()

    print(f"Got {len(url_list)} entries from API")

    # The API now returns a list of URLs — fetch each one individually
    raw = []
    with httpx.Client(timeout=30) as client:
        for i, item in enumerate(url_list):
            url = item if isinstance(item, str) else item.get("url", "")
            if not url:
                continue
            try:
                r = client.get(url)
                r.raise_for_status()
                raw.append(r.json())
            except Exception as e:
                print(f"  Warning: failed to fetch {url}: {e}")
            if (i + 1) % 50 == 0:
                print(f"  Fetched {i + 1}/{len(url_list)}...")

    print(f"Successfully fetched {len(raw)} occupation details")

    occupations = []
    for entry in raw:
        title = entry.get("title", "").strip()
        if not title:
            continue

        # Extract STYRK-08 codes
        styrk_codes = []
        for s in entry.get("styrk08", []):
            if isinstance(s, str):
                code = s
            elif isinstance(s, dict):
                code = s.get("styrk08_kode", s.get("kode", s.get("code", s.get("id", ""))))
            else:
                code = ""
            code = str(code).strip()
            if code and code != "0":
                styrk_codes.append(code)

        # Extract text fields
        body = entry.get("body", {})
        if isinstance(body, dict):
            description_html = body.get("value", "")
        else:
            description_html = str(body) if body else ""

        education_html = entry.get("yrke_utdanning", "")
        if isinstance(education_html, dict):
            education_html = education_html.get("value", "")

        traits = entry.get("yrke_personegenskaper", "")
        if isinstance(traits, dict):
            traits = traits.get("value", "")

        where_work = entry.get("yrke_hvor_jobber", "")
        if isinstance(where_work, dict):
            where_work = where_work.get("value", "")

        occ_id = entry.get("sammenligning_id", entry.get("id", ""))

        occupations.append({
            "title": title,
            "id": occ_id,
            "slug": slugify(title),
            "styrk08": styrk_codes,
            "description": strip_html(description_html),
            "description_html": description_html,
            "education": strip_html(education_html),
            "education_html": education_html,
            "traits": strip_html(traits),
            "where_work": strip_html(where_work),
            "url": f"https://utdanning.no/yrker/beskrivelse/{url_slug(title, occ_id)}" if occ_id else "",
        })

    # Sort by title
    occupations.sort(key=lambda x: x["title"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(occupations, f, ensure_ascii=False, indent=2)

    # Stats
    with_styrk = sum(1 for o in occupations if o["styrk08"])
    print(f"Wrote {len(occupations)} occupations to {OUTPUT_FILE}")
    print(f"  With STYRK-08 codes: {with_styrk}")
    print(f"  Without STYRK codes: {len(occupations) - with_styrk}")

    # Show a few examples
    print("\nExamples:")
    for o in occupations[:3]:
        print(f"  {o['title']} (STYRK: {', '.join(o['styrk08'][:3])})")


if __name__ == "__main__":
    main()
