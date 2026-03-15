"""
Fetch the STYRK-08 occupation classification hierarchy from SSB Klass API.

Downloads the full 4-level hierarchy and saves it as styrk_categories.json,
mapping each 4-digit code to its name and parent category.

Usage:
    uv run python fetch_styrk.py
"""

import json
import httpx

KLASS_URL = "https://data.ssb.no/api/klass/v1/classifications/7/codesAt"
OUTPUT_FILE = "styrk_categories.json"


def fetch_level(date="2025-01-01", level=None):
    """Fetch STYRK-08 codes at a given level."""
    params = {"date": date}
    if level is not None:
        params["level"] = level
    response = httpx.get(KLASS_URL, params=params, headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json()["codes"]


def main():
    print("Fetching STYRK-08 classification from SSB Klass API...")

    # Fetch all levels
    all_codes = fetch_level()

    # Build hierarchy: map code -> {name, level, parentCode}
    hierarchy = {}
    for code_entry in all_codes:
        code = code_entry["code"]
        name = code_entry["name"]
        level = code_entry.get("level", str(len(code)))
        parent = code_entry.get("parentCode", "")
        hierarchy[code] = {
            "code": code,
            "name": name,
            "level": level,
            "parentCode": parent,
        }

    # Build category lookup: for any code, find the 1-digit and 2-digit parent names
    categories = {}
    for code, info in hierarchy.items():
        entry = {
            "code": code,
            "name": info["name"],
        }
        # Find 1-digit parent (major group)
        if len(code) >= 1 and code[0] in hierarchy:
            entry["major_group"] = hierarchy[code[0]]["name"]
            entry["major_code"] = code[0]
        # Find 2-digit parent (sub-major group)
        if len(code) >= 2 and code[:2] in hierarchy:
            entry["sub_group"] = hierarchy[code[:2]]["name"]
            entry["sub_code"] = code[:2]
        categories[code] = entry

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    # Stats
    levels = {}
    for code in hierarchy:
        l = len(code)
        levels[l] = levels.get(l, 0) + 1

    print(f"Wrote {len(categories)} codes to {OUTPUT_FILE}")
    for l in sorted(levels):
        print(f"  {l}-digit codes: {levels[l]}")


if __name__ == "__main__":
    main()
